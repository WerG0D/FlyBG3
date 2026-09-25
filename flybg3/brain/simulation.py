"""Stateful pipeline with group-level audit records and timings."""
from __future__ import annotations

from dataclasses import asdict
import logging
from time import perf_counter
from flybg3.config import Config
from flybg3.bridge.protocol import Action
from .encoder import SensoryEncoder
from .decoder import MotorDecoder
from .fly_brain import FlyBrainAdapter
from flybg3.telemetry.collector import TelemetryCollector
from flybg3.telemetry.registry import resolve_telemetry_groups

LOG = logging.getLogger("FlyBG3")


class Simulation:
    def __init__(self, config: Config):
        self.config = config
        self.brain = FlyBrainAdapter(config)
        self.encoder = SensoryEncoder(config.encoder)
        self.decoder = MotorDecoder(config.decoder)
        self.telemetry_groups = {}
        if config.telemetry.enabled:
            try:
                self.telemetry_groups = resolve_telemetry_groups(self.brain.brain)
            except Exception:
                LOG.exception("Telemetry probes unavailable; neural decisions remain active")

    def reset(self) -> None:
        self.brain.reset()
        self.encoder.reset()
        self.decoder.reset()

    def decide(self, observation: dict) -> tuple[Action, dict]:
        t0 = perf_counter()
        stimulus = self.encoder.encode(observation)
        t1 = perf_counter()
        observer = None
        if self.telemetry_groups:
            try:
                observer = TelemetryCollector(self.telemetry_groups, self.brain.brain.n,
                                              self.config.decoder.decision_window, self.brain.brain.dt)
            except Exception:
                LOG.exception("Telemetry collector unavailable; neural decision continues")
        neural = self.brain.simulate(stimulus, observer=observer)
        t2 = perf_counter()
        decision = self.decoder.decode(neural["rates_hz"])
        t3 = perf_counter()
        timings = dict(zip(("encoder_ms", "simulation_ms", "decoder_ms", "total_ms"),
                           (1000 * (t1-t0), 1000 * (t2-t1), 1000 * (t3-t2), 1000 * (t3-t0))))
        timings["decision_path_ms"] = max(0.0, timings["total_ms"] - (observer.compute_ms if observer else 0.0))
        action = Action(observation["session_id"], observation["request_id"], observation["npc"]["uuid"],
                        decision.action, decision.confidence,
                        (observation.get("nearest_hostile") or {}).get("uuid"),
                        {"scores": decision.scores, "timings": timings, "neural_activity": neural})
        record = {"observation": observation, "stimulus": stimulus, "neural_activity": neural,
                  "scores": decision.scores, "action": action.to_dict(), "timings": timings,
                  "parameters": asdict(self.config)}
        if observer is not None and not observer.failed:
            try:
                record["telemetry"] = observer.snapshot(observation, action.action.upper(),
                                                         timings["simulation_ms"]).to_dict()
                if self.config.dashboard.enabled:
                    from flybg3.telemetry.connectome import active_snapshot
                    visual_start = perf_counter()
                    record["visualization"] = active_snapshot(
                        self.brain.brain, observer.active,
                        self.config.dashboard.max_active_neurons,
                        self.config.dashboard.max_edges)
                    timings["visualization_ms"] = 1000 * (perf_counter() - visual_start)
            except Exception:
                LOG.exception("Telemetry snapshot unavailable; neural decision continues")
        return action, record
