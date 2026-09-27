"""Paired synthetic holdout for two frozen readout checkpoints.

MaleCNS runs normally. Each checkpoint sees the same arena seeds and episode
indices; neither policy nor connectome is updated during this evaluation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from flybg3.brain.simulation import Simulation
from flybg3.bridge.atomic_io import atomic_write_json
from flybg3.combat.arena import CombatArena
from flybg3.combat.experiment import load_policy, summarize
from flybg3.combat.policy_gradient import PolicyGradientReadoutPolicy
from flybg3.combat.reward import RewardEngine
from flybg3.combat.runner import EpisodeRunner
from flybg3.config import load_config


def evaluate(config_path: Path, checkpoints: tuple[Path, Path], *, opponent: str,
             seed: int, first_episode: int, episodes: int, output: Path) -> dict:
    if opponent not in {"A", "B", "C", "D"} or seed < 0 or first_episode < 1 or episodes < 1:
        raise ValueError("invalid holdout settings")
    if checkpoints[0].resolve() == checkpoints[1].resolve():
        raise ValueError("holdout needs two distinct checkpoints")
    config = load_config(config_path)
    config.brain.seed = seed
    rows = []
    for checkpoint in checkpoints:
        policy = load_policy(checkpoint)
        if policy.seed != seed:
            raise ValueError(f"checkpoint seed mismatch: {checkpoint}")
        if (isinstance(policy, PolicyGradientReadoutPolicy)
                != (config.combat.algorithm == "reinforce")):
            raise ValueError(f"checkpoint algorithm mismatch: {checkpoint}")
        before = [weights[:] for weights in policy.weights]
        before_episodes = policy.episodes
        runner = EpisodeRunner(Simulation(config), policy, RewardEngine(config.reward))
        evaluated = [
            runner.run(CombatArena(seed * 100000 + episode_id,
                                   max_turns=config.combat.max_turns, opponent=opponent),
                       episode_id, training=False, feature_seed=seed)
            for episode_id in range(first_episode, first_episode + episodes)
        ]
        if policy.weights != before or policy.episodes != before_episodes:
            raise RuntimeError("evaluation changed readout checkpoint state")
        resolved = checkpoint.resolve()
        try:
            display_path = str(resolved.relative_to(Path.cwd()))
        except ValueError:
            display_path = str(resolved)
        rows.append({
            "checkpoint": display_path,
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "trained_episodes": before_episodes,
            "metrics": summarize(evaluated),
            "episodes": [{"episode_id": e.episode_id, "result": e.result,
                          "reward": e.total_reward, "turns": e.turn_count,
                          "actions": e.actions} for e in evaluated],
        })
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "MaleCNS v1.0",
        "config_file_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "brain": {"simulation_steps": config.brain.simulation_steps,
                  "dt": config.brain.dt, "seed": config.brain.seed},
        "readout_algorithm": config.combat.algorithm,
        "reward": asdict(config.reward),
        "opponent": opponent,
        "seed": seed,
        "first_episode": first_episode,
        "episodes_per_checkpoint": episodes,
        "checkpoints": rows,
        "note": "Paired synthetic holdout only; no BG3 combat-learning claim.",
    }
    atomic_write_json(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/combat-reinforce.toml"))
    parser.add_argument("--opponent", choices=["A", "B", "C", "D"], default="C")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--first-episode", type=int, default=1001)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("experiments/policy_gradient_holdout.json"))
    args = parser.parse_args()
    report = evaluate(args.config, (args.before, args.after), opponent=args.opponent,
                      seed=args.seed, first_episode=args.first_episode,
                      episodes=args.episodes, output=args.output)
    for row in report["checkpoints"]:
        print(f"{row['trained_episodes']} training episodes: "
              f"{row['metrics']['wins']}/{row['metrics']['episodes']} wins; "
              f"mean reward {row['metrics']['mean_reward']:.3f}")
