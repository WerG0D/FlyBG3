from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from rich.console import Console

from flybg3.bridge.atomic_io import read_json
from flybg3.bridge.protocol import Action, ActionType
from flybg3.bridge.service import BridgeService
from flybg3.bridge.watcher import RequestJournal
from flybg3.config import Config, TelemetryConfig, load_config
from flybg3.telemetry.collector import TelemetryCollector
from flybg3.telemetry.dashboard import DisplayState, normalized_display_rate, render_snapshot, run_dashboard
from flybg3.telemetry.registry import ResolvedGroup, TelemetryGroup, resolve_telemetry_groups


def test_registry_skips_absent_optional_groups(caplog):
    class TinyBrain:
        cell_type = np.array(["DNa02", "DNa02", "DNp01"])
        side = np.array(["L", "R", "L"])

        def cells(self, types, side=None):
            selected = np.isin(self.cell_type, types)
            if side:
                selected &= self.side == side
            return np.flatnonzero(selected)

    groups = resolve_telemetry_groups(TinyBrain())
    assert groups["steer_left"].neuron_count == 1
    assert groups["steer_right"].neuron_count == 1
    assert groups["escape"].neuron_count == 1
    assert "grooming" not in groups
    assert "pam" not in groups
    assert "disabled" in caplog.text


def test_population_rate_and_window_are_normalized(observation):
    small = TelemetryGroup("small", "SMALL", ("a",), "test", default=True)
    large = TelemetryGroup("large", "LARGE", ("b",), "test", default=True)
    groups = {"small": ResolvedGroup(small, np.array([0, 1]), {"a": 2}),
              "large": ResolvedGroup(large, np.arange(2, 22), {"b": 20})}
    collector = TelemetryCollector(groups, neuron_count=22, window_steps=2, dt=0.5)
    collector.observe(np.array([0, 2, 3]))
    collector.observe(np.array([1, 4, 5]))
    collector.observe(np.array([0, 6, 7]))  # first frame leaves the rate window
    result = collector.snapshot(observation, "TURN_LEFT", 250).to_dict()
    assert result["groups"]["small"] == {"hz": 1.0, "spikes": 2, "neurons": 2}
    assert result["groups"]["large"] == {"hz": 0.2, "spikes": 4, "neurons": 20}
    assert result["total_spikes"] == 9
    assert result["active_neurons"] == 8
    assert result["window_seconds"] == 1.0
    assert result["environment"]["heading_degrees"] is None


def test_display_smoothing_and_scale_never_change_raw_snapshot():
    config = TelemetryConfig(smoothing=0.25)
    state = DisplayState()
    assert state.displayed_rate("escape", 4.0, config.smoothing) == 4.0
    assert state.displayed_rate("escape", 8.0, config.smoothing) == 5.0
    assert normalized_display_rate(5.0, 10.0) == 0.5
    assert normalized_display_rate(50.0, 10.0) == 1.0


def test_dashboard_renders_neural_and_perception_context():
    snapshot = {"schema_version": 1, "session_id": str(uuid4()), "request_id": 16,
                "groups": {"steer_left": {"hz": 1.0}, "steer_right": {"hz": 7.0},
                           "escape": {"hz": 3.0}},
                "individual_groups": {"DNp01": {"hz": 2.0}},
                "total_spikes": 18329, "active_neurons": 12428,
                "simulation_ms": 267.0, "telemetry_compute_ms": 0.8,
                "environment": {"enemy_distance": 2.72, "enemy_relative_angle": 118.4,
                                "closing_speed": 0.0, "heading_degrees": -84.73},
                "decision": "TURN_RIGHT"}
    console = Console(record=True, width=100, force_terminal=False)
    console.print(render_snapshot(snapshot, TelemetryConfig(), DisplayState(), debug=True))
    rendered = console.export_text()
    for expected in ("STEER LEFT", "STEER RIGHT", "ESCAPE", "DNp01", "12,428", "18,329",
                     "2.72 m", "118.40 deg", "-84.73 deg", "TURN_RIGHT"):
        assert expected in rendered


def test_dashboard_prints_complete_panel_in_noninteractive_console(tmp_path):
    snapshot = {"schema_version": 1, "session_id": str(uuid4()), "request_id": 7,
                "groups": {"steer_left": {"hz": 2.0}},
                "individual_groups": {}, "decision": "TURN_LEFT"}
    (tmp_path / "telemetry.json").write_text(json.dumps(snapshot), encoding="utf-8")
    console = Console(record=True, width=100, force_terminal=False)
    run_dashboard(tmp_path, TelemetryConfig(), once=True, console=console)
    rendered = console.export_text()
    assert "STEER LEFT" in rendered
    assert "DECISION: TURN_LEFT" in rendered
    assert "request #7" in rendered


def test_config_nested_telemetry_scale(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[telemetry]\nenabled = false\nsmoothing = 0.5\n"
                    "[telemetry.scale]\nescape_max_hz = 25.0\n", encoding="utf-8")
    config = load_config(path)
    assert not config.telemetry.enabled
    assert config.telemetry.scale.escape_max_hz == 25
    config.telemetry.scale.escape_max_hz = 0
    with pytest.raises(ValueError, match="visual scales"):
        config.validate()


def test_service_publishes_separate_telemetry_and_logs_it(tmp_path, observation):
    class FakeSimulation:
        def decide(self, obs):
            action = Action(obs["session_id"], obs["request_id"], obs["npc"]["uuid"], ActionType.TURN_LEFT)
            telemetry = {"schema_version": 1, "session_id": obs["session_id"], "request_id": obs["request_id"],
                         "groups": {"steer_left": {"hz": 3.0, "spikes": 3, "neurons": 1}},
                         "individual_groups": {}, "decision": "TURN_LEFT", "telemetry_compute_ms": 0.1}
            return action, {"timings": {"total_ms": 1.0, "decision_path_ms": 0.9},
                            "stimulus": {}, "neural_activity": {}, "scores": {}, "telemetry": telemetry}

    config = Config()
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    service = BridgeService(config, simulation=FakeSimulation())
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    try:
        assert service.process(observation, journal)
        assert read_json(tmp_path / "telemetry.json")["request_id"] == observation["request_id"]
        assert "telemetry" not in read_json(tmp_path / "action.json")
        record = json.loads(service.log_path.read_text(encoding="utf-8").splitlines()[0])
        assert record["telemetry"]["groups"]["steer_left"]["hz"] == 3.0
        assert not service.process(observation, journal)
    finally:
        journal.close()


def test_telemetry_write_failure_does_not_change_action(tmp_path, observation, monkeypatch):
    from flybg3.bridge import service as module
    original = module.atomic_write_json

    def fail_telemetry(path: Path, data: dict):
        if path.name == "telemetry.json":
            raise OSError("display disk issue")
        return original(path, data)

    class FakeSimulation:
        def decide(self, obs):
            return Action(obs["session_id"], obs["request_id"], obs["npc"]["uuid"], ActionType.TURN_RIGHT), {
                "timings": {"total_ms": 1.0, "decision_path_ms": 1.0},
                "stimulus": {}, "neural_activity": {}, "scores": {},
                "telemetry": {"schema_version": 1, "decision": "TURN_RIGHT", "telemetry_compute_ms": 0.0}}

    monkeypatch.setattr(module, "atomic_write_json", fail_telemetry)
    config = Config()
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    service = BridgeService(config, simulation=FakeSimulation())
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    try:
        assert service.process(observation, journal)
        assert read_json(tmp_path / "action.json")["action"] == "turn_right"
    finally:
        journal.close()


@pytest.mark.brain
def test_real_brain_telemetry_does_not_change_spikes_state_or_decision(observation):
    from flybg3.brain.simulation import Simulation

    on = Config()
    on.performance.device = "cpu"
    off = Config()
    off.performance.device = "cpu"
    off.telemetry.enabled = False
    with_telemetry = Simulation(on)
    without_telemetry = Simulation(off)
    observation["nearest_hostile"].update(distance=4.0, relative_angle=-75.0, closing_speed=5.0)
    counts = {"on": 0, "off": 0}
    for sim, key in ((with_telemetry, "on"), (without_telemetry, "off")):
        original = sim.brain.brain.step

        def counted(*args, original=original, key=key, **kwargs):
            counts[key] += 1
            return original(*args, **kwargs)

        sim.brain.brain.step = counted
    for request_id, angle in ((1, -75.0), (2, 75.0)):
        observation["request_id"] = request_id
        observation["sample_time_ms"] = request_id * 1000
        observation["nearest_hostile"]["relative_angle"] = angle
        action_on, record_on = with_telemetry.decide(observation)
        action_off, record_off = without_telemetry.decide(observation)
        assert counts == {"on": request_id * on.brain.simulation_steps,
                          "off": request_id * off.brain.simulation_steps}
        assert action_on.action == action_off.action
        assert action_on.confidence == action_off.confidence
        assert record_on["neural_activity"] == record_off["neural_activity"]
        assert record_on["scores"] == record_off["scores"]
        np.testing.assert_array_equal(with_telemetry.brain.brain.v, without_telemetry.brain.brain.v)
        assert "telemetry" in record_on and "telemetry" not in record_off
        assert record_on["telemetry"]["decision"] == action_on.action.upper()
