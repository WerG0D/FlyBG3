"""Small 1v1 environment; its rules never enter CombatPolicy."""
from __future__ import annotations

from dataclasses import dataclass
import random
from uuid import UUID

from .model import CombatAction, CombatOutcome

NPC_UUID = "10000000-0000-4000-8000-000000000001"
ENEMY_UUID = "20000000-0000-4000-8000-000000000002"


@dataclass
class ArenaState:
    flyman_hp: int
    flyman_max_hp: int
    enemy_hp: int
    enemy_max_hp: int
    distance: float
    turn: int = 0
    previous_hp: int | None = None
    previous_distance: float | None = None


class CombatArena:
    """Synthetic environment for software/ablation tests, never BG3 evidence."""

    def __init__(self, seed: int, max_turns: int = 24, opponent: str = "A"):
        if opponent not in {"A", "B", "C", "D"}:
            raise ValueError("unknown arena opponent")
        self.rng = random.Random(seed)
        self.max_turns = max_turns
        self.opponent = opponent
        hp_range = (24, 30) if opponent == "B" else (6, 10) if opponent == "D" else (14, 20)
        distance_range = ((4.0, 8.0) if opponent == "B" else
                          (3.0, 7.0) if opponent == "C" else
                          (2.0, 3.5) if opponent == "D" else (2.0, 6.0))
        self.state = ArenaState(22, 22, self.rng.randint(*hp_range), 20,
                                self.rng.uniform(*distance_range))
        self.state.enemy_max_hp = self.state.enemy_hp

    def observation(self, session_id: str, request_id: int) -> dict:
        s = self.state
        damage_fraction = 0.0 if s.previous_hp is None else max(0, s.previous_hp - s.flyman_hp) / s.flyman_max_hp
        speed = 0.0 if s.previous_distance is None else s.previous_distance - s.distance
        return {"schema_version": 1, "session_id": session_id, "request_id": request_id,
                "sample_time_ms": 1000 * request_id,
                "npc": {"uuid": NPC_UUID, "hp": s.flyman_hp, "max_hp": s.flyman_max_hp,
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0}, "heading_degrees": 0.0},
                "combat": {"active": True, "my_turn": True},
                "nearest_hostile": {"uuid": ENEMY_UUID, "hp": s.enemy_hp,
                                    "max_hp": s.enemy_max_hp, "distance": s.distance,
                                    "relative_angle": 0.0, "closing_speed": speed, "visible": True},
                "stimuli": {"damage_fraction": damage_fraction}}

    def step(self, action: CombatAction) -> tuple[CombatOutcome, bool, str | None]:
        s = self.state
        if s.flyman_hp <= 0 or s.enemy_hp <= 0 or s.turn >= self.max_turns:
            raise RuntimeError("episode already terminal")
        before_hp, before_distance = s.flyman_hp, s.distance
        dealt = 0
        status, reason = "executed", ""
        if action == CombatAction.APPROACH:
            s.distance = max(0.5, s.distance - 2.0)
        elif action == CombatAction.RETREAT:
            s.distance = min(12.0, s.distance + 2.0)
        elif action == CombatAction.BASIC_ATTACK:
            if s.distance > 1.5:
                status, reason = "invalid", "target_out_of_melee_range"
            else:
                dealt = min(s.enemy_hp, self.rng.randint(3, 6))
                s.enemy_hp -= dealt
        elif action not in (CombatAction.IDLE, CombatAction.END_TURN):
            status, reason = "invalid", "unknown_action"
        killed = s.enemy_hp <= 0
        if not killed:
            if self.opponent in {"C", "D"}:
                # Kiting opponent: repeated out-of-range attacks never close
                # the gap; a useful policy must switch between approach/attack.
                s.flyman_hp = max(0, s.flyman_hp - (1 if self.opponent == "D"
                                                   else self.rng.randint(1, 2)))
                if s.distance > 1.5:
                    s.distance = min(8.0, s.distance + (0.25 if self.opponent == "D" else 0.5))
            elif s.distance > 1.5:
                s.distance = max(0.5, s.distance - (1.0 if self.opponent == "A" else 1.25))
            else:
                s.flyman_hp = max(0, s.flyman_hp - self.rng.randint(
                    *(2, 5) if self.opponent == "A" else (3, 7)))
        s.turn += 1
        s.previous_hp, s.previous_distance = before_hp, before_distance
        dead = s.flyman_hp <= 0
        timed_out = s.turn >= self.max_turns and not (killed or dead)
        result = "victory" if killed else "defeat" if dead else "timeout" if timed_out else None
        return CombatOutcome(status, reason, dealt, before_hp - s.flyman_hp,
                             killed, dead, killed, dead, timed_out), result is not None, result
