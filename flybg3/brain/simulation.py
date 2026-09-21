"""Stateful pipeline with group-level audit records and timings."""
from __future__ import annotations

from dataclasses import asdict
from time import perf_counter
from flybg3.config import Config
from flybg3.bridge.protocol import Action
from .encoder import SensoryEncoder
from .decoder import MotorDecoder
from .fly_brain import FlyBrainAdapter


class Simulation:
    def __init__(self, config: Config):
        self.config = config
        self.brain = FlyBrainAdapter(config)
        self.encoder = SensoryEncoder(config.encoder)
        self.decoder = MotorDecoder(config.decoder)

    def reset(self) -> None:
        self.brain.reset()
        self.encoder.reset()
        self.decoder.reset()

    def decide(self, observation: dict) -> tuple[Action, dict]:
        t0 = perf_counter()
        stimulus = self.encoder.encode(observation)
        t1 = perf_counter()
        neural = self.brain.simulate(stimulus)
        t2 = perf_counter()
        decision = self.decoder.decode(neural["rates_hz"])
        t3 = perf_counter()
        timings = dict(zip(("encoder_ms", "simulation_ms", "decoder_ms", "total_ms"),
                           (1000 * (t1-t0), 1000 * (t2-t1), 1000 * (t3-t2), 1000 * (t3-t0))))
        action = Action(observation["session_id"], observation["request_id"], observation["npc"]["uuid"],
                        decision.action, decision.confidence,
                        (observation.get("nearest_hostile") or {}).get("uuid"),
                        {"scores": decision.scores, "timings": timings, "neural_activity": neural})
        return action, {"observation": observation, "stimulus": stimulus, "neural_activity": neural,
                        "scores": decision.scores, "action": action.to_dict(), "timings": timings,
                        "parameters": asdict(self.config)}
