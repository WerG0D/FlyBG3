from __future__ import annotations
import argparse
import logging
from pathlib import Path
from uuid import uuid4
from . import __version__
from .config import load_config
from .bridge.atomic_io import atomic_write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen MaleCNS -> BG3 filesystem bridge")
    parser.add_argument("command", nargs="?", choices=["telemetry", "speech-test", "arena", "validate-learning", "generalize", "dashboard", "export-connectome"],
                        help="Read-only monitor or standalone Windows voice check")
    parser.add_argument("--config")
    parser.add_argument("--directory")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Request manual reset in running bridge")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--speech", action="store_true", help="Enable optional neural speech for this bridge run")
    parser.add_argument("--mode", choices=["observe", "validate", "train", "eval"])
    parser.add_argument("--policy", choices=["random", "frozen", "trainable", "shuffled", "zero"])
    parser.add_argument("--algorithm", choices=["td", "reinforce"],
                        help="External combat readout algorithm; MaleCNS remains fixed")
    parser.add_argument("--opponent", choices=["A", "B", "C", "D"], default="A",
                        help="Synthetic arena opponent for arena training/evaluation")
    parser.add_argument("--exploration", type=float,
                        help="Override epsilon for a training run; logged in its manifest")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--train-episodes", type=int, default=4)
    parser.add_argument("--eval-episodes", type=int, default=2)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--checkpoint", type=Path,
                        help="Resume the neural readout from this checkpoint (arena train/eval)")
    parser.add_argument("--combat-observe-checkpoint", type=Path,
                        help="Log frozen combat candidates from real BG3 neural activity; never execute them")
    args = parser.parse_args()
    lab_command = args.command in {"arena", "validate-learning", "generalize", "dashboard", "export-connectome"}
    config = load_config(args.config or ("config/combat-lab.toml" if lab_command else None))
    if args.algorithm:
        config.combat.algorithm = args.algorithm
        config.validate()
    if args.directory:
        config.bridge.directory = args.directory
    if args.speech:
        config.speech.enabled = True
    if args.combat_observe_checkpoint and (args.command is not None or config.combat.mode != "observe"):
        parser.error("combat observation checkpoint requires the BG3 bridge in observe mode")
    logging.basicConfig(level="DEBUG" if args.debug else config.bridge.log_level,
                        format="[FlyBG3] %(levelname)s: %(message)s")
    print(f"FlyBG3 {__version__}", flush=True)
    if args.command == "dashboard":
        from .combat.dashboard_server import run_dashboard_server
        run_dashboard_server(config.dashboard.host, config.dashboard.port)
        return
    if args.command == "export-connectome":
        from .brain.fly_brain import FlyBrainAdapter
        from .telemetry.connectome import structural_sample
        import json
        config.dashboard.enabled = True
        brain = FlyBrainAdapter(config).brain
        output = args.output or Path("dashboard/public/connectome.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(structural_sample(brain), separators=(",", ":")), encoding="utf-8")
        print(f"Anatomical sample: {output}", flush=True)
        return
    if args.command == "generalize":
        from .combat.experiment import evaluate_generalization
        output = args.output or Path("experiments/generalization.json")
        result = evaluate_generalization(config, args.input or Path("experiments/learning_validation.json"),
                                        args.eval_episodes, output)
        print(f"Generalization: {result['conclusion']}\nResults: {output}", flush=True)
        return
    if args.command in {"arena", "validate-learning"}:
        from .combat.experiment import run_control, validate_learning
        if args.command == "validate-learning":
            output = args.output or Path("experiments/learning_validation.json")
            result = validate_learning(config, tuple(args.seeds), args.train_episodes,
                                       args.eval_episodes, output, runs_root=Path("runtime/lab-runs"))
            print(f"Validation: {result['conclusion']}\nResults: {output}", flush=True)
        else:
            name = args.policy or config.combat.policy
            mode = args.mode or config.combat.mode
            root = Path("runtime/lab-runs") / f"run_manual_{uuid4().hex[:8]}"
            result = run_control(config, name, config.brain.seed,
                                 args.episodes if mode == "train" else 0,
                                 args.episodes if mode != "train" else args.eval_episodes,
                                 root=root, checkpoint=args.checkpoint,
                                 opponent=args.opponent, exploration=args.exploration)
            print(f"Arena {name} {mode}: {result['evaluation']}\nRun: {root}", flush=True)
        return
    if args.command == "speech-test":
        from .speech.tts import NullTTSProvider, make_provider
        provider = make_provider(config.speech)
        if isinstance(provider, NullTTSProvider):
            print("Speech audio unavailable (NullTTSProvider); choose a Windows voice provider", flush=True)
            raise SystemExit(1)
        for phrase in ("Left.", "Right.", "Danger.", "Away."):
            print(f"Speaking: {phrase}", flush=True)
            provider.speak(phrase)
        return
    if args.command == "telemetry":
        from .telemetry.dashboard import run_dashboard
        try:
            run_dashboard(config.directory(), config.telemetry, debug=args.debug, once=args.once,
                          poll_seconds=max(0.2, config.performance.poll_ms / 1000))
        except KeyboardInterrupt:
            pass
        return
    if args.reset:
        atomic_write_json(config.directory() / "control.json", {"command": "reset", "command_id": str(uuid4())})
        return
    from .bridge.service import BridgeService
    probe = None
    if args.combat_observe_checkpoint:
        from .combat.shadow import CombatShadowProbe
        probe = CombatShadowProbe(args.combat_observe_checkpoint,
                                  algorithm=config.combat.algorithm, seed=config.brain.seed)
        logging.getLogger("FlyBG3").info("Combat readout loaded in OBSERVE ONLY mode; no attack action will be sent to BG3")
    try:
        BridgeService(config, combat_probe=probe).run(once=args.once)
    except KeyboardInterrupt:
        logging.getLogger("FlyBG3").info("Bridge stopped")


if __name__ == "__main__":
    main()
