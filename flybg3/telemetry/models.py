"""Versioned, compact neural telemetry snapshots."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NeuralGroupActivity:
    hz: float
    spikes: int
    neurons: int


@dataclass(frozen=True)
class NeuralTelemetry:
    schema_version: int
    recorded_at: str
    session_id: str
    request_id: int
    groups: dict[str, NeuralGroupActivity]
    individual_groups: dict[str, NeuralGroupActivity]
    total_spikes: int
    active_neurons: int
    window_seconds: float
    simulation_ms: float
    telemetry_compute_ms: float
    decision: str
    environment: dict[str, float | None]

    def to_dict(self) -> dict:
        return asdict(self)
