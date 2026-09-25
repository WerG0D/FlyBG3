"""Exact MaleCNS v1.0 cell-type names for optional read-only probes."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import numpy as np

LOG = logging.getLogger("FlyBG3")

PAM_TYPES = tuple(f"PAM{i:02d}" for i in range(1, 16))
PPL1_TYPES = tuple(f"PPL1{i:02d}" for i in range(1, 9))
DNG12_TYPES = tuple(f"DNg12_{suffix}" for suffix in "abcde")


@dataclass(frozen=True)
class TelemetryGroup:
    name: str
    label: str
    cell_types: tuple[str, ...]
    interpretation: str
    side: str | None = None
    scale: str = "steering_max_hz"
    default: bool = False
    unit: str = "Hz/neuron"


TELEMETRY_GROUPS = (
    TelemetryGroup("steer_left", "STEER LEFT", ("DNa02",), "DNa02 left steering-related output", "L", default=True),
    TelemetryGroup("steer_right", "STEER RIGHT", ("DNa02",), "DNa02 right steering-related output", "R", default=True),
    TelemetryGroup("escape", "ESCAPE", ("DNp01", "DNp02", "DNp11"),
                   "Aggregate of distinct escape/jump-related DNs", scale="escape_max_hz", default=True),
    TelemetryGroup("grooming", "GROOMING", ("DNg11",) + DNG12_TYPES,
                   "Exploratory anterior grooming-related DN family activity", scale="grooming_max_hz", default=True),
    TelemetryGroup("pam", "PAM", PAM_TYPES, "Simulated PAM spikes, not dopamine release",
                   scale="dopamine_max_hz", default=True),
    TelemetryGroup("ppl1", "PPL1", PPL1_TYPES, "Simulated PPL1 spikes, not reward or pleasure",
                   scale="dopamine_max_hz", default=True),
    TelemetryGroup("DNa02_L", "DNa02 L", ("DNa02",), "Individual steering probe", "L"),
    TelemetryGroup("DNa02_R", "DNa02 R", ("DNa02",), "Individual steering probe", "R"),
    TelemetryGroup("DNp01", "DNp01", ("DNp01",), "Giant-fiber escape-related probe", scale="escape_max_hz"),
    TelemetryGroup("DNp02", "DNp02", ("DNp02",), "Jump/escape-related probe", scale="escape_max_hz"),
    TelemetryGroup("DNp11", "DNp11", ("DNp11",), "Jump/escape-related probe", scale="escape_max_hz"),
    TelemetryGroup("DNg11", "DNg11", ("DNg11",), "Front-leg rubbing-related probe", scale="grooming_max_hz"),
    TelemetryGroup("DNg12", "DNg12 family", DNG12_TYPES,
                   "Family-level grooming-related probe; subtype roles not independently established",
                   scale="grooming_max_hz"),
    TelemetryGroup("DNg29", "DNg29", ("DNg29",), "Exploratory probe; no grooming claim"),
    TelemetryGroup("DNg84", "DNg84", ("DNg84",), "Exploratory probe; no grooming claim"),
    TelemetryGroup("DNg100", "DNg100", ("DNg100",), "Forward-walking-related probe"),
    TelemetryGroup("MDN", "MDN", ("MDN",), "Backward-walking-related probe"),
    TelemetryGroup("DNp09", "DNp09", ("DNp09",), "Context-dependent walking/freezing probe"),
)


@dataclass(frozen=True)
class ResolvedGroup:
    definition: TelemetryGroup
    indices: np.ndarray
    type_counts: dict[str, int]

    @property
    def neuron_count(self) -> int:
        return int(len(self.indices))


def resolve_telemetry_groups(brain, *, logger: logging.Logger = LOG) -> dict[str, ResolvedGroup]:
    """Resolve exact types; missing optional probes never prevent neural decisions."""
    available = set(map(str, brain.cell_type))
    groups: dict[str, ResolvedGroup] = {}
    for definition in TELEMETRY_GROUPS:
        found = tuple(t for t in definition.cell_types if t in available)
        missing = sorted(set(definition.cell_types) - set(found))
        if missing:
            logger.warning("Telemetry %s: missing MaleCNS types %s", definition.name, missing)
        if not found:
            logger.warning("Telemetry %s disabled: no matching neurons", definition.name)
            continue
        indices = np.asarray(brain.cells(list(found), side=definition.side), dtype=np.int32)
        if not len(indices):
            logger.warning("Telemetry %s disabled: no matching neurons on side %s", definition.name, definition.side)
            continue
        counts = {t: int(len(brain.cells([t], side=definition.side))) for t in found}
        groups[definition.name] = ResolvedGroup(definition, indices, counts)
        logger.info("Telemetry %-12s %4d neurons (%s)", definition.name, len(indices), ", ".join(f"{k}={v}" for k, v in counts.items()))
    return groups
