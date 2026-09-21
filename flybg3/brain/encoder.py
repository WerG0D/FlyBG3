"""Abstract feature detectors; this module never selects motor actions."""
from __future__ import annotations

import math
from flybg3.config import EncoderConfig
from .neuron_groups import SENSORY_TYPES


class SensoryEncoder:
    def __init__(self, config: EncoderConfig):
        self.config = config
        self.previous: tuple[str, float, float] | None = None

    def reset(self) -> None:
        self.previous = None

    def encode(self, observation: dict) -> dict[str, float]:
        c = self.config
        drive = {f"{t}_{s}": 0.0 for t in SENSORY_TYPES for s in "LR"}
        target = observation.get("nearest_hostile")
        damage = min(1.0, observation.get("stimuli", {}).get("damage_fraction", 0.0))
        if target and target["visible"] and target["distance"] <= c.max_distance:
            distance = max(target["distance"], c.object_radius)
            size = 2 * math.atan(c.object_radius / distance)
            # Derivative of angular size in radians per second. Velocity estimates
            # from game sampling are optional; identity changes do not create looming.
            growth = 0.0
            sampled = observation["sample_time_ms"] / 1000
            if self.previous and self.previous[0] == target["uuid"]:
                elapsed = sampled - self.previous[2]
                if c.minimum_sample_seconds <= elapsed <= c.maximum_sample_seconds:
                    growth = max(0.0, (size - self.previous[1]) / elapsed)
            speed = target.get("closing_speed")
            if speed is not None:
                growth = max(0.0, 2 * c.object_radius * speed / (distance**2 + c.object_radius**2))
            self.previous = (target["uuid"], size, sampled)
            # Negative angle = left. Saturation preserves side for rear targets.
            lateral = max(-1.0, min(1.0, target["relative_angle"] / 90 * c.left_right_gain))
            strengths = {"LPLC2": growth * c.looming_gain,
                         "LC4": growth * c.looming_gain,
                         "LPLC1": growth * c.looming_gain / (1 + size),
                         "LC10a": c.tracking_gain}
            for side, weight in (("L", (1 - lateral) / 2), ("R", (1 + lateral) / 2)):
                for t, value in strengths.items():
                    drive[f"{t}_{side}"] = min(c.cap, value * weight)
        else:
            self.previous = None
        # Damage is an explicit experimental proxy for a nondirectional threat,
        # not a claim of stimulating identified nociceptors.
        for side in "LR":
            drive[f"LC4_{side}"] = min(c.cap, drive[f"LC4_{side}"] + damage * c.damage_gain / 2)
        return drive
