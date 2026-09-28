"""Single worker, nonblocking game peer; exceptions never substitute fake AI."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
import time
from uuid import uuid4
from flybg3.config import Config
from flybg3.brain.simulation import Simulation
from flybg3.speech.runtime import SpeechRuntime
from .atomic_io import atomic_write_json, read_json
from .protocol import Action, ActionType, ProtocolError, uuid_string
from .watcher import RequestJournal, observation_at, single_instance

LOG = logging.getLogger("FlyBG3")


class BridgeService:
    def __init__(self, config: Config, simulation=None, speech=None, combat_probe=None):
        self.config = config
        self.directory = config.directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.simulation = simulation
        self.last_request = 0
        self.session: str | None = None
        self.stopped = threading.Event()
        self.failure: str | None = None
        self.log_path = Path(config.bridge.log_directory) / f"session-{datetime.now():%Y%m%d-%H%M%S}-{str(uuid4())[:8]}.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_lock = threading.Lock()
        self.speech = speech if speech is not None else (
            SpeechRuntime(config.speech, self.directory, self._append_event) if config.speech.enabled else None)
        self.combat_probe = combat_probe

    def _append_event(self, event: dict) -> None:
        with self.log_lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, allow_nan=False) + "\n")
                f.flush()

    def heartbeat(self, alive: bool = True) -> None:
        atomic_write_json(self.directory / "heartbeat_brain.json", {
            "schema_version": 1, "alive": alive, "brain_loaded": self.simulation is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(), "unix_ms": int(time.time() * 1000),
            "session_id": self.session, "last_request": self.last_request, "error": self.failure})

    def _heartbeats(self) -> None:
        while not self.stopped.wait(1):
            try:
                self.heartbeat()
            except OSError:
                LOG.exception("Cannot write heartbeat")

    def load(self) -> None:
        try:
            LOG.info("Loading MaleCNS...")
            self.simulation = Simulation(self.config)
            self.failure = None
            LOG.info("%s neurons loaded; backend %s", self.simulation.brain.brain.n, self.simulation.brain.brain.device)
        except Exception as e:
            self.simulation = None
            self.failure = str(e)
            LOG.exception("FlyBG3 ERROR: fly brain unavailable")

    def process(self, observation: dict, journal: RequestJournal) -> bool:
        expected = self.config.bridge.npc_uuid.lower()
        if expected and observation["npc"]["uuid"].lower() != expected:
            return False
        if not journal.claim(observation["session_id"], observation["request_id"]):
            return False
        LOG.info("Processing observation #%s", observation["request_id"])
        record = {"observation": observation, "stimulus": {}, "neural_activity": {}, "scores": {}}
        try:
            if self.simulation is None:
                raise RuntimeError("fly brain unavailable")
            if self.session != observation["session_id"]:
                if self.session is not None:
                    self.simulation.reset()
                    if self.speech:
                        self.speech.reset()
                self.session = observation["session_id"]
            action, record = self.simulation.decide(observation)
            if record["timings"].get("decision_path_ms", record["timings"]["total_ms"]) > self.config.performance.decision_timeout_ms:
                record["neural_action_before_timeout"] = action.to_dict()
                action = Action(observation["session_id"], observation["request_id"], observation["npc"]["uuid"],
                                debug={"error": "decision_timeout", "timings": record["timings"]})
        except Exception as e:
            self.failure = str(e)
            self.simulation = None  # partially updated neural state cannot silently continue
            LOG.exception("FlyBG3 ERROR: fly brain unavailable")
            action = Action(observation["session_id"], observation["request_id"], observation["npc"]["uuid"],
                            debug={"error": "fly brain unavailable", "detail": str(e)})
        self.last_request = observation["request_id"]
        self.session = observation["session_id"]
        record["action"] = action.to_dict()
        if "telemetry" in record:
            record["telemetry"]["decision"] = action.action.upper()
        record["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._append_event(record)
        atomic_write_json(self.directory / "action.json", action.to_dict())
        if self.combat_probe and not action.debug.get("error"):
            try:
                shadow = self.combat_probe.inspect(
                    record["neural_activity"], session_id=observation["session_id"],
                    request_id=observation["request_id"])
                self._append_event({"type": "combat_observe", **shadow})
                atomic_write_json(self.directory / "combat_observe.json", shadow)
                LOG.info("Combat shadow #%s: %s (observe only)",
                         shadow["request_id"], shadow["candidate_action"].upper())
            except Exception:
                LOG.exception("Combat shadow failed; BG3 action already published")
        if self.speech and not action.debug.get("error"):
            rates = record.get("neural_activity", {}).get("rates_hz")
            if rates:
                try:
                    self.speech.handle(observation["session_id"], observation["request_id"], rates)
                except Exception:
                    LOG.exception("Neural speech failed; action already published")
        if "telemetry" in record:
            try:
                started = time.perf_counter()
                atomic_write_json(self.directory / "telemetry.json", record["telemetry"])
                LOG.debug("Telemetry compute %.2f ms; write %.2f ms",
                          record["telemetry"]["telemetry_compute_ms"], (time.perf_counter() - started) * 1000)
            except Exception:
                LOG.exception("Telemetry write failed; neural action already published")
        LOG.info("Decision: %s; scores=%s; timings=%s", action.action.upper(), record["scores"], record.get("timings", {}))
        LOG.debug("Stimulus=%s descending=%s", record["stimulus"], record["neural_activity"])
        return True

    def run(self, once: bool = False) -> None:
        if self.config.bridge.npc_uuid:
            uuid_string(self.config.bridge.npc_uuid)
        with single_instance(self.directory):
            journal = RequestJournal(self.directory / "requests.sqlite3")
            self.heartbeat()
            worker = threading.Thread(target=self._heartbeats, daemon=True)
            worker.start()
            try:
                if self.simulation is None:
                    self.load()
                self.heartbeat()
                LOG.info("Watching BG3: %s\nWaiting for observation...", self.directory)
                last_error = ""
                while not self.stopped.is_set():
                    try:
                        command = read_json(self.directory / "control.json")
                        if command and command.get("command") == "reset":
                            token = uuid_string(command.get("command_id"))
                            if journal.claim("reset:" + token, 1):
                                if self.simulation:
                                    self.simulation.reset()
                                    if self.speech:
                                        self.speech.reset()
                                else:
                                    self.load()
                                LOG.info("Manual neural reset %s", token)
                        observation = observation_at(self.directory / "observation.json", self.config.bridge.max_json_bytes)
                        if observation:
                            hb = read_json(self.directory / "heartbeat_bg3.json")
                            fresh = (hb and hb.get("alive") is True and hb.get("session_id") == observation["session_id"]
                                     and type(hb.get("unix_ms")) in (int, float)
                                     and 0 <= time.time() * 1000 - hb["unix_ms"] <= 10000)
                            if fresh and self.process(observation, journal) and once:
                                if self.speech:
                                    self.speech.queue.wait_idle(timeout=15)
                                break
                        last_error = ""
                    except (ProtocolError, OSError, ValueError) as e:
                        if str(e) != last_error:
                            LOG.warning("Ignoring unavailable/malformed request: %s", e)
                        last_error = str(e)
                    self.stopped.wait(self.config.performance.poll_ms / 1000)
            finally:
                self.stopped.set()
                worker.join(timeout=2)
                self.heartbeat(alive=False)
                journal.close()
                if self.speech:
                    self.speech.close()
