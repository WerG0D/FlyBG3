"""Separate read-only terminal that renders one frame per neural decision."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from flybg3.bridge.atomic_io import read_json
from flybg3.config import TelemetryConfig
from .registry import TELEMETRY_GROUPS

DEFINITIONS = {group.name: group for group in TELEMETRY_GROUPS}
BAR_WIDTH = 18


@dataclass
class DisplayState:
    rates: dict[str, float] = field(default_factory=dict)

    def displayed_rate(self, name: str, raw_hz: float, alpha: float) -> float:
        previous = self.rates.get(name, raw_hz)
        value = alpha * raw_hz + (1 - alpha) * previous
        self.rates[name] = value
        return value


def normalized_display_rate(hz: float, max_hz: float) -> float:
    """Visual-only scale; the raw rate is kept separately in telemetry.json."""
    return min(1.0, max(0.0, hz / max_hz))


def _bar(fraction: float, width: int = BAR_WIDTH) -> Text:
    filled = min(width, max(0, round(fraction * width)))
    # ASCII survives legacy Windows cp1252 consoles and redirected PowerShell output.
    return Text.assemble(("#" * filled, "bold cyan"), ("." * (width - filled), "dim"))


def _valid(snapshot: dict | None) -> bool:
    return bool(snapshot and snapshot.get("schema_version") == 1
                and isinstance(snapshot.get("session_id"), str)
                and type(snapshot.get("request_id")) is int and snapshot["request_id"] > 0
                and isinstance(snapshot.get("groups"), dict)
                and isinstance(snapshot.get("decision"), str))


def _format_optional(value: object, suffix: str = "", digits: int = 2) -> str:
    if type(value) not in (int, float) or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}{suffix}"


def render_snapshot(snapshot: dict, config: TelemetryConfig, state: DisplayState,
                    *, debug: bool = False) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column(width=14)
    table.add_column(width=BAR_WIDTH)
    table.add_column(justify="right", width=12)
    def row(name: str, activity: dict, width: int) -> tuple[str, Text, str] | None:
        raw = activity.get("hz")
        if type(raw) not in (int, float) or not math.isfinite(raw):
            return None
        definition = DEFINITIONS.get(name)
        label = definition.label if definition else name
        scale = getattr(config.scale, definition.scale, 10.0) if definition else 10.0
        shown = state.displayed_rate(name, float(raw), config.smoothing)
        return label, _bar(normalized_display_rate(shown, scale), width), f"{raw:.2f} Hz"

    for name, activity in snapshot.get("groups", {}).items():
        if isinstance(activity, dict) and (values := row(name, activity, BAR_WIDTH)):
            table.add_row(*values)
    details = None
    if debug:
        details = Table.grid(padding=(0, 1))
        for width in (14, 8, 9, 14, 8, 9):
            details.add_column(width=width)
        individual = []
        for name, activity in snapshot.get("individual_groups", {}).items():
            if isinstance(activity, dict) and (values := row(name, activity, 8)):
                individual.append(values)
        for offset in range(0, len(individual), 2):
            left = individual[offset]
            right = individual[offset + 1] if offset + 1 < len(individual) else ("", Text(""), "")
            details.add_row(*left, *right)
    environment = snapshot.get("environment") or {}
    distance = _format_optional(environment.get("enemy_distance"), " m")
    angle = _format_optional(environment.get("enemy_relative_angle"), " deg")
    active = f"{snapshot['active_neurons']:,}" if isinstance(snapshot.get("active_neurons"), int) else "n/a"
    spikes = f"{snapshot['total_spikes']:,}" if isinstance(snapshot.get("total_spikes"), int) else "n/a"
    lines = [Text(f"Active neurons: {active}  |  Neural spikes: {spikes}"),
             Text(f"Simulation: {_format_optional(snapshot.get('simulation_ms'), ' ms', 1)}"),
             Text(f"Enemy: {distance} @ {angle}")]
    if debug:
        lines.extend((Text(f"NPC heading: {_format_optional(environment.get('heading_degrees'), ' deg')}  |  "
                           f"Closing speed: {_format_optional(environment.get('closing_speed'), ' m/s')}"),
                      Text(f"Telemetry compute: {_format_optional(snapshot.get('telemetry_compute_ms'), ' ms', 2)}")))
    lines.append(Text(f"DECISION: {snapshot['decision']}", style="bold green"))
    parts = [Text("MaleCNS v1.0", style="bold"), table]
    if debug and details is not None:
        parts.extend((Text("INDIVIDUAL", style="dim"), details))
    content = Group(*parts, *lines)
    return Panel(content, title="FlyBG3 Neural Monitor",
                 subtitle=f"request #{snapshot['request_id']} / {snapshot['session_id'][:8]}",
                 border_style="cyan", safe_box=True, expand=False)


def run_dashboard(directory: Path, config: TelemetryConfig, *, debug: bool = False,
                  once: bool = False, poll_seconds: float = 0.2, console: Console | None = None) -> None:
    console = console or Console()
    state = DisplayState()
    last_token: tuple[str, int] | None = None
    with Live(Panel("Waiting for telemetry.json...", title="FlyBG3 Neural Monitor"),
              console=console, auto_refresh=False, transient=False) as live:
        while True:
            snapshot = read_json(directory / "telemetry.json")
            if _valid(snapshot):
                token = (snapshot["session_id"], snapshot["request_id"])
                if token != last_token:
                    if last_token is not None and token[0] != last_token[0]:
                        state = DisplayState()
                    started = time.perf_counter()
                    live.update(render_snapshot(snapshot, config, state, debug=debug), refresh=True)
                    last_token = token
                    # Render time is measured here, not fed back into neural processing.
                    if debug:
                        console.log(f"Dashboard update: {(time.perf_counter() - started) * 1000:.2f} ms")
                    if once:
                        return
            time.sleep(poll_seconds)
