"""Reward is computed after game/arena outcomes; action labels receive no bonus."""
from __future__ import annotations

from dataclasses import dataclass

from .model import CombatOutcome, RewardBreakdown


@dataclass(frozen=True)
class RewardConfig:
    damage_dealt_scale: float = 0.02
    damage_received_scale: float = -0.02
    enemy_kill: float = 1.0
    self_death: float = -1.0
    victory: float = 3.0
    defeat: float = -3.0
    invalid_action: float = -0.05
    timeout: float = -1.0


class RewardEngine:
    def __init__(self, config: RewardConfig | None = None):
        self.config = config or RewardConfig()

    def calculate(self, outcome: CombatOutcome) -> RewardBreakdown:
        c = self.config
        return RewardBreakdown(
            damage_dealt=outcome.damage_dealt * c.damage_dealt_scale,
            damage_received=outcome.damage_received * c.damage_received_scale,
            kill=c.enemy_kill if outcome.enemy_kill else 0.0,
            death=c.self_death if outcome.self_death else 0.0,
            victory=c.victory if outcome.victory else 0.0,
            defeat=c.defeat if outcome.defeat else 0.0,
            invalid=c.invalid_action if outcome.status == "invalid" else 0.0,
            timeout=c.timeout if outcome.timeout else 0.0,
        )
