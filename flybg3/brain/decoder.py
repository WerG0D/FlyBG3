"""Motor readout accepts descending firing rates ONLY, never observations."""
from __future__ import annotations

from dataclasses import dataclass
from flybg3.config import DecoderConfig
from flybg3.bridge.protocol import ActionType


@dataclass(frozen=True)
class Decision:
    action: ActionType
    confidence: float
    scores: dict[str, float]


class MotorDecoder:
    def __init__(self, config: DecoderConfig):
        self.config = config
        self.reset()

    def reset(self) -> None:
        self.smoothed: dict[str, float] = {}
        self.previous = ActionType.IDLE
        self.age = 0

    def decode(self, rates: dict[str, float]) -> Decision:
        c = self.config
        left, right = rates["DNa02_L"], rates["DNa02_R"]
        forward = (rates["DNg100_L"] + rates["DNg100_R"]) / 2
        backward = (rates["MDN_L"] + rates["MDN_R"]) / 2
        escape = max(rates["DNp01_L"], rates["DNp01_R"])
        raw = {"turn_left": max(0.0, left - right), "turn_right": max(0.0, right - left),
               "approach": max(0.0, forward - backward), "retreat": max(escape, backward)}
        scores = {k: c.smoothing * self.smoothed.get(k, 0.0) + (1 - c.smoothing) * v / c.rate_scale_hz
                  for k, v in raw.items()}
        self.smoothed = scores
        winner = max(scores, key=scores.get)
        action = ActionType(winner) if scores[winner] >= c.minimum_activity else ActionType.IDLE
        old_score = scores.get(self.previous.value, 0.0)
        if action != self.previous and old_score >= c.minimum_activity:
            if self.age < c.minimum_action_decisions or scores[winner] < old_score + c.hysteresis:
                action = self.previous
        self.age = self.age + 1 if action == self.previous else 1
        self.previous = action
        ordered = sorted(scores.values(), reverse=True)
        confidence = 0.0 if action == ActionType.IDLE else max(0.0, (scores[action.value] - ordered[1]) / max(ordered[0], 1e-9))
        return Decision(action, min(1.0, confidence), scores)
