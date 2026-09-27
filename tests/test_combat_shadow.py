from __future__ import annotations

import inspect
import json
import pytest

from flybg3.bridge.atomic_io import read_json
from flybg3.bridge.protocol import Action, ActionType
from flybg3.bridge.service import BridgeService
from flybg3.bridge.watcher import RequestJournal
from flybg3.combat.model import FEATURE_NAMES
from flybg3.combat.policy_gradient import PolicyGradientReadoutPolicy
from flybg3.combat.shadow import CombatShadowProbe
from flybg3.config import Config, load_config


class _FakeSimulation:
    def __init__(self):
        self.calls = 0

    def decide(self, observation):
        self.calls += 1
        rates = {name: 0.0 for name in FEATURE_NAMES}
        rates["DNp01_L"] = 12.0
        return Action(observation["session_id"], observation["request_id"],
                      observation["npc"]["uuid"], ActionType.TURN_RIGHT), {
            "timings": {"total_ms": 1.0, "decision_path_ms": 1.0},
            "stimulus": {}, "scores": {},
            "neural_activity": {"rates_hz": rates, "spikes": {}},
        }


def test_shadow_probe_sees_only_neural_activity_and_valid_checkpoint(tmp_path):
    checkpoint = tmp_path / "policy.json"
    PolicyGradientReadoutPolicy(seed=42).save(checkpoint, {})
    probe = CombatShadowProbe(checkpoint, algorithm="reinforce", seed=42)
    parameters = set(inspect.signature(probe.inspect).parameters)
    assert parameters == {"neural_activity", "session_id", "request_id"}
    rates = {name: 0.0 for name in FEATURE_NAMES}
    result = probe.inspect({"rates_hz": rates}, session_id="session", request_id=4)
    assert result["request_id"] == 4 and result["mode"] == "observe_only"
    assert result["candidate_action"] in {"idle", "approach", "retreat", "basic_attack", "end_turn"}
    assert set(result["features_hz"]) == set(FEATURE_NAMES)
    with pytest.raises(ValueError, match="seed"):
        CombatShadowProbe(checkpoint, algorithm="reinforce", seed=43)
    with pytest.raises(ValueError, match="algorithm"):
        CombatShadowProbe(checkpoint, algorithm="td", seed=42)


def test_bridge_combat_probe_is_read_only_side_channel(tmp_path, observation):
    checkpoint = tmp_path / "policy.json"
    PolicyGradientReadoutPolicy(seed=42).save(checkpoint, {})
    probe = CombatShadowProbe(checkpoint, algorithm="reinforce", seed=42)

    def run(directory, combat_probe):
        config = Config()
        config.bridge.directory = str(directory)
        config.bridge.log_directory = str(directory / "logs")
        simulation = _FakeSimulation()
        service = BridgeService(config, simulation=simulation, combat_probe=combat_probe)
        journal = RequestJournal(directory / "requests.sqlite3")
        try:
            assert service.process(observation, journal)
            assert not service.process(observation, journal)
        finally:
            journal.close()
        return read_json(directory / "action.json"), simulation.calls, service

    off = tmp_path / "off"
    on = tmp_path / "on"
    action_off, calls_off, _ = run(off, None)
    action_on, calls_on, service = run(on, probe)
    assert action_on == action_off
    assert action_on["action"] == "turn_right"
    assert calls_off == calls_on == 1
    assert probe.policy.updates == 0
    shadow = read_json(on / "combat_observe.json")
    assert (shadow["session_id"], shadow["request_id"]) == (
        observation["session_id"], observation["request_id"])
    assert not {"observation", "enemy", "distance", "npc", "hp"} & set(shadow)
    assert "combat_observe" not in action_on
    lines = [json.loads(line) for line in service.log_path.read_text().splitlines()]
    assert lines[-1]["type"] == "combat_observe"


def test_shadow_failure_cannot_block_original_action(tmp_path, observation):
    class BrokenProbe:
        def inspect(self, *_args, **_kwargs):
            raise RuntimeError("readout device failed")

    config = Config()
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    service = BridgeService(config, simulation=_FakeSimulation(), combat_probe=BrokenProbe())
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    try:
        assert service.process(observation, journal)
    finally:
        journal.close()
    assert read_json(tmp_path / "action.json")["action"] == "turn_right"
    assert not (tmp_path / "combat_observe.json").exists()


def test_game_observe_config_keeps_physical_actions_disabled():
    config = load_config("config/combat-bg3-observe.toml")
    assert config.combat.mode == "observe"
    assert config.combat.algorithm == "reinforce"
    assert not config.combat.physical_actions_enabled
    assert not config.dashboard.enabled
