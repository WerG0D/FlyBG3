"""Compile immutable summaries from recorded synthetic MaleCNS lab runs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from flybg3.bridge.atomic_io import atomic_write_json


def summarize_runs(items: list[str]) -> dict:
    rows = []
    for item in items:
        label, separator, directory = item.partition("=")
        if not separator or not label or not directory:
            raise ValueError("use LABEL=RUN_DIRECTORY")
        root = Path(directory)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
        rows.append({"label": label, "run_directory": str(root),
                     "seed": manifest["seed"], "opponent": manifest.get("opponent", "A"),
                     "policy": manifest["policy"],
                     "parent_checkpoint": manifest.get("parent_checkpoint"),
                     "exploration_override": manifest.get("exploration_override"),
                     "training": metrics["training"], "evaluation": metrics["evaluation"]})
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "MaleCNS v1.0", "environment": "synthetic arena only",
            "runs": rows, "conclusion": "INCONCLUSIVE",
            "note": "Training wins are not evaluation wins. Fixed MaleCNS; only the linear readout changes."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIRECTORY")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_write_json(args.output, summarize_runs(args.run))
    print(args.output)
