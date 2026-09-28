"""Episodic policy-gradient readout over frozen MaleCNS descending rates.

This is an external linear softmax policy, not plasticity in the connectome.
Only neural features and observed reward cross the learner boundary.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random

from flybg3.bridge.atomic_io import atomic_write_json

from .model import CombatAction, FEATURE_NAMES, NeuralFeatures
from .policy import ACTIONS, WIDTH, PolicyDecision


class PolicyGradientReadoutPolicy:
    """REINFORCE with discounted reward-to-go and a per-time-step baseline.

    Parameters are updated once per *completed training episode*. The baseline
    is action-independent and estimated from prior episodes at the same step
    index. Evaluation is deterministic argmax with no updates or sampling.
    """

    algorithm = "linear_softmax_reinforce"

    def __init__(self, seed: int = 42, learning_rate: float = 0.15,
                 discount: float = 0.98, temperature: float = 1.0,
                 return_scale: float = 4.0, gradient_clip: float = 10.0):
        if (not 0 < learning_rate <= 1 or not 0 <= discount <= 1
                or temperature <= 0 or return_scale <= 0 or gradient_clip <= 0):
            raise ValueError("invalid policy gradient parameters")
        self.seed = seed
        self.rng = random.Random(seed)
        self.learning_rate = learning_rate
        self.discount = discount
        self.temperature = temperature
        self.return_scale = return_scale
        self.gradient_clip = gradient_clip
        self.weights = [[self.rng.uniform(-0.01, 0.01) for _ in range(WIDTH)]
                        for _ in ACTIONS]
        self.baselines: list[float] = []
        self.baseline_counts: list[int] = []
        self.trajectory: list[tuple[tuple[float, ...], int, float]] = []
        self.updates = 0
        self.episodes = 0

    def logits(self, features: NeuralFeatures) -> list[float]:
        vector = features.vector()
        return [sum(w * x for w, x in zip(row, vector)) for row in self.weights]

    def _probabilities(self, vector: tuple[float, ...]) -> list[float]:
        logits = [sum(w * x for w, x in zip(row, vector)) / self.temperature
                  for row in self.weights]
        largest = max(logits)
        exponentials = [math.exp(value - largest) for value in logits]
        total = sum(exponentials)
        return [value / total for value in exponentials]

    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision:
        values = self.logits(features)
        greedy = max(range(len(ACTIONS)), key=values.__getitem__)
        if training:
            probabilities = self._probabilities(features.vector())
            draw = self.rng.random()
            cumulative = 0.0
            index = len(ACTIONS) - 1
            for candidate, probability in enumerate(probabilities):
                cumulative += probability
                if draw < cumulative:
                    index = candidate
                    break
        else:
            index = greedy
        return PolicyDecision(ACTIONS[index], training and index != greedy, 0.0,
                              dict(zip((action.value for action in ACTIONS), values)))

    def observe_transition(self, features: NeuralFeatures, action: CombatAction,
                           reward: float, next_features: NeuralFeatures | None,
                           *, training: bool) -> None:
        if training:
            if not math.isfinite(reward):
                raise ValueError("reward must be finite")
            self.trajectory.append((features.vector(), ACTIONS.index(action), reward))

    def end_episode(self, *, training: bool) -> None:
        if not training:
            self.trajectory.clear()
            return
        if not self.trajectory:
            raise ValueError("cannot learn from an empty episode")
        returns = [0.0] * len(self.trajectory)
        future = 0.0
        for index in range(len(self.trajectory) - 1, -1, -1):
            future = self.trajectory[index][2] + self.discount * future
            returns[index] = future
        gradient = [[0.0] * WIDTH for _ in ACTIONS]
        for t, ((vector, chosen, _), discounted_return) in enumerate(zip(self.trajectory, returns)):
            baseline = self.baselines[t] if t < len(self.baselines) else 0.0
            advantage = (discounted_return - baseline) / self.return_scale
            probabilities = self._probabilities(vector)
            for action_index, probability in enumerate(probabilities):
                factor = (advantage / self.temperature) * (
                    (1.0 if action_index == chosen else 0.0) - probability)
                for feature_index, feature_value in enumerate(vector):
                    gradient[action_index][feature_index] += factor * feature_value
        magnitude = math.sqrt(sum(value * value for row in gradient for value in row))
        multiplier = min(1.0, self.gradient_clip / magnitude) if magnitude else 1.0
        for action_index, row in enumerate(gradient):
            self.weights[action_index] = [max(-20.0, min(20.0, weight +
                                                self.learning_rate * multiplier * change))
                                          for weight, change in zip(self.weights[action_index], row)]
        for t, discounted_return in enumerate(returns):
            if t == len(self.baselines):
                self.baselines.append(0.0)
                self.baseline_counts.append(0)
            count = self.baseline_counts[t] + 1
            self.baselines[t] += (discounted_return - self.baselines[t]) / count
            self.baseline_counts[t] = count
        self.trajectory.clear()
        self.updates += 1
        self.episodes += 1

    def save(self, path: Path, metadata: dict) -> None:
        if path.exists():
            raise FileExistsError(path)
        if self.trajectory:
            raise RuntimeError("save only at an episode boundary")
        atomic_write_json(path, {
            "schema_version": 1, "algorithm": self.algorithm, "seed": self.seed,
            "feature_names": FEATURE_NAMES, "actions": [action.value for action in ACTIONS],
            "weights": self.weights, "updates": self.updates, "episodes": self.episodes,
            "baselines": self.baselines, "baseline_counts": self.baseline_counts,
            "learning_rate": self.learning_rate, "discount": self.discount,
            "temperature": self.temperature, "return_scale": self.return_scale,
            "gradient_clip": self.gradient_clip, "rng_state": self.rng.getstate(),
            "metadata": metadata,
        })

    @classmethod
    def load(cls, path: Path) -> PolicyGradientReadoutPolicy:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("schema_version") != 1 or data.get("algorithm") != cls.algorithm
                or tuple(data.get("feature_names", ())) != FEATURE_NAMES
                or data.get("actions") != [action.value for action in ACTIONS]):
            raise ValueError("incompatible policy-gradient checkpoint")
        policy = cls(seed=data["seed"], learning_rate=data["learning_rate"],
                     discount=data["discount"], temperature=data["temperature"],
                     return_scale=data["return_scale"], gradient_clip=data["gradient_clip"])
        weights = data["weights"]
        if (len(weights) != len(ACTIONS) or any(len(row) != WIDTH for row in weights)
                or any(not math.isfinite(value) for row in weights for value in row)):
            raise ValueError("invalid checkpoint matrix")
        baselines = data["baselines"]
        counts = data["baseline_counts"]
        if (len(baselines) != len(counts) or any(not math.isfinite(x) for x in baselines)
                or any(not isinstance(x, int) or x < 1 for x in counts)):
            raise ValueError("invalid checkpoint baseline")
        policy.weights = [[float(value) for value in row] for row in weights]
        policy.baselines = [float(value) for value in baselines]
        policy.baseline_counts = list(counts)
        policy.updates = int(data["updates"])
        policy.episodes = int(data["episodes"])

        def nested_tuple(value):
            return tuple(nested_tuple(part) for part in value) if isinstance(value, list) else value

        policy.rng.setstate(nested_tuple(data["rng_state"]))
        return policy


class FrozenPolicyGradient(PolicyGradientReadoutPolicy):
    """Seed-matched, untrained deterministic readout control."""

    def select_action(self, features: NeuralFeatures, *, training: bool) -> PolicyDecision:
        return super().select_action(features, training=False)

    def observe_transition(self, features: NeuralFeatures, action: CombatAction,
                           reward: float, next_features: NeuralFeatures | None,
                           *, training: bool) -> None:
        return None

    def end_episode(self, *, training: bool) -> None:
        return None
