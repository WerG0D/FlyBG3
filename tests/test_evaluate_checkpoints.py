from __future__ import annotations

import json
from pathlib import Path

import pytest

from flybg3.combat.model import FEATURE_NAMES
from flybg3.combat.policy_gradient import PolicyGradientReadoutPolicy
from tools import evaluate_checkpoints


class _NeuralTestDouble:
    """Only the holdout orchestration test uses this; real runs use MaleCNS."""

    def reset(self):
        pass

    def decide(self, observation):
        rates = {name: 0.0 for name in FEATURE_NAMES}
        rates["DNp01_L"] = observation["nearest_hostile"]["distance"]
        return None, {"neural_activity": {"rates_hz": rates, "spikes": {}},
                      "stimulus": {}, "timings": {"simulation_ms": 0.0}}


def test_paired_holdout_uses_same_arenas_and_keeps_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate_checkpoints, "Simulation", lambda _config: _NeuralTestDouble())
    before = PolicyGradientReadoutPolicy(seed=42)
    after = PolicyGradientReadoutPolicy(seed=42)
    after.episodes = 40
    first, second = tmp_path / "before.json", tmp_path / "after.json"
    before.save(first, {})
    after.save(second, {})
    original = (first.read_bytes(), second.read_bytes())
    output = tmp_path / "holdout.json"
    report = evaluate_checkpoints.evaluate(
        Path("config/combat-reinforce.toml"), (first, second),
        opponent="C", seed=42, first_episode=1001, episodes=2, output=output)
    assert output.exists() and json.loads(output.read_text()) == report
    assert [row["trained_episodes"] for row in report["checkpoints"]] == [0, 40]
    assert all([e["episode_id"] for e in row["episodes"]] == [1001, 1002]
               for row in report["checkpoints"])
    assert (first.read_bytes(), second.read_bytes()) == original
    with pytest.raises(ValueError, match="distinct"):
        evaluate_checkpoints.evaluate(
            Path("config/combat-reinforce.toml"), (first, first),
            opponent="C", seed=42, first_episode=1001, episodes=2,
            output=tmp_path / "never.json")
