from __future__ import annotations

import json
import inspect

import pytest

from flybg3.combat.arena import CombatArena
from flybg3.combat.experiment import run_control
from flybg3.combat.model import CombatAction, FEATURE_NAMES, NeuralFeatures
from flybg3.combat.policy import ACTIONS
from flybg3.combat.policy_gradient import PolicyGradientReadoutPolicy
from flybg3.combat.reward import RewardEngine
from flybg3.combat.runner import EpisodeRunner
from flybg3.config import Config


def neural(*, far: bool) -> NeuralFeatures:
    rates = [0.0] * len(FEATURE_NAMES)
    rates[FEATURE_NAMES.index("DNp01_L")] = 50.0 if far else 0.0
    return NeuralFeatures(tuple(rates))


def test_policy_gradient_boundary_accepts_neural_features_only():
    parameters = inspect.signature(PolicyGradientReadoutPolicy.select_action).parameters
    assert "features" in parameters
    assert not {"observation", "distance", "hp", "angle", "enemy"} & set(parameters)


def test_delayed_reward_reaches_earlier_neural_action():
    policy = PolicyGradientReadoutPolicy(seed=7, learning_rate=0.2, discount=0.98)
    policy.weights = [[0.0] * len(neural(far=True).vector()) for _ in ACTIONS]
    far, close = neural(far=True), neural(far=False)
    before = [row[:] for row in policy.weights]
    policy.observe_transition(far, CombatAction.APPROACH, 0.0, close, training=True)
    policy.observe_transition(close, CombatAction.BASIC_ATTACK, 4.0, None, training=True)
    assert policy.weights == before
    policy.end_episode(training=True)
    feature = 1 + FEATURE_NAMES.index("DNp01_L")
    assert policy.weights[ACTIONS.index(CombatAction.APPROACH)][feature] > 0
    assert policy.weights[ACTIONS.index(CombatAction.BASIC_ATTACK)][0] > 0
    assert policy.updates == policy.episodes == 1
    assert not policy.trajectory


def test_negative_return_and_baseline_are_episode_boundaries():
    policy = PolicyGradientReadoutPolicy(seed=3)
    policy.weights = [[0.0] * len(neural(far=False).vector()) for _ in ACTIONS]
    features = neural(far=False)
    policy.observe_transition(features, CombatAction.IDLE, -4.0, None, training=True)
    policy.end_episode(training=True)
    assert policy.weights[ACTIONS.index(CombatAction.IDLE)][0] < 0
    assert policy.baselines == [-4.0] and policy.baseline_counts == [1]
    before = [row[:] for row in policy.weights]
    policy.observe_transition(features, CombatAction.IDLE, -4.0, None, training=True)
    policy.end_episode(training=True)
    assert policy.weights == before
    policy.observe_transition(features, CombatAction.IDLE, 10.0, None, training=False)
    policy.end_episode(training=False)
    assert policy.weights == before and policy.episodes == 2


def test_seeded_softmax_checkpoint_and_eval_are_reproducible(tmp_path):
    a = PolicyGradientReadoutPolicy(seed=19)
    b = PolicyGradientReadoutPolicy(seed=19)
    features = neural(far=True)
    assert [a.select_action(features, training=True).action for _ in range(8)] == [
        b.select_action(features, training=True).action for _ in range(8)]
    checkpoint = tmp_path / "policy.json"
    a.save(checkpoint, {"source": "test"})
    loaded = PolicyGradientReadoutPolicy.load(checkpoint)
    assert loaded.select_action(features, training=True) == a.select_action(features, training=True)
    before = [row[:] for row in loaded.weights]
    choice = loaded.select_action(features, training=False)
    assert choice.epsilon == 0 and choice.exploratory is False
    loaded.observe_transition(features, choice.action, 4.0, None, training=False)
    loaded.end_episode(training=False)
    assert loaded.weights == before
    with pytest.raises(FileExistsError):
        a.save(checkpoint, {})
    data = json.loads(checkpoint.read_text())
    data["algorithm"] = "wrong"
    checkpoint.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="incompatible"):
        PolicyGradientReadoutPolicy.load(checkpoint)


class _FakeSimulation:
    def __init__(self):
        self.brain = self
        self.calls = 0

    def info(self):
        return {"name": "test-double"}

    def reset(self):
        self.calls = 0

    def decide(self, observation):
        self.calls += 1
        rates = {name: 0.0 for name in FEATURE_NAMES}
        rates["DNp01_L"] = observation["nearest_hostile"]["distance"]
        return None, {"neural_activity": {"rates_hz": rates, "spikes": {}},
                      "stimulus": {}, "timings": {"simulation_ms": 1.0}}


class _ClearSignalSimulation(_FakeSimulation):
    """Algorithm sanity check, never substituted for MaleCNS evidence."""

    def decide(self, observation):
        self.calls += 1
        rates = {name: 0.0 for name in FEATURE_NAMES}
        rates["DNp01_L"] = 50.0 if observation["nearest_hostile"]["distance"] > 1.5 else 0.0
        return None, {"neural_activity": {"rates_hz": rates, "spikes": {}},
                      "stimulus": {}, "timings": {"simulation_ms": 1.0}}


def test_lab_runner_uses_episodic_policy_without_extra_brain_steps(tmp_path):
    config = Config()
    config.combat.algorithm = "reinforce"
    config.combat.max_turns = 3
    config.validate()
    simulation = _FakeSimulation()
    root = tmp_path / "run"
    result = run_control(config, "trainable", 42, 1, 1, root=root,
                         simulation=simulation, opponent="D")
    assert result["training"]["episodes"] == result["evaluation"]["episodes"] == 1
    checkpoint = next((root / "checkpoints").glob("policy_final_*.json"))
    loaded = PolicyGradientReadoutPolicy.load(checkpoint)
    assert loaded.episodes == loaded.updates == 1
    incompatible = Config()
    incompatible.combat.max_turns = 3
    with pytest.raises(ValueError, match="algorithm differs"):
        run_control(incompatible, "trainable", 42, 0, 1,
                    simulation=_FakeSimulation(), checkpoint=checkpoint)
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    assert sum(event["event"] == "neural_state" for event in events) == sum(
        episode["turn_count"] if "turn_count" in episode else len(episode["transitions"])
        for episode in (json.loads(line) for line in (root / "episodes.jsonl").read_text().splitlines()))
    assert json.loads((root / "manifest.json").read_text())["policy_version"] == "linear_softmax_reinforce_v1"


def test_policy_gradient_sanity_with_clear_synthetic_neural_signal():
    config = Config()
    config.combat.algorithm = "reinforce"
    config.combat.learning_rate = 0.15
    config.combat.discount = 0.98
    result = run_control(config, "trainable", 42, 120, 20,
                         simulation=_ClearSignalSimulation(), opponent="D")
    assert result["evaluation"]["win_rate"] >= 0.5


@pytest.mark.brain
def test_reinforce_episode_keeps_malecns_weights_fixed():
    import numpy as np
    from flybg3.brain.simulation import Simulation

    config = Config()
    config.combat.algorithm = "reinforce"
    config.combat.max_turns = 2
    simulation = Simulation(config)
    before = np.asarray(simulation.brain.brain.weights).copy()
    policy = PolicyGradientReadoutPolicy(seed=42)
    episode = EpisodeRunner(simulation, policy, RewardEngine()).run(
        CombatArena(42, max_turns=2, opponent="D"), 1, training=True)
    assert policy.updates == 1 and episode.turn_count >= 1
    np.testing.assert_array_equal(before, simulation.brain.brain.weights)
