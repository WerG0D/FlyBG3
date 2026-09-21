from uuid import uuid4
import pytest


@pytest.fixture
def observation():
    return {"schema_version": 1, "session_id": str(uuid4()), "request_id": 1, "sample_time_ms": 1000,
            "npc": {"uuid": str(uuid4()), "hp": 40, "max_hp": 50, "position": {"x": 0, "y": 0, "z": 0}},
            "combat": {"active": False, "my_turn": False},
            "nearest_hostile": {"uuid": str(uuid4()), "distance": 8., "relative_angle": -75., "visible": True},
            "stimuli": {"damage_fraction": 0.0}}
