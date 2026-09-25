"""Bounded samples of actual MaleCNS positions/edges for passive visualization."""
from __future__ import annotations

import numpy as np
from weakref import WeakKeyDictionary

_POSITION_CACHE: WeakKeyDictionary = WeakKeyDictionary()


def _normalized_positions(positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(positions).all(axis=1)
    finite = positions[valid]
    lo, hi = np.min(finite, axis=0), np.max(finite, axis=0)
    span = np.maximum(hi - lo, 1)
    return valid, (positions - lo) / span * 2 - 1


def _brain_positions(brain) -> tuple[np.ndarray, np.ndarray]:
    cached = _POSITION_CACHE.get(brain)
    if cached is None:
        cached = _normalized_positions(np.asarray(brain.positions))
        _POSITION_CACHE[brain] = cached
    return cached


def _edges(brain, selected: np.ndarray, max_edges: int) -> list[dict]:
    if max_edges <= 0:
        return []
    selected_set = set(map(int, selected))
    found = []
    for pre in selected:
        begin, end = int(brain.indptr[pre]), int(brain.indptr[pre + 1])
        for pointer in range(begin, end):
            post = int(brain.indices[pointer])
            if post in selected_set:
                found.append((abs(float(brain.weights[pointer])), int(pre), post))
    found.sort(reverse=True)
    return [{"source": pre, "target": post, "weight_abs": round(weight, 5)}
            for weight, pre, post in found[:max_edges]]


def active_snapshot(brain, active: np.ndarray, max_neurons: int, max_edges: int) -> dict:
    positions = brain.positions
    if positions is None:
        return {"layout": "unavailable", "nodes": [], "edges": []}
    valid, scaled = _brain_positions(brain)
    indices = np.flatnonzero(active & valid)
    if len(indices) > max_neurons:
        indices = indices[np.linspace(0, len(indices) - 1, max_neurons, dtype=int)]
    nodes = [{"index": int(i), "neuron_id": int(brain.ids[i]) if hasattr(brain, "ids") else int(i),
              "cell_type": str(brain.cell_type[i]), "side": str(brain.side[i]),
              "position": [round(float(v), 5) for v in scaled[i]], "activity": 1.0}
             for i in indices]
    return {"layout": "MaleCNS positions normalized to [-1,1]",
            "nodes": nodes, "edges": _edges(brain, indices, max_edges),
            "total_active": int(np.count_nonzero(active)), "sampled_active": len(nodes)}


def structural_sample(brain, max_neurons: int = 1400, max_edges: int = 2000) -> dict:
    if brain.positions is None:
        return {"schema_version": 1, "layout": "unavailable", "nodes": [], "edges": []}
    valid, scaled = _brain_positions(brain)
    indices = np.flatnonzero(valid)
    if len(indices) > max_neurons:
        indices = indices[np.linspace(0, len(indices) - 1, max_neurons, dtype=int)]
    nodes = [{"index": int(i), "neuron_id": int(brain.ids[i]) if hasattr(brain, "ids") else int(i),
              "cell_type": str(brain.cell_type[i]), "side": str(brain.side[i]),
              "position": [round(float(v), 5) for v in scaled[i]]}
             for i in indices]
    return {"schema_version": 1, "dataset": "MaleCNS v1.0",
            "layout": "anatomical soma positions, normalized coordinates",
            "nodes": nodes, "edges": _edges(brain, indices, max_edges),
            "source_neurons": int(brain.n), "sampled_neurons": len(nodes)}
