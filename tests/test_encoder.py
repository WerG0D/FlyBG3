from copy import deepcopy
import pytest
from flybg3.brain.encoder import SensoryEncoder
from flybg3.config import EncoderConfig


@pytest.mark.parametrize("angle,side", [(-60, "L"), (60, "R")])
def test_laterality(observation, angle, side):
    observation["nearest_hostile"].update(relative_angle=angle, closing_speed=1)
    s = SensoryEncoder(EncoderConfig()).encode(observation)
    opposite = "R" if side == "L" else "L"
    assert s[f"LPLC2_{side}"] > s[f"LPLC2_{opposite}"]


def test_growth(observation):
    encoder = SensoryEncoder(EncoderConfig())
    still = encoder.encode(observation)
    observation["sample_time_ms"] += 1000
    observation["nearest_hostile"]["distance"] = 4
    growing = encoder.encode(observation)
    assert growing["LPLC2_L"] > still["LPLC2_L"]


def test_target_switch_and_invisible_do_not_loom(observation):
    encoder = SensoryEncoder(EncoderConfig())
    encoder.encode(observation)
    from uuid import uuid4
    observation["nearest_hostile"].update(uuid=str(uuid4()), distance=1)
    observation["sample_time_ms"] += 1000
    assert encoder.encode(observation)["LPLC2_L"] == 0
    observation["nearest_hostile"]["visible"] = False
    assert not any(encoder.encode(observation).values())


def test_growth_strength_and_cap(observation):
    encoder = SensoryEncoder(EncoderConfig())
    observation["nearest_hostile"]["closing_speed"] = 0.1
    low = encoder.encode(observation)
    observation["nearest_hostile"]["closing_speed"] = 1
    high = encoder.encode(observation)
    assert high["LPLC2_L"] > low["LPLC2_L"]
    assert max(high.values()) <= encoder.config.cap


def test_damage_is_stimulus_only(observation):
    observation["nearest_hostile"] = None
    observation["stimuli"]["damage_fraction"] = 0.5
    s = SensoryEncoder(EncoderConfig()).encode(observation)
    assert s["LC4_L"] == s["LC4_R"] > 0
