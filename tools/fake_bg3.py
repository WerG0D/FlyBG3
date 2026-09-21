"""Real neural scenarios, or a file-protocol peer. Synthetic UUIDs only here."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4
from flybg3.config import load_config
from flybg3.brain.simulation import Simulation
from flybg3.bridge.atomic_io import atomic_write_json, read_json
from flybg3.bridge.protocol import response_matches


def scenario(session: str, rid: int, npc: str, target: str, name: str) -> dict:
    params = {"left": (8.0, -75.0, 0.0), "right_approaching": (4.0, 75.0, 8.0),
              "front_looming": (3.0, 0.0, 10.0), "none": None}[name]
    hostile = None if params is None else dict(uuid=target, distance=params[0], relative_angle=params[1],
                                              closing_speed=params[2], visible=True)
    return {"schema_version": 1, "session_id": session, "request_id": rid, "sample_time_ms": rid * 1000,
            "npc": {"uuid": npc, "hp": 40, "max_hp": 50, "position": {"x": 0, "y": 0, "z": 0}},
            "combat": {"active": False, "my_turn": False}, "nearest_hostile": hostile,
            "stimuli": {"damage_fraction": 0.0}}


def show(action: dict, record: dict | None = None) -> None:
    print("\n+---------------- FlyBG3 real brain ----------------+")
    if record:
        print("Stimulus (voltage / step):")
        for k, v in record["stimulus"].items():
            print(f"  {k:10} {'#' * min(30, round(v * 30)):30} {v:.3f}")
    print("Motor (Hz / neuron):")
    for k, v in action.get("debug", {}).get("neural_activity", {}).get("rates_hz", {}).items():
        print(f"  {k:10} {'#' * min(30, round(v)):30} {v:.2f}")
    print("Scores:", action.get("debug", {}).get("scores", {}))
    print("ACTION:", action["action"].upper())
    print("Timing:", action.get("debug", {}).get("timings", {}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--bridge-dir", type=Path, help="Use running bridge instead of in-process real brain")
    parser.add_argument("--scenario", choices=["all", "left", "right_approaching", "front_looming", "none"], default="all")
    parser.add_argument("--output", type=Path, default=Path("logs/fake-bg3.jsonl"))
    parser.add_argument("--wait-seconds", type=float, default=30)
    parser.add_argument("--experiment", action="store_true", help="Run the reproducible real-connectome battery")
    parser.add_argument("--experiment-results", type=Path, default=Path("experiments/results.json"))
    parser.add_argument("--experiment-doc", type=Path, default=Path("docs/EXPERIMENTS.md"))
    args = parser.parse_args()
    c = load_config(args.config)
    if args.experiment:
        from flybg3.experiments import run_experiments, save_results, render_markdown
        result = run_experiments(c)
        save_results(result, args.experiment_results)
        args.experiment_doc.parent.mkdir(parents=True, exist_ok=True)
        args.experiment_doc.write_text(render_markdown(result), encoding="utf-8")
        print(f"Wrote {args.experiment_results} and {args.experiment_doc}")
        return
    names = ["left", "right_approaching", "front_looming", "none"] if args.scenario == "all" else [args.scenario]
    sim = None if args.bridge_dir else Simulation(c)
    session, npc, target = str(uuid4()), str(uuid4()), str(uuid4())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for rid, name in enumerate(names, 1):
        observation = scenario(session, rid, npc, target, name)
        if args.bridge_dir:
            atomic_write_json(args.bridge_dir / "heartbeat_bg3.json", {"alive": True, "session_id": session, "last_request": rid, "unix_ms": int(time.time() * 1000)})
            atomic_write_json(args.bridge_dir / "observation.json", observation)
            deadline = time.monotonic() + args.wait_seconds
            while True:
                action = read_json(args.bridge_dir / "action.json")
                if action and response_matches(action, observation):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("No matching bridge response; start python -m flybg3 --directory ... --once")
                time.sleep(0.05)
            record = {"observation": observation, "action": action}
        else:
            result, record = sim.decide(observation)
            action = result.to_dict()
        print(f"Scenario: {name} / request {rid}")
        show(action, record if "stimulus" in record else None)
        with args.output.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
