from __future__ import annotations
import argparse
import logging
from uuid import uuid4
from . import __version__
from .config import load_config
from .bridge.atomic_io import atomic_write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen MaleCNS -> BG3 filesystem bridge")
    parser.add_argument("command", nargs="?", choices=["telemetry"], help="Read-only terminal neural monitor")
    parser.add_argument("--config")
    parser.add_argument("--directory")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Request manual reset in running bridge")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.directory:
        config.bridge.directory = args.directory
    logging.basicConfig(level="DEBUG" if args.debug else config.bridge.log_level,
                        format="[FlyBG3] %(levelname)s: %(message)s")
    print(f"FlyBG3 {__version__}", flush=True)
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
    try:
        BridgeService(config).run(once=args.once)
    except KeyboardInterrupt:
        logging.getLogger("FlyBG3").info("Bridge stopped")


if __name__ == "__main__":
    main()
