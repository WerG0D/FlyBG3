from __future__ import annotations

from dataclasses import asdict
import inspect
import json

import pytest

from flybg3.brain.encoder import SensoryEncoder
from flybg3.combat.arena import CombatArena
from flybg3.combat.experiment import run_control
from flybg3.combat.features import NeuralFeatureExtractor
from flybg3.combat.model import CombatAction, CombatEpisode, CombatOutcome, FEATURE_NAMES, NeuralFeatures
from flybg3.combat.policy import FrozenPolicy, RandomPolicy, TrainableNeuralReadoutPolicy
from flybg3.combat.reward import RewardEngine
from flybg3.combat.runner import EpisodeRunner
from flybg3.config import EncoderConfig


def features(value=1.0):
    return NeuralFeatures((value,) * len(FEATURE_NAMES))


def test_policy_boundary_has_only_neural_features():
    assert "observation" not in inspect.signature(TrainableNeuralReadoutPolicy.select_action).parameters
    assert "features" in inspect.signature(TrainableNeuralReadoutPolicy.select_action).parameters
    with pytest.raises((KeyError, TypeError)):
        NeuralFeatureExtractor().extract({"npc": {"hp": 1}})
    assert features().vector()[0] == 1.0


def test_reward_is_about_observed_consequences():
    reward = RewardEngine()
    result = reward.calculate(CombatOutcome("executed", damage_dealt=10, damage_received=15,
                                            enemy_kill=True, victory=True))
    assert result.damage_dealt == 0.20
    assert result.damage_received == -0.30
    assert result.kill == 1 and result.victory == 3
    assert round(result.total, 2) == 3.9
    assert reward.calculate(CombatOutcome("invalid")).total == -0.05
    assert reward.calculate(CombatOutcome("executed", self_death=True, defeat=True)).total == -4.0
    assert reward.calculate(CombatOutcome("executed", timeout=True)).total == -1.0


def test_retreating_to_timeout_is_not_free():
    arena = CombatArena(42, max_turns=2)
    arena.state.distance = 10.0
    _, terminal, _ = arena.step(CombatAction.RETREAT)
    assert not terminal
    outcome, terminal, result = arena.step(CombatAction.RETREAT)
    assert terminal and result == "timeout"
    assert RewardEngine().calculate(outcome).total == -1.0


def test_linear_policy_determinism_freeze_and_checkpoint(tmp_path):
    a, b = TrainableNeuralReadoutPolicy(seed=7), TrainableNeuralReadoutPolicy(seed=7)
    f = features(12)
    assert a.select_action(f, training=False) == b.select_action(f, training=False)
    before = [row[:] for row in a.weights]
    choice = a.select_action(f, training=False).action
    a.observe_transition(f, choice, 2.0, features(3), training=False)
    assert a.weights == before
    a.observe_transition(f, choice, 2.0, features(3), training=True)
    assert a.weights != before
    checkpoint = tmp_path / "policy.json"
    a.save(checkpoint, {"seed": 7})
    loaded = TrainableNeuralReadoutPolicy.load(checkpoint)
    assert loaded.weights == a.weights
    assert loaded.select_action(f, training=True) == a.select_action(f, training=True)
    with pytest.raises(FileExistsError):
        a.save(checkpoint, {})
    frozen = FrozenPolicy(seed=7)
    frozen.observe_transition(f, choice, 10, None, training=True)
    assert frozen.updates == 0
    assert RandomPolicy(seed=7).select_action(f, training=False).action in CombatAction
    first = RandomPolicy(seed=7)
    second = RandomPolicy(seed=7)
    assert [first.select_action(f, training=False).action for _ in range(10)] == [
        second.select_action(f, training=False).action for _ in range(10)]


def test_episode_rejects_second_terminal_state():
    episode = CombatEpisode(1, "start")
    episode.end("timeout", "end")
    with pytest.raises(ValueError):
        episode.end("victory", "later")


def test_hp_and_near_field_are_inputs_not_action_rules():
    arena = CombatArena(42)
    obs = arena.observation("00000000-0000-4000-8000-000000000001", 1)
    encoder = SensoryEncoder(EncoderConfig(health_stress_gain=0.4, proximity_gain=0.6))
    healthy = encoder.encode(obs)
    obs["npc"]["hp"] = obs["npc"]["max_hp"] // 2
    low_hp = encoder.encode(obs)
    assert low_hp["LC4_L"] > healthy["LC4_L"]
    assert low_hp["LC4_R"] > healthy["LC4_R"]
    obs["nearest_hostile"]["distance"] = 1.0
    near = encoder.encode(obs)
    assert near["LC10a_L"] > low_hp["LC10a_L"]


def test_invalid_attack_is_reported_not_replaced():
    arena = CombatArena(1)
    arena.state.distance = 5
    outcome, _, _ = arena.step(CombatAction.BASIC_ATTACK)
    assert outcome.status == "invalid"
    assert outcome.reason == "target_out_of_melee_range"
    assert outcome.damage_dealt == 0


def test_holdout_opponent_changes_environment_not_policy_inputs():
    a = CombatArena(7, opponent="A")
    b = CombatArena(7, opponent="B")
    assert b.state.enemy_hp > a.state.enemy_hp
    assert b.state.distance > a.state.distance
    assert "opponent" not in b.observation("00000000-0000-4000-8000-000000000001", 1)


def test_kiting_opponent_requires_action_switch_not_constant_attack():
    for opponent in ("C", "D"):
        arena = CombatArena(7, opponent=opponent, max_turns=4)
        start_distance = arena.state.distance
        for _ in range(4):
            outcome, terminal, _ = arena.step(CombatAction.BASIC_ATTACK)
            assert outcome.status == "invalid"
            assert outcome.damage_dealt == 0
            if terminal:
                break
        assert arena.state.distance >= start_distance
        assert arena.state.enemy_hp == arena.state.enemy_max_hp


def test_curriculum_opponent_has_winning_approach_then_attack_path():
    arena = CombatArena(7, opponent="D", max_turns=8)
    arena.step(CombatAction.APPROACH)
    assert arena.state.distance <= 1.5
    for _ in range(4):
        outcome, terminal, result = arena.step(CombatAction.BASIC_ATTACK)
        assert outcome.status == "executed"
        if terminal:
            break
    assert terminal and result == "victory"


class _SyntheticSimulation:
    """Test double only: production arena runner uses Simulation/MaleCNS."""
    def __init__(self):
        self.calls = 0
        self.brain = self

    def info(self):
        return {"name": "test-double"}

    def reset(self):
        self.calls = 0

    def decide(self, observation):
        self.calls += 1
        rates = {name: 0.0 for name in FEATURE_NAMES}
        rates["DNa02_L"] = observation["nearest_hostile"]["distance"]
        return None, {"neural_activity": {"rates_hz": rates, "spikes": {}},
                      "stimulus": {}, "timings": {"simulation_ms": 1.0}}


def test_closed_loop_reward_after_outcome_and_dashboard_cannot_change_action():
    def run(sink):
        sim, policy = _SyntheticSimulation(), TrainableNeuralReadoutPolicy(seed=21)
        events = []
        def observer(event):
            events.append(event)
            if sink:
                raise RuntimeError("dashboard disconnected")
        episode = EpisodeRunner(sim, policy, RewardEngine(), sink=observer).run(
            CombatArena(21, max_turns=4), 1, training=False)
        return episode, sim.calls, events, policy.updates
    off, calls_off, events_off, updates_off = run(False)
    on, calls_on, _, updates_on = run(True)
    assert [t["action"] for t in off.transitions] == [t["action"] for t in on.transitions]
    assert [t["features"] for t in off.transitions] == [t["features"] for t in on.transitions]
    assert calls_off == calls_on == off.turn_count
    assert updates_off == updates_on == 0
    assert off.ended_at and off.result in {"victory", "defeat", "timeout"}
    event_names = [e["event"] for e in events_off]
    assert event_names.index("action_result") < event_names.index("reward")
    assert event_names.index("reward") < event_names.index("episode_end")


def test_training_resumes_checkpoint_and_skips_old_arena_seeds(tmp_path):
    from flybg3.config import Config

    config = Config()
    config.combat.max_turns = 2
    old = TrainableNeuralReadoutPolicy(seed=42)
    old.episodes = 5
    checkpoint = tmp_path / "parent.json"
    old.save(checkpoint, {})
    run = tmp_path / "continued"
    result = run_control(config, "trainable", 42, 1, 1, root=run,
                         simulation=_SyntheticSimulation(), checkpoint=checkpoint)
    episodes = [json.loads(line) for line in (run / "episodes.jsonl").read_text().splitlines()]
    assert [episode["episode_id"] for episode in episodes] == [6, 7]
    assert result["training"]["episodes"] == result["evaluation"]["episodes"] == 1
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["parent_checkpoint"]["rng_state_restored"] is True
    saved = next((run / "checkpoints").glob("policy_final_*.json"))
    resumed = TrainableNeuralReadoutPolicy.load(saved)
    assert resumed.episodes == 6
    with pytest.raises(ValueError, match="seed"):
        run_control(config, "trainable", 43, 0, 1, simulation=_SyntheticSimulation(),
                    checkpoint=checkpoint)
    ablated = run_control(config, "zero", 42, 0, 1,
                          simulation=_SyntheticSimulation(), checkpoint=checkpoint)
    assert ablated["evaluation"]["episodes"] == 1
    with pytest.raises(ValueError, match="evaluation-only"):
        run_control(config, "zero", 42, 1, 1,
                    simulation=_SyntheticSimulation(), checkpoint=checkpoint)
    with pytest.raises(ValueError, match="exploration"):
        run_control(config, "trainable", 42, 0, 1,
                    simulation=_SyntheticSimulation(), checkpoint=checkpoint,
                    exploration=0.7)


@pytest.mark.brain
def test_real_connectome_arena_one_episode():
    from flybg3.brain.simulation import Simulation
    from flybg3.config import Config
    import numpy as np
    config = Config()
    config.encoder.health_stress_gain = 0.4
    config.encoder.proximity_gain = 0.6
    simulation = Simulation(config)
    before = np.asarray(simulation.brain.brain.weights).copy()
    policy = TrainableNeuralReadoutPolicy(seed=42)
    episode = EpisodeRunner(simulation, policy, RewardEngine()).run(
        CombatArena(42, max_turns=2), 1, training=True)
    assert episode.turn_count >= 1
    assert episode.transitions[0]["features"]["DNa02_L"] >= 0
    assert policy.updates == episode.turn_count
    np.testing.assert_array_equal(before, simulation.brain.brain.weights)
