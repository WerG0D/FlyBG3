"""Typed boundary: a combat policy can receive neural features, never BG3 state."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CombatAction(StrEnum):
    IDLE = "idle"
    APPROACH = "approach"
    RETREAT = "retreat"
    BASIC_ATTACK = "basic_attack"
    END_TURN = "end_turn"


FEATURE_NAMES = (
    "DNa02_L", "DNa02_R", "DNp01_L", "DNp01_R",
    "DNg100_L", "DNg100_R", "MDN_L", "MDN_R",
    "DNp02_L", "DNp02_R", "DNp11_L", "DNp11_R",
    "aSP22_L", "aSP22_R",
)


@dataclass(frozen=True)
class NeuralFeatures:
    rates_hz: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.rates_hz) != len(FEATURE_NAMES):
            raise ValueError("Neural feature count does not match MaleCNS readout")
        import math
        if any(not math.isfinite(x) or x < 0 for x in self.rates_hz):
            raise ValueError("Neural rates must be finite and nonnegative")

    def vector(self) -> tuple[float, ...]:
        return (1.0,) + tuple(min(x / 50.0, 1.0) for x in self.rates_hz)

    def to_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.rates_hz))


@dataclass(frozen=True)
class CombatOutcome:
    status: str
    reason: str = ""
    damage_dealt: float = 0.0
    damage_received: float = 0.0
    enemy_kill: bool = False
    self_death: bool = False
    victory: bool = False
    defeat: bool = False
    timeout: bool = False


@dataclass(frozen=True)
class RewardBreakdown:
    damage_dealt: float = 0.0
    damage_received: float = 0.0
    kill: float = 0.0
    death: float = 0.0
    victory: float = 0.0
    defeat: float = 0.0
    invalid: float = 0.0
    timeout: float = 0.0

    @property
    def total(self) -> float:
        return sum(vars(self).values())

    def to_dict(self) -> dict[str, float]:
        return {**vars(self), "total": self.total}


@dataclass
class CombatEpisode:
    episode_id: int
    started_at: str
    initial_state: dict = field(default_factory=dict)
    ended_at: str | None = None
    result: str | None = None
    transitions: list[dict] = field(default_factory=list)
    total_reward: float = 0.0
    damage_dealt: float = 0.0
    damage_received: float = 0.0
    enemy_kills: int = 0

    @property
    def turn_count(self) -> int:
        return len(self.transitions)

    @property
    def actions(self) -> list[str]:
        return [step["action"] for step in self.transitions]

    @property
    def rewards(self) -> list[float]:
        return [step["reward"]["total"] for step in self.transitions]

    def add(self, transition: dict, outcome: CombatOutcome, reward: RewardBreakdown) -> None:
        if self.ended_at is not None:
            raise RuntimeError("episode already ended")
        self.transitions.append(transition)
        self.total_reward += reward.total
        self.damage_dealt += outcome.damage_dealt
        self.damage_received += outcome.damage_received
        self.enemy_kills += int(outcome.enemy_kill)

    def end(self, result: str, at: str) -> None:
        if result not in {"victory", "defeat", "aborted", "timeout"} or self.ended_at:
            raise ValueError("invalid or repeated episode end")
        self.result, self.ended_at = result, at
