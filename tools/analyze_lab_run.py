"""Offline diagnostic of neural separability; never feeds game state to policy."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean


def analyze(run: Path) -> dict:
    grouped: dict[tuple[int, int], dict] = {}
    with (run / "events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event["event"] not in {"neural_state", "combat_state", "policy_decision"}:
                continue
            key = (event["episode_id"], event["request_id"])
            grouped.setdefault(key, {})[event["event"]] = event["payload"]
    rows = [row for row in grouped.values() if "neural_state" in row and "combat_state" in row]
    if not rows:
        raise ValueError(f"no paired neural/combat states in {run}")
    near = [row for row in rows if row["combat_state"]["distance"] <= 1.5]
    far = [row for row in rows if row["combat_state"]["distance"] > 1.5]
    names = tuple(rows[0]["neural_state"]["features_hz"])
    def group_summary(group: list[dict]) -> dict:
        return {name: mean(row["neural_state"]["features_hz"][name] for row in group)
                if group else None for name in names}
    decisions = Counter(row["policy_decision"]["action"] for row in rows if "policy_decision" in row)
    return {"schema_version": 1, "source": str(run), "paired_windows": len(rows),
            "near_windows": len(near), "far_windows": len(far),
            "near_mean_hz": group_summary(near), "far_mean_hz": group_summary(far),
            "policy_decisions": dict(decisions),
            "interpretation": "Observational diagnostic only; mean rate differences do not establish causal encoding."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.run)
    if args.output:
        from flybg3.bridge.atomic_io import atomic_write_json
        atomic_write_json(args.output, result)
    print(json.dumps(result, indent=2))
