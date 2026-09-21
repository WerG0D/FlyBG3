import pytest
from flybg3.brain.decoder import MotorDecoder
from flybg3.brain.neuron_groups import MOTOR_TYPES
from flybg3.config import DecoderConfig


@pytest.mark.parametrize("group,expected", [("DNa02_L", "turn_left"), ("DNa02_R", "turn_right"),
                                            ("DNp01_L", "retreat"), ("DNg100_R", "approach"), ("MDN_R", "retreat")])
def test_neural_actions(group, expected):
    rates = {f"{t}_{s}": 0.0 for t in MOTOR_TYPES for s in "LR"}
    rates[group] = 20
    decision = MotorDecoder(DecoderConfig()).decode(rates)
    assert decision.action == expected
    assert 0 <= decision.confidence <= 1


def test_silence_and_decay():
    rates = {f"{t}_{s}": 0.0 for t in MOTOR_TYPES for s in "LR"}
    decoder = MotorDecoder(DecoderConfig())
    assert decoder.decode(rates).action == "idle"
    decoder.decode({**rates, "DNp01_R": 20})
    for _ in range(10):
        decision = decoder.decode(rates)
    assert decision.action == "idle"


def test_hysteresis_retains_neural_winner():
    rates = {f"{t}_{s}": 0.0 for t in MOTOR_TYPES for s in "LR"}
    decoder = MotorDecoder(DecoderConfig(smoothing=0, hysteresis=0.5))
    assert decoder.decode({**rates, "DNa02_L": 10}).action == "turn_left"
    assert decoder.decode({**rates, "DNa02_L": 10, "DNp01_R": 11}).action == "turn_left"
