"""Small auditable neural readouts; no policy method accepts game observations."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Protocol

from .model import CombatAction, FEATURE_NAMES, NeuralFeatures

ACTIONS = tuple(CombatAction)
WIDTH = len(FEATURE_NAMES) + 1


@dataclass(frozen=True)
class PolicyDecision:
    action: CombatAction
    exploratory: bool
    epsilon: float
    values: dict[str, float]


class CombatLearner(Protocol):
    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision: ...
    def observe_transition(self, features: NeuralFeatures, action: CombatAction, reward: float,
                           next_features: NeuralFeatures | None, *, training: bool) -> None: ...
    def end_episode(self, *, training: bool) -> None: ...
    def save(self, path: Path, metadata: dict) -> None: ...


class TrainableNeuralReadoutPolicy:
    """Linear Q readout with one-step TD and seeded epsilon-greedy exploration.

    The MaleCNS weights are never referenced or mutated here. Only this matrix
    changes, after the corresponding action has produced a measured outcome.
    """

    def __init__(self, seed: int = 42, learning_rate: float = 0.05, discount: float = 0.9,
                 epsilon: float = 0.2, epsilon_decay: float = 0.995, epsilon_floor: float = 0.02):
        if not 0 < learning_rate <= 1 or not 0 <= discount <= 1:
            raise ValueError("invalid learning parameters")
        if not 0 <= epsilon_floor <= epsilon <= 1 or not 0 < epsilon_decay <= 1:
            raise ValueError("invalid exploration parameters")
        self.seed = seed
        self.rng = random.Random(seed)
        self.learning_rate, self.discount = learning_rate, discount
        self.epsilon, self.epsilon_decay, self.epsilon_floor = epsilon, epsilon_decay, epsilon_floor
        # Small seeded weights break deterministic tie bias without introducing
        # an explicit world-state heuristic or a special attack preference.
        self.weights = [[self.rng.uniform(-0.01, 0.01) for _ in range(WIDTH)] for _ in ACTIONS]
        self.updates = 0
        self.episodes = 0

    def values(self, features: NeuralFeatures) -> list[float]:
        vector = features.vector()
        return [sum(w * x for w, x in zip(row, vector)) for row in self.weights]

    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision:
        values = self.values(features)
        exploration = bool(training and self.rng.random() < self.epsilon)
        index = self.rng.randrange(len(ACTIONS)) if exploration else max(range(len(ACTIONS)), key=values.__getitem__)
        return PolicyDecision(ACTIONS[index], exploration, self.epsilon if training else 0.0,
                              dict(zip((a.value for a in ACTIONS), values)))

    def observe_transition(self, features: NeuralFeatures, action: CombatAction, reward: float,
                           next_features: NeuralFeatures | None, *, training: bool) -> None:
        if not training:
            return
        index = ACTIONS.index(action)
        current = self.values(features)[index]
        target = reward + (self.discount * max(self.values(next_features)) if next_features else 0.0)
        error = max(-10.0, min(10.0, target - current))
        vector = features.vector()
        self.weights[index] = [max(-20.0, min(20.0, w + self.learning_rate * error * x))
                               for w, x in zip(self.weights[index], vector)]
        self.updates += 1

    def end_episode(self, *, training: bool) -> None:
        if training:
            self.episodes += 1
            self.epsilon = max(self.epsilon_floor, self.epsilon * self.epsilon_decay)

    def save(self, path: Path, metadata: dict) -> None:
        from flybg3.bridge.atomic_io import atomic_write_json
        if path.exists():
            raise FileExistsError(path)
        atomic_write_json(path, {"schema_version": 1, "algorithm": "linear_q_td", "seed": self.seed,
                                 "feature_names": FEATURE_NAMES, "actions": [a.value for a in ACTIONS],
                                 "weights": self.weights, "updates": self.updates, "episodes": self.episodes,
                                 "epsilon": self.epsilon, "metadata": metadata})

    @classmethod
    def load(cls, path: Path) -> TrainableNeuralReadoutPolicy:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("schema_version") != 1 or data.get("algorithm") != "linear_q_td"
                or tuple(data.get("feature_names", ())) != FEATURE_NAMES
                or data.get("actions") != [a.value for a in ACTIONS]):
            raise ValueError("incompatible policy checkpoint")
        policy = cls(seed=data["seed"])
        weights = data["weights"]
        if len(weights) != len(ACTIONS) or any(len(row) != WIDTH for row in weights):
            raise ValueError("invalid checkpoint matrix")
        policy.weights = [[float(w) for w in row] for row in weights]
        policy.updates, policy.episodes, policy.epsilon = data["updates"], data["episodes"], data["epsilon"]
        return policy


class FrozenPolicy(TrainableNeuralReadoutPolicy):
    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision:
        return super().select_action(features, training=False)

    def observe_transition(self, features: NeuralFeatures, action: CombatAction, reward: float,
                           next_features: NeuralFeatures | None, *, training: bool) -> None:
        return None

    def end_episode(self, *, training: bool) -> None:
        return None


class RandomPolicy:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision:
        return PolicyDecision(self.rng.choice(ACTIONS), True, 1.0, {})

    def observe_transition(self, features: NeuralFeatures, action: CombatAction, reward: float,
                           next_features: NeuralFeatures | None, *, training: bool) -> None:
        return None

    def end_episode(self, *, training: bool) -> None:
        return None

    def save(self, path: Path, metadata: dict) -> None:
        raise TypeError("random control has no trainable checkpoint")
