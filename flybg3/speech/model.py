from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class SpeechIntent(StrEnum):
    SILENT = "silent"
    IDLE = "idle"
    LEFT = "left"
    RIGHT = "right"
    DANGER = "danger"
    DANGER_LEFT = "danger_left"
    DANGER_RIGHT = "danger_right"
    RETREAT = "retreat"
    APPROACH = "approach"


@dataclass(frozen=True)
class NeuralSpeechState:
    request_id: int
    intent: SpeechIntent
    confidence: float
    urgency: float
    source_groups: tuple[str, ...]
    neural_values: dict[str, float]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["intent"] = self.intent.value
        return result
