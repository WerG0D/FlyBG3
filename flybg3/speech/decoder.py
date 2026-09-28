"""A parallel readout: accepts only firing rates, never game observations or actions."""
from __future__ import annotations

import math
from typing import Mapping

from flybg3.config import SpeechConfig
from .model import NeuralSpeechState, SpeechIntent


class SpeechDecoder:
    def __init__(self, config: SpeechConfig):
        self.config = config

    def decode(self, request_id: int, rates_hz: Mapping[str, float]) -> NeuralSpeechState:
        names = ("DNa02_L", "DNa02_R", "DNp01_L", "DNp01_R",
                 "DNg100_L", "DNg100_R", "MDN_L", "MDN_R")
        values = {}
        for name in names:
            value = rates_hz[name]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid neural rate: {name}")
            values[name] = float(value)
        left, right = values["DNa02_L"], values["DNa02_R"]
        escape = max(values["DNp01_L"], values["DNp01_R"])
        forward = (values["DNg100_L"] + values["DNg100_R"]) / 2
        backward = (values["MDN_L"] + values["MDN_R"]) / 2
        lateral_confidence = abs(left - right) / max(left + right, 1e-9)
        lateral_strong = (abs(left - right) >= self.config.min_activity_hz
                          and lateral_confidence >= self.config.min_confidence)
        urgency = min(1.0, escape / self.config.urgency_scale_hz)
        source: tuple[str, ...] = ()
        confidence = 0.0
        intent = SpeechIntent.SILENT

        if escape >= self.config.escape_threshold_hz:
            confidence = urgency
            source = ("DNp01_L", "DNp01_R")
            if lateral_strong:
                intent = SpeechIntent.DANGER_LEFT if left > right else SpeechIntent.DANGER_RIGHT
                source += ("DNa02_L", "DNa02_R")
            else:
                intent = SpeechIntent.DANGER
        elif lateral_strong:
            intent = SpeechIntent.LEFT if left > right else SpeechIntent.RIGHT
            confidence = lateral_confidence
            source = ("DNa02_L", "DNa02_R")
        elif backward - forward >= self.config.min_activity_hz:
            intent = SpeechIntent.RETREAT
            confidence = min(1.0, (backward - forward) / self.config.urgency_scale_hz)
            source = ("MDN_L", "MDN_R", "DNg100_L", "DNg100_R")
        elif forward - backward >= self.config.min_activity_hz:
            intent = SpeechIntent.APPROACH
            confidence = min(1.0, (forward - backward) / self.config.urgency_scale_hz)
            source = ("DNg100_L", "DNg100_R", "MDN_L", "MDN_R")
        elif self.config.speak_idle and max(values.values()) < self.config.min_activity_hz:
            intent, confidence = SpeechIntent.IDLE, 1.0

        if confidence < self.config.min_confidence:
            intent, source = SpeechIntent.SILENT, ()
        return NeuralSpeechState(request_id, intent, confidence, urgency, source, values)
