"""Fixed MaleCNS neural dynamics and an independently trainable combat readout."""

from .model import CombatAction, NeuralFeatures, CombatOutcome, RewardBreakdown

__all__ = ["CombatAction", "NeuralFeatures", "CombatOutcome", "RewardBreakdown"]
