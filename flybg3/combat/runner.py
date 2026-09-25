"""Closed loop: outcome precedes reward, next MaleCNS window precedes TD update."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import random
from time import perf_counter
from typing import Callable
from uuid import uuid5, NAMESPACE_URL

from .arena import CombatArena
from .features import NeuralFeatureExtractor
from .model import CombatEpisode, FEATURE_NAMES, NeuralFeatures
from .policy import CombatLearner
from .reward import RewardEngine


def _time() -> str:
    return datetime.now(timezone.utc).isoformat()


class EpisodeRunner:
    def __init__(self, simulation, policy: CombatLearner, reward: RewardEngine,
                 *, control: str = "normal", sink: Callable[[dict], None] | None = None):
        if control not in {"normal", "shuffled", "zero"}:
            raise ValueError("unknown neural control")
        self.simulation, self.policy, self.reward = simulation, policy, reward
        self.extractor = NeuralFeatureExtractor()
        self.control, self.sink = control, sink

    def _emit(self, event: str, episode_id: int, request_id: int, payload: dict) -> None:
        if self.sink is None:
            return
        try:
            self.sink({"schema_version": 1, "event": event, "episode_id": episode_id,
                       "request_id": request_id, "timestamp": _time(), "payload": payload})
        except Exception:
            # Visualization/log subscribers are passive; never change a decision.
            import logging
            logging.getLogger("FlyBG3").exception("Combat telemetry subscriber failed")

    def run(self, arena: CombatArena, episode_id: int, *, training: bool,
            feature_seed: int = 42) -> CombatEpisode:
        self.simulation.reset()
        session = str(uuid5(NAMESPACE_URL, f"flybg3-arena-{feature_seed}-{episode_id}"))
        episode = CombatEpisode(episode_id, _time())
        shuffle_rng = random.Random(feature_seed + episode_id)
        request_id = 1

        def evaluate() -> tuple[NeuralFeatures, dict]:
            nonlocal request_id
            observation = arena.observation(session, request_id)
            _, record = self.simulation.decide(observation)
            t = perf_counter()
            features = self.extractor.extract(record["neural_activity"])
            if self.control == "zero":
                features = NeuralFeatures((0.0,) * len(FEATURE_NAMES))
            elif self.control == "shuffled":
                values = list(features.rates_hz)
                shuffle_rng.shuffle(values)
                features = NeuralFeatures(tuple(values))
            feature_ms = (perf_counter() - t) * 1000
            self._emit("neural_state", episode_id, request_id,
                       {"features_hz": features.to_dict(), "brain_ms": record["timings"]["simulation_ms"],
                        "feature_ms": feature_ms, "stimulus": record["stimulus"],
                        "neural_spikes": record["neural_activity"]["spikes"],
                        "telemetry": record.get("telemetry")})
            self._emit("combat_state", episode_id, request_id,
                       {"npc_hp": observation["npc"]["hp"],
                        "enemy_hp": observation["nearest_hostile"]["hp"],
                        "distance": observation["nearest_hostile"]["distance"],
                        "my_turn": True, "source": "synthetic_arena"})
            return features, record

        features, record = evaluate()
        while True:
            t = perf_counter()
            proposed = self.policy.select_action(features, training=training)
            policy_ms = (perf_counter() - t) * 1000
            self._emit("policy_decision", episode_id, request_id,
                       {"action": proposed.action.value, "explore": proposed.exploratory,
                        "epsilon": proposed.epsilon, "values": proposed.values, "policy_ms": policy_ms})
            outcome, terminal, result = arena.step(proposed.action)
            self._emit("action_result", episode_id, request_id,
                       {"action": proposed.action.value, **asdict(outcome)})
            # The reward is only computed after the arena action has returned an outcome.
            breakdown = self.reward.calculate(outcome)
            self._emit("reward", episode_id, request_id, breakdown.to_dict())
            next_features = None
            if not terminal:
                request_id += 1
                next_features, next_record = evaluate()
            self.policy.observe_transition(features, proposed.action, breakdown.total,
                                           next_features, training=training)
            episode.add({"request_id": request_id if terminal else request_id - 1,
                         "features": features.to_dict(), "action": proposed.action.value,
                         "explore": proposed.exploratory, "epsilon": proposed.epsilon,
                         "outcome": asdict(outcome), "reward": breakdown.to_dict(),
                         "brain_ms": record["timings"]["simulation_ms"],
                         "policy_ms": policy_ms}, outcome, breakdown)
            if terminal:
                episode.end(result or "aborted", _time())
                self.policy.end_episode(training=training)
                self._emit("episode_end", episode_id, request_id,
                           {"result": episode.result, "total_reward": episode.total_reward,
                            "turns": episode.turn_count, "damage_dealt": episode.damage_dealt,
                            "damage_received": episode.damage_received,
                            "enemy_kills": episode.enemy_kills})
                return episode
            features, record = next_features, next_record
