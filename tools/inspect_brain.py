"""Load real data and report verified cell counts and backend."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from flybg3.config import load_config
from flybg3.brain.fly_brain import FlyBrainAdapter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-hashes", action="store_true")
    parser.add_argument("--telemetry", action="store_true", help="Validate optional telemetry groups in MaleCNS")
    args = parser.parse_args()
    c = load_config(args.config)
    brain = FlyBrainAdapter(c)
    report = brain.info()
    if args.telemetry:
        from flybg3.telemetry.registry import resolve_telemetry_groups, TELEMETRY_GROUPS
        resolved = resolve_telemetry_groups(brain.brain)
        report["telemetry_groups"] = {
            definition.name: {
                "label": definition.label, "cell_types": list(definition.cell_types),
                "side": definition.side, "neurons": resolved[definition.name].neuron_count,
                "type_counts": resolved[definition.name].type_counts,
                "default": definition.default,
            } if definition.name in resolved else {"available": False, "cell_types": list(definition.cell_types)}
            for definition in TELEMETRY_GROUPS
        }
    if args.verify_hashes:
        from flybrain.data import DATA, FILES
        root = Path(c.brain.data) if c.brain.data else DATA
        report["sha256"] = {}
        for name, expected in FILES.items():
            with (root / name).open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            if digest != expected:
                raise RuntimeError(f"{name}: checksum mismatch")
            report["sha256"][name] = digest
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
