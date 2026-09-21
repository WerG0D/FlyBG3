"""Strict wire validation. Session UUID prevents stale responses after reloads."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import StrEnum
import math
from uuid import UUID

SCHEMA_VERSION = 1
MAX_REQUEST_ID = 9007199254740991


class ProtocolError(ValueError):
    pass


class ActionType(StrEnum):
    IDLE = "idle"
    APPROACH = "approach"
    RETREAT = "retreat"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"


def uuid_string(value: object) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value.lower():
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as e:
        raise ProtocolError("Expected canonical UUID, not name or placeholder") from e
    return value


def number(value: object, name: str, low: float = -math.inf, high: float = math.inf) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ProtocolError(f"Invalid {name}")
    return value


def envelope(data: dict) -> None:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ProtocolError("Unsupported schema_version")
    uuid_string(data.get("session_id"))
    rid = data.get("request_id")
    if type(rid) is not int or not 1 <= rid <= MAX_REQUEST_ID:
        raise ProtocolError("Invalid request_id")


def validate_observation(data: dict) -> dict:
    try:
        envelope(data)
        number(data["sample_time_ms"], "sample_time_ms", 0)
        npc = data["npc"]
        uuid_string(npc["uuid"])
        number(npc["hp"], "hp", 0)
        number(npc["max_hp"], "max_hp", 1)
        for axis in ("x", "y", "z"):
            number(npc["position"][axis], axis)
        for key in ("active", "my_turn"):
            if type(data["combat"][key]) is not bool:
                raise ProtocolError(f"Invalid combat.{key}")
        target = data.get("nearest_hostile")
        if target is not None:
            uuid_string(target["uuid"])
            number(target["distance"], "distance", 0)
            number(target["relative_angle"], "relative_angle", -180, 180)
            if type(target["visible"]) is not bool:
                raise ProtocolError("Invalid visible")
            if target.get("closing_speed") is not None:
                number(target["closing_speed"], "closing_speed")
        if "stimuli" in data:
            number(data["stimuli"].get("damage_fraction", 0), "damage_fraction", 0, 1)
    except (KeyError, TypeError, AttributeError) as e:
        raise ProtocolError(f"Malformed observation: {e}") from e
    return data


@dataclass(frozen=True)
class Action:
    session_id: str
    request_id: int
    npc_uuid: str
    action: ActionType = ActionType.IDLE
    confidence: float = 0.0
    target_uuid: str | None = None
    debug: dict = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def validate_action(data: dict) -> dict:
    try:
        envelope(data)
        uuid_string(data["npc_uuid"])
        ActionType(data["action"])
        number(data["confidence"], "confidence", 0, 1)
        if data.get("target_uuid") is not None:
            uuid_string(data["target_uuid"])
        if not isinstance(data.get("debug", {}), dict):
            raise ProtocolError("Invalid debug")
    except (KeyError, TypeError, ValueError) as e:
        raise ProtocolError(f"Malformed action: {e}") from e
    return data


def response_matches(action: dict, observation: dict) -> bool:
    try:
        validate_action(action)
        return (action["session_id"], action["request_id"], action["npc_uuid"].lower()) == (
            observation["session_id"], observation["request_id"], observation["npc"]["uuid"].lower())
    except (ProtocolError, KeyError):
        return False
