"""Small adapter around the installed, frozen flybrain 0.1.0 API."""
from __future__ import annotations

from collections import deque
import logging
import numpy as np
from typing import TYPE_CHECKING
from flybg3.config import Config
from .neuron_groups import MOTOR_TYPES, resolve_groups, resolve_candidate_groups

if TYPE_CHECKING:
    from flybg3.telemetry.collector import TelemetryCollector


class FlyBrainAdapter:
    def __init__(self, config: Config):
        import numba
        from flybrain import FlyBrain
        # Application DEBUG should expose FlyBG3 records, not Numba compiler IR.
        logging.getLogger("numba").setLevel(logging.WARNING)
        numba.set_num_threads(min(config.performance.cpu_threads, numba.config.NUMBA_NUM_THREADS))
        self.config = config
        self.brain = FlyBrain(data=config.brain.data or None, seed=config.brain.seed,
                              device=config.performance.device, batch=1, dt=config.brain.dt)
        self.groups = resolve_groups(self.brain)
        self.decoder_motor = {k: v for k, v in self.groups.items() if k.split("_")[0] in MOTOR_TYPES}
        self.candidate_motor = resolve_candidate_groups(self.brain)
        self.motor = self.decoder_motor | self.candidate_motor
        self.reset()

    def reset(self) -> None:
        self.brain.reset(self.config.brain.seed)
        # Includes Numba JIT before advertising ready; no hidden reset per decision.
        for _ in range(self.config.brain.warmup_steps):
            self.brain.step()

    def simulate(self, stimulus: dict[str, float], observer: TelemetryCollector | None = None) -> dict:
        injections = [(self.groups[k], value) for k, value in stimulus.items() if value > 0]
        window: deque[dict[str, int]] = deque(maxlen=self.config.decoder.decision_window)
        total = {k: 0 for k in self.motor}
        for _ in range(self.config.brain.simulation_steps):
            fired = self.brain.step(inject=injections)
            if observer is not None:
                try:
                    observer.observe(fired)
                except Exception:
                    # Display failures never replace or suppress a neural decision.
                    logging.getLogger("FlyBG3").exception("Telemetry probe disabled for this decision")
                    observer.failed = True
                    observer = None
            counts = {k: int(np.isin(fired, idx).sum()) for k, idx in self.motor.items()}
            window.append(counts)
            for k, v in counts.items():
                total[k] += v
        duration = len(window) * self.brain.dt
        rates = {k: sum(frame[k] for frame in window) / (len(idx) * duration)
                 for k, idx in self.motor.items()}
        return {"spikes": total, "rates_hz": rates, "steps_total": self.brain.steps,
                "window_seconds": duration, "residual_state": self.residual_state()}

    def residual_state(self) -> dict:
        """Compact post-decision state; this is observation, never decoder input."""
        values = self.brain.v[:, 0]
        if self.brain.device == "cuda":
            values = values.get()
        values = np.asarray(values)
        groups = {}
        for name, indices in self.motor.items():
            selected = values[indices]
            groups[name] = {"mean_voltage": float(selected.mean()),
                            "max_voltage": float(selected.max()),
                            "fraction_above_half": float((selected >= 0.5).mean())}
        return {"network_mean_voltage": float(values.mean()),
                "network_p95_voltage": float(np.quantile(values, 0.95)),
                "network_fraction_above_half": float((values >= 0.5).mean()),
                "last_step_spike_count": int(len(self.brain.fired)),
                "monitored_groups": groups}

    def info(self) -> dict:
        import importlib.metadata
        return {"flybrain_version": importlib.metadata.version("flybrain"),
                "neurons": self.brain.n, "connections": len(self.brain.weights),
                "descending_neurons": len(self.brain.cells(["descending_neuron"])),
                "device": self.brain.device, "dt": self.brain.dt,
                "groups": {k: len(v) for k, v in self.groups.items()},
                "candidate_groups": {k: len(v) for k, v in self.candidate_motor.items()}}
