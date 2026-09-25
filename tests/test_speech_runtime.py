from __future__ import annotations

import json
import threading
import time

import pytest
from rich.console import Console

from flybg3.bridge.atomic_io import read_json
from flybg3.bridge.protocol import Action, ActionType
from flybg3.bridge.service import BridgeService
from flybg3.bridge.watcher import RequestJournal
from flybg3.config import Config, SpeechConfig, TelemetryConfig, load_config
from flybg3.speech.model import SpeechIntent
from flybg3.speech.queue import SpeechEvent, SpeechQueue
from flybg3.speech.runtime import SpeechGate, SpeechRuntime
from flybg3.speech.tts import NullTTSProvider
from flybg3.telemetry.dashboard import DisplayState, render_snapshot

BASE = {name: 0.0 for name in ("DNa02_L", "DNa02_R", "DNp01_L", "DNp01_R",
                               "DNg100_L", "DNg100_R", "MDN_L", "MDN_R")}


def _wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    pytest.fail("timed out waiting for audio worker")


def test_cooldown_and_transition():
    now = [0.0]
    gate = SpeechGate(2.0, lambda: now[0])
    assert gate.allow(SpeechIntent.RIGHT)
    now[0] = 1.0
    assert not gate.allow(SpeechIntent.RIGHT)
    assert gate.allow(SpeechIntent.DANGER_RIGHT)
    assert not gate.allow(SpeechIntent.DANGER_RIGHT)
    gate.allow(SpeechIntent.SILENT)
    assert gate.allow(SpeechIntent.DANGER_RIGHT)
    gate.reset()
    assert gate.allow(SpeechIntent.DANGER_RIGHT)


def test_queue_coalesces_direction_and_never_blocks_enqueue():
    started, release = threading.Event(), threading.Event()
    heard = []

    class SlowProvider:
        def speak(self, text):
            heard.append(text)
            started.set()
            release.wait(2)

    queue = SpeechQueue(SlowProvider(), capacity=2)
    try:
        assert queue.enqueue(SpeechEvent("s", 1, "danger", "Danger."))[0]
        assert started.wait(1)
        queue.enqueue(SpeechEvent("s", 2, "right", "Right."))
        accepted, dropped = queue.enqueue(SpeechEvent("s", 3, "danger_right", "Danger. Right."))
        assert accepted and [event.request_id for event in dropped] == [2]
        assert [event.request_id for event in queue.pending] == [3]
        release.set()
        _wait_for(lambda: heard == ["Danger.", "Danger. Right."])
    finally:
        release.set()
        queue.close()


def test_runtime_atomic_speech_file_and_session_events(tmp_path):
    events = []
    runtime = SpeechRuntime(SpeechConfig(enabled=True, provider="null"), tmp_path,
                            events.append, provider=NullTTSProvider())
    try:
        state = runtime.handle("session", 4, BASE | {"DNa02_L": 8, "DNa02_R": 1})
        assert state["intent"] == "left" and state["text"] == "Left."
        assert state["timings"]["speech_decode_ms"] >= 0
        assert state["timings"]["verbalization_ms"] >= 0
        assert state["timings"]["queue_enqueue_ms"] >= 0
        _wait_for(lambda: read_json(tmp_path / "speech.json")["status"] == "null_provider")
        assert not read_json(tmp_path / "speech.json")["spoken"]
        assert any(event["type"] == "speech" and event["request_id"] == 4 for event in events)
        state = runtime.handle("session", 5, BASE | {"DNa02_L": 8, "DNa02_R": 1})
        assert state["status"] == "suppressed" and not state["queued"]
        state = runtime.handle("session", 6, BASE)
        assert state["intent"] == "silent" and state["text"] is None
        assert not any(key in state for key in ("observation", "enemy_distance", "npc_position"))
    finally:
        runtime.close()


def test_tts_exception_cannot_change_bridge_action(tmp_path, observation):
    class FailingProvider:
        def speak(self, text):
            raise OSError("no audio device")

    class FakeSimulation:
        def decide(self, obs):
            action = Action(obs["session_id"], obs["request_id"], obs["npc"]["uuid"], ActionType.TURN_RIGHT)
            return action, {"stimulus": {}, "neural_activity": {"rates_hz": BASE | {"DNa02_R": 8}},
                            "scores": {}, "timings": {"total_ms": 1, "decision_path_ms": 1}}

    config = Config()
    config.speech.enabled = True
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    events = []
    runtime = SpeechRuntime(config.speech, tmp_path, events.append, provider=FailingProvider())
    service = BridgeService(config, simulation=FakeSimulation(), speech=runtime)
    runtime.log_event = lambda event: (events.append(event), service._append_event(event))
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    try:
        assert service.process(observation, journal)
        _wait_for(lambda: read_json(tmp_path / "speech.json")["status"] == "failed")
        assert read_json(tmp_path / "action.json")["action"] == "turn_right"
        assert service.simulation is not None
        assert any(event.get("status") == "failed" for event in events)
        assert any(json.loads(line).get("type") == "speech" for line in service.log_path.read_text().splitlines())
    finally:
        runtime.close()
        journal.close()


def test_speech_disabled_means_no_audio_or_speech_file(tmp_path, observation):
    class FakeSimulation:
        def decide(self, obs):
            return Action(obs["session_id"], obs["request_id"], obs["npc"]["uuid"], ActionType.IDLE), {
                "stimulus": {}, "neural_activity": {"rates_hz": BASE}, "scores": {},
                "timings": {"total_ms": 1, "decision_path_ms": 1}}

    config = Config()
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    service = BridgeService(config, simulation=FakeSimulation())
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    try:
        assert service.speech is None
        assert service.process(observation, journal)
        assert not (tmp_path / "speech.json").exists()
    finally:
        journal.close()


def test_dashboard_shows_matching_speech_only():
    snapshot = {"schema_version": 1, "session_id": "session", "request_id": 2,
                "groups": {}, "decision": "TURN_RIGHT"}
    speech = {"session_id": "session", "request_id": 2, "intent": "danger_right",
              "text": "Danger. Right.", "confidence": 0.87, "urgency": 0.74, "status": "queued"}
    console = Console(record=True, width=100)
    console.print(render_snapshot(snapshot, TelemetryConfig(), DisplayState(), speech=speech))
    rendered = console.export_text()
    assert "DANGER_RIGHT" in rendered and "Danger. Right." in rendered
    assert "87%" in rendered and "74%" in rendered
    other = Console(record=True, width=100)
    other.print(render_snapshot(snapshot, TelemetryConfig(), DisplayState(), speech=speech | {"request_id": 1}))
    assert "Danger. Right." not in other.export_text()


def test_speech_config_nested_voice_and_validation(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[speech]\nenabled = true\nprovider = 'null'\n[speech.voice]\nrate = -2\nvolume = 80\n")
    config = load_config(path)
    assert config.speech.enabled and config.speech.voice.rate == -2
    config.speech.voice.volume = 101
    with pytest.raises(ValueError, match="voice"):
        config.validate()


@pytest.mark.brain
def test_real_brain_speech_side_channel_never_steps_or_changes_action(tmp_path, observation):
    import numpy as np
    from flybg3.brain.simulation import Simulation

    off, on = Config(), Config()
    off.performance.device = on.performance.device = "cpu"
    on.speech.enabled = True
    sim_off, sim_on = Simulation(off), Simulation(on)
    counts = {"off": 0, "on": 0}
    for sim, key in ((sim_off, "off"), (sim_on, "on")):
        original = sim.brain.brain.step

        def counted(*args, original=original, key=key, **kwargs):
            counts[key] += 1
            return original(*args, **kwargs)

        sim.brain.brain.step = counted
    runtime = SpeechRuntime(on.speech, tmp_path, lambda event: None, provider=NullTTSProvider())
    try:
        for rid, angle in ((1, -75.0), (2, 75.0)):
            observation["request_id"] = rid
            observation["sample_time_ms"] = rid * 1000
            observation["nearest_hostile"].update(relative_angle=angle, closing_speed=1.0)
            a_off, r_off = sim_off.decide(observation)
            a_on, r_on = sim_on.decide(observation)
            runtime.handle(observation["session_id"], rid, r_on["neural_activity"]["rates_hz"])
            assert a_off.action == a_on.action and a_off.confidence == a_on.confidence
            assert r_off["neural_activity"]["spikes"] == r_on["neural_activity"]["spikes"]
            assert r_off["neural_activity"]["rates_hz"] == r_on["neural_activity"]["rates_hz"]
            assert r_off["scores"] == r_on["scores"]
            np.testing.assert_array_equal(sim_off.brain.brain.v, sim_on.brain.brain.v)
            assert counts == {"off": rid * off.brain.simulation_steps,
                              "on": rid * on.brain.simulation_steps}
    finally:
        runtime.close()
