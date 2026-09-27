"""Read-only combat-policy probe for real BG3 neural windows.

It sees only descending-neuron activity. It cannot issue BG3 actions, update a
policy, or call the brain simulator. The original movement decoder remains the
sole publisher of action.json.
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
import hashlib

from .experiment import load_policy
from .features import NeuralFeatureExtractor
from .policy_gradient import PolicyGradientReadoutPolicy


class CombatShadowProbe:
    def __init__(self, checkpoint: Path, *, algorithm: str, seed: int):
        self.policy = load_policy(checkpoint)
        if self.policy.seed != seed:
            raise ValueError("combat shadow checkpoint seed differs from brain seed")
        if (isinstance(self.policy, PolicyGradientReadoutPolicy)
                != (algorithm == "reinforce")):
            raise ValueError("combat shadow checkpoint algorithm differs from config")
        self.algorithm = algorithm
        self.checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.extractor = NeuralFeatureExtractor()

    def inspect(self, neural_activity: dict, *, session_id: str, request_id: int) -> dict:
        started = perf_counter()
        features = self.extractor.extract(neural_activity)
        before = self.policy.updates
        decision = self.policy.select_action(features, training=False)
        if self.policy.updates != before:
            raise RuntimeError("combat shadow readout updated during observation")
        return {
            "schema_version": 1,
            "session_id": session_id,
            "request_id": request_id,
            "mode": "observe_only",
            "algorithm": self.algorithm,
            "checkpoint_sha256": self.checkpoint_sha256,
            "candidate_action": decision.action.value,
            "features_hz": features.to_dict(),
            "values": decision.values,
            "readout_ms": (perf_counter() - started) * 1000,
        }
