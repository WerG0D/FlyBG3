from __future__ import annotations

import pytest

from flybg3.config import SpeechConfig
from flybg3.speech.decoder import SpeechDecoder
from flybg3.speech.model import SpeechIntent
from flybg3.speech.verbalizer import TemplateSpeechVerbalizer


BASE = {name: 0.0 for name in ("DNa02_L", "DNa02_R", "DNp01_L", "DNp01_R",
                               "DNg100_L", "DNg100_R", "MDN_L", "MDN_R")}


@pytest.mark.parametrize(("updates", "expected", "text"), [
    ({"DNa02_L": 8, "DNa02_R": 1}, SpeechIntent.LEFT, "Left."),
    ({"DNa02_L": 1, "DNa02_R": 8}, SpeechIntent.RIGHT, "Right."),
    ({"DNa02_L": 8, "DNa02_R": 1, "DNp01_L": 10}, SpeechIntent.DANGER_LEFT, "Danger. Left."),
    ({"DNa02_L": 1, "DNa02_R": 8, "DNp01_R": 10}, SpeechIntent.DANGER_RIGHT, "Danger. Right."),
    ({"DNp01_L": 10}, SpeechIntent.DANGER, "Danger."),
    ({"MDN_L": 12, "MDN_R": 12}, SpeechIntent.RETREAT, "Away."),
    ({"DNg100_L": 12, "DNg100_R": 12}, SpeechIntent.APPROACH, "Closer."),
    ({"DNa02_L": 5, "DNa02_R": 4.8}, SpeechIntent.SILENT, None),
    ({}, SpeechIntent.SILENT, None),
])
def test_neural_intents_only_from_rates(updates, expected, text):
    state = SpeechDecoder(SpeechConfig()).decode(42, BASE | updates)
    assert state.intent is expected
    assert TemplateSpeechVerbalizer().verbalize(state) == text
    assert state.request_id == 42
    assert set(state.neural_values) == set(BASE)


def test_confidence_urgency_and_low_escape():
    decoder = SpeechDecoder(SpeechConfig())
    left = decoder.decode(1, BASE | {"DNa02_L": 8, "DNa02_R": 1})
    assert left.confidence == pytest.approx(7 / 9)
    assert left.urgency == 0
    danger = decoder.decode(2, BASE | {"DNp01_R": 10})
    assert danger.urgency == danger.confidence == 0.5
    assert decoder.decode(3, BASE | {"DNp01_R": 4}).intent is SpeechIntent.SILENT
