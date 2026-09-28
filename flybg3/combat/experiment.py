"""Reproducible real-MaleCNS arena runs and honest baseline comparisons."""
from __future__ import annotations

from dataclasses import asdict
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time
from uuid import uuid4

from flybg3.brain.simulation import Simulation
from flybg3.bridge.atomic_io import atomic_write_json
from flybg3.bridge.atomic_io import read_json
from flybg3.config import Config

from .arena import CombatArena
from .policy import FrozenPolicy, RandomPolicy, TrainableNeuralReadoutPolicy
from .policy_gradient import FrozenPolicyGradient, PolicyGradientReadoutPolicy
from .reward import RewardEngine
from .runner import EpisodeRunner


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def manifest(config: Config, seed: int, policy: str, brain_info: dict) -> dict:
    raw = json.dumps(asdict(config), sort_keys=True, default=str).encode()
    project_root = Path(__file__).resolve().parents[2]
    source_files = ("flybg3/brain/encoder.py", "flybg3/brain/fly_brain.py",
                    "flybg3/brain/simulation.py", "flybg3/combat/arena.py",
                    "flybg3/combat/features.py", "flybg3/combat/policy.py",
                    "flybg3/combat/policy_gradient.py",
                    "flybg3/combat/reward.py", "flybg3/combat/runner.py",
                    "flybg3/combat/experiment.py", "flybg3/telemetry/connectome.py")
    source_hashes = {name: hashlib.sha256((project_root / name).read_bytes()).hexdigest()
                     for name in source_files}
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": seed, "policy": policy, "python": platform.python_version(),
            "flybrain": importlib.metadata.version("flybrain"), "dataset": "MaleCNS v1.0",
            "brain": brain_info, "git_sha": _git("rev-parse", "HEAD"),
            "git_branch": _git("branch", "--show-current"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "source_sha256": source_hashes,
            "config_sha256": hashlib.sha256(raw).hexdigest(), "config": asdict(config),
            "policy_version": ("linear_softmax_reinforce_v1" if config.combat.algorithm == "reinforce"
                               else "linear_q_td_v1"), "reward": asdict(config.reward)}


class RunStore:
    def __init__(self, root: Path, manifest_data: dict):
        self.root = root
        self.root.parent.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=False)
        (root / "checkpoints").mkdir()
        atomic_write_json(root / "manifest.json", manifest_data)
        self.last_control_token = None
        self.paused = False
        self.pending_checkpoint = False

    def event(self, event: dict) -> None:
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n")

    def episode(self, episode) -> None:
        with (self.root / "episodes.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(asdict(episode), allow_nan=False, separators=(",", ":")) + "\n")

    def before_decision(self, policy, episode_id: int, request_id: int) -> str | None:
        while True:
            command = read_json(self.root / "control.json")
            if command and command.get("schema_version") == 1 and command.get("token") != self.last_control_token:
                self.last_control_token = command.get("token")
                kind = command.get("command")
                if kind == "pause":
                    self.paused = True
                elif kind == "resume":
                    self.paused = False
                elif kind == "reset_episode":
                    self.event({"schema_version": 1, "event": "system_status", "episode_id": episode_id,
                                "request_id": request_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                                "payload": {"status": "episode_reset_requested"}})
                    return "reset_episode"
                elif kind == "checkpoint" and isinstance(policy, (TrainableNeuralReadoutPolicy,
                                                                  PolicyGradientReadoutPolicy)):
                    if isinstance(policy, PolicyGradientReadoutPolicy):
                        self.pending_checkpoint = True
                    else:
                        checkpoint = self.root / "checkpoints" / f"policy_manual_{uuid4().hex[:8]}.json"
                        policy.save(checkpoint, {"episode": episode_id, "run_manifest": "../manifest.json"})
                        self.event({"schema_version": 1, "event": "checkpoint", "episode_id": episode_id,
                                    "request_id": request_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "payload": {"path": str(checkpoint)}})
                self.event({"schema_version": 1, "event": "system_status", "episode_id": episode_id,
                            "request_id": request_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                            "payload": {"status": "paused" if self.paused else "running", "command": kind}})
            if not self.paused:
                return None
            time.sleep(0.1)


def make_policy(name: str, seed: int, config: Config):
    c = config.combat
    if name == "random":
        return RandomPolicy(seed)
    if c.algorithm == "reinforce":
        kwargs = dict(seed=seed, learning_rate=c.learning_rate, discount=c.discount,
                      temperature=c.reinforce_temperature,
                      return_scale=c.reinforce_return_scale,
                      gradient_clip=c.reinforce_gradient_clip)
        if name == "frozen":
            return FrozenPolicyGradient(**kwargs)
        if name == "trainable":
            return PolicyGradientReadoutPolicy(**kwargs)
        raise ValueError(f"unknown policy {name}")
    kwargs = dict(seed=seed, learning_rate=c.learning_rate, discount=c.discount,
                  epsilon=c.epsilon, epsilon_decay=c.epsilon_decay, epsilon_floor=c.epsilon_floor)
    if name == "frozen":
        return FrozenPolicy(**kwargs)
    if name == "trainable":
        return TrainableNeuralReadoutPolicy(**kwargs)
    raise ValueError(f"unknown policy {name}")


def load_policy(path: Path):
    algorithm = json.loads(path.read_text(encoding="utf-8")).get("algorithm")
    if algorithm == PolicyGradientReadoutPolicy.algorithm:
        return PolicyGradientReadoutPolicy.load(path)
    if algorithm == "linear_q_td":
        return TrainableNeuralReadoutPolicy.load(path)
    raise ValueError("unknown checkpoint algorithm")


def summarize(episodes: list) -> dict:
    wins = sum(e.result == "victory" for e in episodes)
    losses = sum(e.result == "defeat" for e in episodes)
    n = len(episodes)
    rewards = [e.total_reward for e in episodes]
    actions = [step["action"] for e in episodes for step in e.transitions]
    choices = [step for e in episodes for step in e.transitions]
    switches = sum(a != b for e in episodes for a, b in zip(e.actions, e.actions[1:]))
    return {"episodes": n, "wins": wins, "losses": losses, "win_rate": wins / n if n else 0,
            "rolling_win_rate_20": sum(e.result == "victory" for e in episodes[-20:]) / min(n, 20) if n else 0,
            "rolling_reward_20": sum(rewards[-20:]) / min(n, 20) if n else 0,
            "mean_reward": sum(rewards) / n if n else 0,
            "mean_turns": sum(e.turn_count for e in episodes) / n if n else 0,
            "mean_turns_to_win": sum(e.turn_count for e in episodes if e.result == "victory") / wins if wins else None,
            "action_counts": dict(Counter(actions)), "action_switches": switches,
            "exploration_rate": sum(bool(step["explore"]) for step in choices) / len(choices) if choices else 0,
            "mean_damage_dealt": sum(e.damage_dealt for e in episodes) / n if n else 0,
            "mean_damage_received": sum(e.damage_received for e in episodes) / n if n else 0,
            "mean_brain_ms": sum(t["brain_ms"] for e in episodes for t in e.transitions)
                             / max(1, sum(e.turn_count for e in episodes)),
            "mean_policy_ms": sum(t["policy_ms"] for e in episodes for t in e.transitions)
                              / max(1, sum(e.turn_count for e in episodes))}


def run_control(config: Config, name: str, seed: int, train_episodes: int, eval_episodes: int,
                *, root: Path | None = None, simulation=None,
                checkpoint: Path | None = None, opponent: str = "A",
                exploration: float | None = None) -> dict:
    if train_episodes < 0 or eval_episodes < 1:
        raise ValueError("need at least one evaluation episode")
    if opponent not in {"A", "B", "C", "D"}:
        raise ValueError("unknown arena opponent")
    config.brain.seed = seed
    simulation = simulation or Simulation(config)
    policy_name = "trainable" if name in {"trainable", "shuffled", "zero"} else name
    if checkpoint is not None and (name not in {"trainable", "shuffled", "zero"}
                                   or (name != "trainable" and train_episodes)):
        raise ValueError("checkpoint ablations require evaluation-only mode")
    policy = (load_policy(checkpoint) if checkpoint is not None
              else make_policy(policy_name, seed, config))
    if checkpoint is not None and (isinstance(policy, PolicyGradientReadoutPolicy)
                                   != (config.combat.algorithm == "reinforce")):
        raise ValueError("checkpoint algorithm differs from config.combat.algorithm")
    if checkpoint is not None and policy.seed != seed:
        raise ValueError("checkpoint seed differs from requested seed")
    if exploration is not None:
        if (name != "trainable" or train_episodes < 1
                or not isinstance(policy, TrainableNeuralReadoutPolicy)
                or not policy.epsilon_floor <= exploration <= 1):
            raise ValueError("exploration override requires trainable training run and valid epsilon")
        policy.epsilon = exploration
    episode_offset = policy.episodes if checkpoint is not None else 0
    control = name if name in {"shuffled", "zero"} else "normal"
    store = None
    if root is not None:
        run_manifest = manifest(config, seed, name, simulation.brain.info())
        run_manifest["opponent"] = opponent
        if exploration is not None:
            run_manifest["exploration_override"] = exploration
        if checkpoint is not None:
            checkpoint_data = json.loads(checkpoint.read_text(encoding="utf-8"))
            run_manifest["parent_checkpoint"] = {
                "path": str(checkpoint),
                "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "episodes_completed": episode_offset,
                "rng_state_restored": "rng_state" in checkpoint_data,
            }
        store = RunStore(root, run_manifest)
    runner = EpisodeRunner(simulation, policy, RewardEngine(config.reward),
                           control=control, sink=store.event if store else None,
                           before_decision=(lambda episode_id, request_id: store.before_decision(
                               policy, episode_id, request_id)) if store else None)
    training, evaluation = [], []
    for i in range(episode_offset + 1, episode_offset + train_episodes + eval_episodes + 1):
        arena = CombatArena(seed * 100000 + i, max_turns=config.combat.max_turns,
                            opponent=opponent)
        is_train = i <= episode_offset + train_episodes
        learn = is_train and policy_name == "trainable"
        episode = runner.run(arena, i, training=learn, feature_seed=seed)
        (training if is_train else evaluation).append(episode)
        if store:
            store.episode(episode)
            if store.pending_checkpoint:
                deferred_checkpoint = store.root / "checkpoints" / f"policy_manual_{uuid4().hex[:8]}.json"
                policy.save(deferred_checkpoint,
                            {"episode": i, "run_manifest": "../manifest.json", "deferred": True})
                store.event({"schema_version": 1, "event": "checkpoint", "episode_id": i,
                             "request_id": episode.turn_count,
                             "timestamp": datetime.now(timezone.utc).isoformat(),
                             "payload": {"path": str(deferred_checkpoint)}})
                store.pending_checkpoint = False
            seen = training if is_train else evaluation
            store.event({"schema_version": 1, "event": "training_metrics", "episode_id": i,
                         "request_id": episode.turn_count, "timestamp": datetime.now(timezone.utc).isoformat(),
                         "payload": {"phase": ("train" if learn else "control") if is_train else "eval",
                                     "policy": name, "epsilon": getattr(policy, "epsilon", 0.0) if learn else 0.0,
                                     "summary": summarize(seen),
                                     "reward_series": [e.total_reward for e in seen],
                                     "win_series": [int(e.result == "victory") for e in seen]}})
            if policy_name == "trainable" and learn and i % 10 == 0:
                periodic_checkpoint = store.root / "checkpoints" / f"policy_episode_{i:04d}.json"
                policy.save(periodic_checkpoint,
                            {"episode": i, "run_manifest": "../manifest.json"})
                store.event({"schema_version": 1, "event": "checkpoint", "episode_id": i,
                             "request_id": episode.turn_count,
                             "timestamp": datetime.now(timezone.utc).isoformat(),
                             "payload": {"path": str(periodic_checkpoint)}})
    if store:
        if policy_name == "trainable" and train_episodes:
            policy.save(store.root / "checkpoints" / f"policy_final_{uuid4().hex[:8]}.json",
                        {"episode": episode_offset + train_episodes, "run_manifest": "../manifest.json"})
        atomic_write_json(store.root / "metrics.json",
                          {"training": summarize(training), "evaluation": summarize(evaluation)})
    return {"name": name, "seed": seed, "opponent": opponent, "training": summarize(training),
            "evaluation": summarize(evaluation), "run_directory": str(root) if root else None,
            "parent_checkpoint": str(checkpoint) if checkpoint else None}


def validate_learning(config: Config, seeds: tuple[int, ...], train_episodes: int,
                      eval_episodes: int, output: Path, *, runs_root: Path | None = None) -> dict:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique and nonempty")
    results = []
    for seed in seeds:
        config.brain.seed = seed
        simulation = Simulation(config)
        for name in ("random", "frozen", "trainable", "shuffled", "zero"):
            root = None
            if runs_root:
                root = runs_root / f"run_{datetime.now():%Y%m%d_%H%M%S}_{seed}_{name}_{uuid4().hex[:6]}"
            results.append(run_control(config, name, seed, train_episodes, eval_episodes,
                                       root=root, simulation=simulation))
    by_name = {name: [r for r in results if r["name"] == name]
               for name in ("random", "frozen", "trainable", "shuffled", "zero")}
    means = {name: {"mean_eval_win_rate": sum(r["evaluation"]["win_rate"] for r in rows) / len(rows),
                    "mean_eval_reward": sum(r["evaluation"]["mean_reward"] for r in rows) / len(rows)}
             for name, rows in by_name.items()}
    conclusion = "INCONCLUSIVE"
    result = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
              "dataset": "MaleCNS v1.0", "seeds": seeds, "train_episodes_per_seed": train_episodes,
              "eval_episodes_per_seed": eval_episodes, "controls": results,
              "summary": means, "conclusion": conclusion,
              "note": "Synthetic arena only; no BG3 combat learning claim."}
    atomic_write_json(output, result)
    return result


def evaluate_generalization(config: Config, validation_path: Path, episodes_per_seed: int,
                            output: Path) -> dict:
    if episodes_per_seed < 1:
        raise ValueError("episodes_per_seed must be positive")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    runs = [row for row in validation["controls"] if row["name"] == "trainable"]
    results = []
    for row in runs:
        seed = int(row["seed"])
        run_directory = Path(row["run_directory"])
        checkpoints = list((run_directory / "checkpoints").glob("policy_final_*.json"))
        if len(checkpoints) != 1:
            raise RuntimeError(f"expected exactly one final checkpoint: {run_directory}")
        checkpoint = checkpoints[0]
        frozen = load_policy(checkpoint)
        before_weights = [weights[:] for weights in frozen.weights]
        config.brain.seed = seed
        runner = EpisodeRunner(Simulation(config), frozen, RewardEngine(config.reward))
        for opponent in ("B", "C"):
            episodes = [runner.run(CombatArena(seed * 100000 + 100 + i,
                                              max_turns=config.combat.max_turns, opponent=opponent),
                                   100 + i, training=False, feature_seed=seed)
                        for i in range(episodes_per_seed)]
            if frozen.weights != before_weights:
                raise RuntimeError("EVAL updated checkpoint weights")
            results.append({"seed": seed, "trained_enemy": "A", "evaluation_enemy": opponent,
                            "policy_checkpoint": str(checkpoint),
                            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                            "metrics": summarize(episodes),
                            "episodes": [{"result": e.result, "reward": e.total_reward,
                                          "turns": e.turn_count, "actions": e.actions} for e in episodes]})
    result = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
              "dataset": "MaleCNS v1.0", "comparison": "A checkpoint frozen on synthetic opponents B and C",
              "results": results, "conclusion": "INCONCLUSIVE",
              "note": "Small synthetic holdout; no BG3 generalization claim."}
    atomic_write_json(output, result)
    return result
