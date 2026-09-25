from __future__ import annotations

from typing import Protocol

from .model import NeuralSpeechState, SpeechIntent


class SpeechVerbalizer(Protocol):
    def verbalize(self, state: NeuralSpeechState) -> str | None: ...


class TemplateSpeechVerbalizer:
    TEMPLATES = {
        SpeechIntent.SILENT: None,
        SpeechIntent.IDLE: "Quiet.",
        SpeechIntent.LEFT: "Left.",
        SpeechIntent.RIGHT: "Right.",
        SpeechIntent.DANGER: "Danger.",
        SpeechIntent.DANGER_LEFT: "Danger. Left.",
        SpeechIntent.DANGER_RIGHT: "Danger. Right.",
        SpeechIntent.RETREAT: "Away.",
        SpeechIntent.APPROACH: "Closer.",
    }

    def verbalize(self, state: NeuralSpeechState) -> str | None:
        return self.TEMPLATES[state.intent]
