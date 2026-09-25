"""Count existing spikes without stepping, sampling or modifying the brain."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import math
from time import perf_counter
import numpy as np

from .models import NeuralGroupActivity, NeuralTelemetry
from .registry import ResolvedGroup


def _optional_finite(value: object) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


class TelemetryCollector:
    def __init__(self, groups: dict[str, ResolvedGroup], neuron_count: int, window_steps: int, dt: float):
        if neuron_count <= 0 or window_steps <= 0 or dt <= 0:
            raise ValueError("invalid telemetry population or window")
        self.groups = groups
        self.window_steps = window_steps
        self.dt = dt
        self.group_indices = {}
        for name, group in groups.items():
            indices = np.asarray(group.indices, dtype=np.intp)
            if np.any(indices < 0) or np.any(indices >= neuron_count):
                raise ValueError(f"invalid telemetry group indices: {name}")
            self.group_indices[name] = indices
        self.counts = {name: deque(maxlen=window_steps) for name in groups}
        self.active = np.zeros(neuron_count, dtype=np.bool_)
        self.step_fired = np.zeros(neuron_count, dtype=np.bool_)
        self.total_spikes = 0
        self.steps = 0
        self.compute_ms = 0.0
        self.failed = False

    def observe(self, fired: np.ndarray) -> None:
        """Receive the *returned* spikes from one normal FlyBrain.step call."""
        started = perf_counter()
        indices = np.asarray(fired, dtype=np.intp)
        self.total_spikes += int(len(indices))
        self.active[indices] = True
        self.step_fired[indices] = True
        for name, group_indices in self.group_indices.items():
            self.counts[name].append(int(np.count_nonzero(self.step_fired[group_indices])))
        self.step_fired[indices] = False
        self.steps += 1
        self.compute_ms += (perf_counter() - started) * 1000

    def snapshot(self, observation: dict, decision: str, simulation_ms: float) -> NeuralTelemetry:
        started = perf_counter()
        window_seconds = min(self.window_steps, self.steps) * self.dt
        if window_seconds <= 0:
            raise ValueError("telemetry has no observed steps")
        activities = {
            name: NeuralGroupActivity(
                hz=sum(self.counts[name]) / (group.neuron_count * window_seconds),
                spikes=sum(self.counts[name]), neurons=group.neuron_count)
            for name, group in self.groups.items()
        }
        target = observation.get("nearest_hostile") or {}
        npc = observation.get("npc") or {}
        context = {
            "enemy_distance": _optional_finite(target.get("distance")),
            "enemy_relative_angle": _optional_finite(target.get("relative_angle")),
            "closing_speed": _optional_finite(target.get("closing_speed")),
            "heading_degrees": _optional_finite(npc.get("heading_degrees")),
        }
        result = NeuralTelemetry(
            schema_version=1, recorded_at=datetime.now(timezone.utc).isoformat(),
            session_id=observation["session_id"], request_id=observation["request_id"],
            groups={name: activity for name, activity in activities.items() if self.groups[name].definition.default},
            individual_groups={name: activity for name, activity in activities.items() if not self.groups[name].definition.default},
            total_spikes=self.total_spikes, active_neurons=int(np.count_nonzero(self.active)),
            window_seconds=window_seconds, simulation_ms=simulation_ms,
            telemetry_compute_ms=self.compute_ms + (perf_counter() - started) * 1000,
            decision=decision, environment=context)
        return result
