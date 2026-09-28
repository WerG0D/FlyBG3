"""Type names verified against brain-v1 MaleCNS metadata, not inferred aliases."""
SENSORY_TYPES = ("LC4", "LPLC2", "LPLC1", "LC10a")
MOTOR_TYPES = ("DNa02", "DNp01", "DNg100", "MDN")
CANDIDATE_DESCENDING_TYPES = (
    "DNa01", "DNb02", "DNg13",
    "DNa03", "DNa11", "aSP22",
    "DNp09", "DNp26",
    "DNp02", "DNp10", "DNp11",
    "pIP10", "pMP2",
    "DNg103",
)


def resolve_groups(brain) -> dict:
    groups = {f"{t}_{s}": brain.cells([t], side=s)
              for t in SENSORY_TYPES + MOTOR_TYPES for s in "LR"}
    missing = [name for name, indices in groups.items() if not len(indices)]
    if missing:
        raise RuntimeError(f"MaleCNS required neuron groups missing: {missing}")
    descending = set(brain.cells(["descending_neuron"]).tolist())
    for t in MOTOR_TYPES:
        for s in "LR":
            if not set(groups[f"{t}_{s}"].tolist()) <= descending:
                raise RuntimeError(f"{t}_{s} contains non-descending neurons")
    return groups


def resolve_candidate_groups(brain) -> dict:
    """Resolve optional research probes without changing required decoder groups."""
    descending = set(brain.cells(["descending_neuron"]).tolist())
    groups = {}
    for neuron_type in CANDIDATE_DESCENDING_TYPES:
        for side in "LR":
            indices = brain.cells([neuron_type], side=side)
            if len(indices):
                if not set(indices.tolist()) <= descending:
                    raise RuntimeError(f"{neuron_type}_{side} contains non-descending neurons")
                groups[f"{neuron_type}_{side}"] = indices
    return groups
