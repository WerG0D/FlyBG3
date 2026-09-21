"""Reproducible real-connectome characterization for the fake BG3 peer."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from uuid import UUID

from flybg3 import __version__
from flybg3.brain.neuron_groups import MOTOR_TYPES
from flybg3.brain.simulation import Simulation
from flybg3.config import Config

NPC_UUID = "10000000-0000-4000-8000-000000000001"
TARGET_UUID = "20000000-0000-4000-8000-000000000002"
DEFAULT_SEEDS = (42, 43, 44, 45, 46)


@dataclass(frozen=True)
class Phase:
    name: str
    angle: float | None = None
    distance: float = 8.0
    closing_speed: float = 0.0
    visible: bool = True
    decisions: int = 1


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    phases: tuple[Phase, ...]


SCENARIOS = (
    Scenario("threat_left_low", "Ameaça a -75°, baixa aproximação.", (Phase("stimulus", -75, 12, 0.25),)),
    Scenario("threat_left_medium", "Ameaça a -75°, aproximação média.", (Phase("stimulus", -75, 8, 2.0),)),
    Scenario("threat_left_high", "Ameaça a -75°, aproximação alta.", (Phase("stimulus", -75, 4, 8.0),)),
    Scenario("threat_right_low", "Ameaça a +75°, baixa aproximação.", (Phase("stimulus", 75, 12, 0.25),)),
    Scenario("threat_right_medium", "Ameaça a +75°, aproximação média.", (Phase("stimulus", 75, 8, 2.0),)),
    Scenario("threat_right_high", "Ameaça a +75°, aproximação alta.", (Phase("stimulus", 75, 4, 8.0),)),
    Scenario("threat_front", "Ameaça frontal simétrica em aproximação alta.", (Phase("stimulus", 0, 4, 8.0),)),
    Scenario("approaching_slowly", "Alvo frontal aproximando lentamente.", (Phase("stimulus", 0, 10, 0.5),)),
    Scenario("approaching_quickly", "Alvo frontal aproximando rapidamente.", (Phase("stimulus", 0, 5, 8.0),)),
    Scenario("moving_away", "Alvo frontal afastando; looming é retificado em zero.", (Phase("stimulus", 0, 6, -4.0),)),
    Scenario("stationary", "Alvo frontal imóvel; permanece apenas tracking visual.", (Phase("stimulus", 0, 8, 0.0),)),
    Scenario("no_stimulus", "Nenhum alvo ou dano.", (Phase("silence", None),)),
    Scenario("left_to_right", "Continuidade temporal: esquerda seguida por direita.",
             (Phase("left", -75, 12, 0.25), Phase("right", 75, 12, 0.25))),
    Scenario("threat_then_silence", "Ameaça alta seguida por três janelas sem estímulo.",
             (Phase("threat", -75, 4, 8.0), Phase("silence", None, decisions=3))),
)


def observation(session: str, request_id: int, sample_ms: int, phase: Phase) -> dict:
    hostile = None if phase.angle is None else {
        "uuid": TARGET_UUID, "distance": phase.distance, "relative_angle": phase.angle,
        "closing_speed": phase.closing_speed, "visible": phase.visible,
    }
    return {"schema_version": 1, "session_id": session, "request_id": request_id,
            "sample_time_ms": sample_ms,
            "npc": {"uuid": NPC_UUID, "hp": 40, "max_hp": 50,
                    "position": {"x": 0, "y": 0, "z": 0}},
            "combat": {"active": False, "my_turn": False},
            "nearest_hostile": hostile, "stimuli": {"damage_fraction": 0.0}}


def _mean_std(values: list[float]) -> dict:
    return {"mean": fmean(values), "stddev": pstdev(values), "min": min(values), "max": max(values)}


def _summary(trials: list[dict]) -> dict:
    rates = sorted(trials[0]["descending_rates_hz"])
    return {"runs": len(trials),
            "decision_counts": dict(sorted(Counter(t["decision"] for t in trials).items())),
            "decision_consistency": max(Counter(t["decision"] for t in trials).values()) / len(trials),
            "latency_ms": _mean_std([t["latency_ms"] for t in trials]),
            "descending_rates_hz": {name: _mean_std([t["descending_rates_hz"][name] for t in trials])
                                    for name in rates}}


def run_experiments(config: Config, seeds: tuple[int, ...] = DEFAULT_SEEDS,
                    scenarios: tuple[Scenario, ...] = SCENARIOS) -> dict:
    """Run each scenario from reset; phases within a scenario preserve all state."""
    config = deepcopy(config)
    config.performance.device = "cpu" if config.performance.device == "auto" else config.performance.device
    config.brain.seed = seeds[0]
    sim = Simulation(config)
    output: list[dict] = [{"name": s.name, "description": s.description,
                           "input_phases": [asdict(phase) for phase in s.phases],
                           "phases": [], "trials": []} for s in scenarios]
    for seed in seeds:
        config.brain.seed = seed
        sim.config.brain.seed = seed
        for scenario_index, scenario in enumerate(scenarios):
            sim.reset()
            session = str(UUID(int=(seed << 64) + scenario_index + 1, version=4))
            rid = 0
            sample_ms = 0
            for phase in scenario.phases:
                for window in range(phase.decisions):
                    rid += 1
                    sample_ms += 1000
                    obs = observation(session, rid, sample_ms, phase)
                    action, record = sim.decide(obs)
                    rates = record["neural_activity"]["rates_hz"]
                    decoder_names = {f"{t}_{side}" for t in MOTOR_TYPES for side in "LR"}
                    trial = {"seed": seed, "phase": phase.name, "phase_window": window + 1,
                             "request_id": rid, "stimulus": record["stimulus"],
                             "decoder_input_rates_hz": {k: rates[k] for k in sorted(decoder_names)},
                             "other_descending_rates_hz": {k: v for k, v in rates.items() if k not in decoder_names},
                             "descending_rates_hz": rates, "spikes": record["neural_activity"]["spikes"],
                             "decision": action.action.value, "confidence": action.confidence,
                             "scores": record["scores"], "latency_ms": record["timings"]["total_ms"],
                             "timings_ms": record["timings"],
                             "residual_state": record["neural_activity"]["residual_state"]}
                    output[scenario_index]["trials"].append(trial)
                    output[scenario_index]["phases"].append({"seed": seed, "name": phase.name,
                                                              "window": window + 1})
    for item in output:
        phase_keys = list(dict.fromkeys((t["phase"], t["phase_window"]) for t in item["trials"]))
        item["phase_summaries"] = []
        for phase, window in phase_keys:
            trials = [t for t in item["trials"] if t["phase"] == phase and t["phase_window"] == window]
            item["phase_summaries"].append({"phase": phase, "window": window, **_summary(trials)})
        del item["phases"]
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "flybg3_version": __version__, "seeds": list(seeds),
            "brain": sim.brain.info(),
            "protocol": {"reset_between_scenarios": True, "state_continuous_within_phases": True,
                         "simulation_steps_per_window": config.brain.simulation_steps,
                         "dt_seconds": config.brain.dt,
                         "decoder_receives_only": "descending firing rates"},
            "scenarios": output}


def save_results(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def render_markdown(result: dict) -> str:
    lines = ["# Experimentos do connectome", "",
             f"Gerado em `{result['generated_at']}` com `flybrain {result['brain']['flybrain_version']}`, "
             f"{result['brain']['neurons']} neurônios, {result['brain']['connections']} conexões, "
             f"backend `{result['brain']['device']}`.", "",
             "Cada linha agrega cinco execuções, uma para cada seed fixa. O cérebro, encoder e decoder são "
             "resetados entre cenários; fases do mesmo cenário preservam voltagens, spikes, estado do encoder e "
             "suavização do decoder. Frequências são spikes por neurônio por segundo na janela de 1 s. A latência "
             "é de parede, inclui a instrumentação das sondas adicionais e não é determinística. `DNp01` é o máximo entre os dois lados; `other_DNs` mostra o "
             "maior candidato adicional por frequência média. O decoder recebeu somente as oito taxas de DNa02, "
             "DNp01, DNg100 e MDN.", "",
             "| scenario / phase | DNa02_L | DNa02_R | DNp01 | DNg100 | MDN | other_DNs | decision | consistency | latency ms |",
             "|---|---:|---:|---:|---:|---:|---|---|---:|---:|"]
    for scenario in result["scenarios"]:
        for summary in scenario["phase_summaries"]:
            r = summary["descending_rates_hz"]
            dn01 = max(r["DNp01_L"]["mean"], r["DNp01_R"]["mean"])
            dng = (r["DNg100_L"]["mean"] + r["DNg100_R"]["mean"]) / 2
            mdn = (r["MDN_L"]["mean"] + r["MDN_R"]["mean"]) / 2
            candidates = {k: v["mean"] for k, v in r.items()
                          if not k.startswith(("DNa02_", "DNp01_", "DNg100_", "MDN_"))}
            other_name, other_value = max(candidates.items(), key=lambda item: item[1])
            decisions = ", ".join(f"{k}:{v}" for k, v in summary["decision_counts"].items())
            label = scenario["name"] + "/" + summary["phase"]
            if summary["window"] > 1:
                label += f"[{summary['window']}]"
            lines.append(f"| {label} | {r['DNa02_L']['mean']:.2f} | {r['DNa02_R']['mean']:.2f} | "
                         f"{dn01:.2f} | {dng:.2f} | {mdn:.2f} | {other_name} {other_value:.2f} | "
                         f"{decisions} | {summary['decision_consistency']:.0%} | "
                         f"{summary['latency_ms']['mean']:.1f} ± {summary['latency_ms']['stddev']:.1f} |")
    lines += ["", "## Definição dos estímulos", ""]
    for scenario in SCENARIOS:
        definitions = []
        for phase in scenario.phases:
            if phase.angle is None:
                definitions.append(f"{phase.name}=sem alvo × {phase.decisions}")
            else:
                definitions.append(f"{phase.name}=ângulo {phase.angle:+g}°, distância {phase.distance:g} m, "
                                   f"closing_speed {phase.closing_speed:+g} m/s × {phase.decisions}")
        lines.append(f"- `{scenario.name}`: {scenario.description} " + "; ".join(definitions))
    lines += ["", "Intensidade não é uma ação nem uma classe comportamental. É apenas a combinação declarada "
              "de distância e velocidade de fechamento que o encoder transforma em voltagem de LC4/LPLC2/LPLC1; "
              "LC10a recebe tracking lateral. Velocidade negativa é retificada para zero no canal looming.", "",
              "## Persistência", ""]
    persistent = next(s for s in result["scenarios"] if s["name"] == "threat_then_silence")
    for summary in persistent["phase_summaries"]:
        r = summary["descending_rates_hz"]
        lines.append(f"- `{summary['phase']}[{summary['window']}]`: DNp01 L/R "
                     f"{r['DNp01_L']['mean']:.2f}/{r['DNp01_R']['mean']:.2f} Hz; decisões "
                     f"{summary['decision_counts']}.")
    summaries = {s["name"]: s["phase_summaries"][0]["descending_rates_hz"] for s in result["scenarios"]}
    left_high, right_high, left_low, right_low, quiet = (
        summaries[name] for name in ("threat_left_high", "threat_right_high", "threat_left_low",
                                     "threat_right_low", "no_stimulus"))
    lines += ["", "## Sondas de outros descending neurons", "",
              f"- `DNp02` respondeu fortemente a looming alto: L/R "
              f"{left_high['DNp02_L']['mean']:.1f}/{left_high['DNp02_R']['mean']:.1f} Hz para ameaça esquerda e "
              f"{right_high['DNp02_L']['mean']:.1f}/{right_high['DNp02_R']['mean']:.1f} Hz para direita. `DNp11` "
              f"também subiu para {left_high['DNp11_L']['mean']:.1f}/{left_high['DNp11_R']['mean']:.1f} e "
              f"{right_high['DNp11_L']['mean']:.1f}/{right_high['DNp11_R']['mean']:.1f} Hz. Isso concorda com a "
              "literatura de jump/escape, mas nenhum deles entra no decoder atual.",
              f"- `DNg13` mostrou resposta modesta e lateral em baixa intensidade: L/R "
              f"{left_low['DNg13_L']['mean']:.1f}/{left_low['DNg13_R']['mean']:.1f} Hz para esquerda e "
              f"{right_low['DNg13_L']['mean']:.1f}/{right_low['DNg13_R']['mean']:.1f} Hz para direita. É candidato "
              "a uma futura comparação de steering, ainda sem peso no readout.",
              f"- `DNg103` apresentou baseline alto em silêncio "
              f"({quiet['DNg103_L']['mean']:.1f}/{quiet['DNg103_R']['mean']:.1f} Hz) e pouca discriminação nesta bateria; "
              "não há base para tratá-lo como STOP. `DNp09`, `DNp26`, `DNp10` e `DNa01` também não produziram aqui "
              "um sinal mais limpo que os grupos atuais.",
              "", "O JSON contém, por execução e fase, o estímulo exato, spikes, todas as taxas monitoradas, "
              "scores, decisão, tempos e um resumo residual: voltagem média/p95 da rede, fração acima de 0,5, "
              "spikes do último step e voltagens agregadas dos DNs monitorados. Nenhum desses campos residuais "
              "é entrada do decoder.", "", "## Leitura cautelosa", "",
              "As seeds medem sensibilidade ao ruído do modelo, não variabilidade biológica. Simetria anatômica "
              "imperfeita, pequeno número de neurônios por tipo e estado inicial podem produzir diferenças laterais. "
              "Consistência aqui significa repetição dentro deste LIF e deste encoder, não validação contra comportamento real."]
    return "\n".join(lines) + "\n"
