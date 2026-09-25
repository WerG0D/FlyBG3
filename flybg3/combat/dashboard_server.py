"""Read-only SSE dashboard. It tails persisted events off the neural path."""
from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import queue
import threading
import time
from urllib.parse import urlparse
from uuid import uuid4

from flybg3.bridge.atomic_io import atomic_write_json

LOG = logging.getLogger("FlyBG3")
CRITICAL = {"action_result", "reward", "episode_end", "checkpoint", "training_metrics"}
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml"}


class TelemetryBus:
    """Bounded per-client queues; persisted JSONL remains the source of truth."""

    def __init__(self, queue_size: int = 64):
        self.queue_size = queue_size
        self.clients: set[queue.Queue] = set()
        self.lock = threading.Lock()
        self.latest: dict[str, dict] = {}

    def subscribe(self) -> queue.Queue:
        client: queue.Queue = queue.Queue(maxsize=self.queue_size)
        with self.lock:
            self.clients.add(client)
            for event in self.latest.values():
                if not client.full():
                    client.put_nowait(event)
        return client

    def unsubscribe(self, client: queue.Queue) -> None:
        with self.lock:
            self.clients.discard(client)

    def reset_run(self) -> None:
        with self.lock:
            self.latest.clear()
            for client in self.clients:
                with client.mutex:
                    client.queue.clear()

    def publish(self, event: dict) -> None:
        kind = event.get("event")
        with self.lock:
            if kind in {"neural_state", "combat_state", "system_status", "training_metrics"}:
                self.latest[kind] = event
            for client in list(self.clients):
                try:
                    client.put_nowait(event)
                except queue.Full:
                    # Fast-changing snapshots may be replaced. Important events
                    # are never silently dropped: detach a stalled client; the
                    # durable JSONL is available for replay/history.
                    if kind in CRITICAL:
                        self.clients.discard(client)
                        try:
                            client.put_nowait(None)
                        except queue.Full:
                            pass
                    else:
                        with client.mutex:
                            items = client.queue
                            for old in list(items):
                                if old and old.get("event") not in CRITICAL:
                                    items.remove(old)
                                    break
                        if not client.full():
                            client.put_nowait(event)


class EventTailer:
    def __init__(self, runs_root: Path, bus: TelemetryBus):
        self.runs_root, self.bus = runs_root, bus
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name="flybg3-dashboard-tailer", daemon=True)
        self.current: Path | None = None

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=2)

    def latest_run(self) -> Path | None:
        folders = [p for p in self.runs_root.glob("run_*") if p.is_dir()]
        return max(folders, key=lambda p: p.stat().st_mtime_ns) if folders else None

    def _run(self) -> None:
        position = 0
        while not self.stopped.wait(0.1):
            try:
                selected = self.latest_run()
                if selected != self.current:
                    self.current, position = selected, 0
                    self.bus.reset_run()
                    self.bus.publish({"schema_version": 1, "event": "system_status", "episode_id": 0,
                                      "request_id": 0, "timestamp": "", "payload":
                                      {"run": str(selected) if selected else None, "status": "connected" if selected else "waiting"}})
                path = selected / "events.jsonl" if selected else None
                if path and path.exists():
                    with path.open("r", encoding="utf-8") as file:
                        file.seek(position)
                        while line := file.readline():
                            if not line.endswith("\n"):
                                break
                            position = file.tell()
                            try:
                                event = json.loads(line)
                            except ValueError:
                                continue
                            if isinstance(event, dict) and event.get("schema_version") == 1:
                                self.bus.publish(event)
            except OSError:
                LOG.exception("Dashboard event tailer recovered from I/O error")


def make_handler(bus: TelemetryBus, tailer: EventTailer, frontend: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            LOG.debug("Dashboard HTTP " + format, *args)

        def _json(self, data, code=200):
            body = json.dumps(data, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if urlparse(self.path).path != "/api/control":
                self._json({"error": "not found"}, 404)
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._json({"error": "application/json required"}, 415)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= 512:
                    raise ValueError("invalid body length")
                data = json.loads(self.rfile.read(size))
                command = data.get("command")
                if command not in {"pause", "resume", "checkpoint", "reset_episode"}:
                    raise ValueError("unknown command")
            except (ValueError, AttributeError, TypeError):
                self._json({"error": "invalid control"}, 400)
                return
            if tailer.current is None:
                self._json({"error": "no active run"}, 409)
                return
            token = uuid4().hex
            atomic_write_json(tailer.current / "control.json",
                              {"schema_version": 1, "token": token, "command": command})
            self._json({"accepted": True, "command": command, "token": token})

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/api/status":
                self._json({"schema_version": 1, "run": str(tailer.current) if tailer.current else None,
                            "clients": len(bus.clients), "connected": tailer.current is not None})
                return
            if route == "/api/history":
                path = tailer.current / "events.jsonl" if tailer.current else None
                events = []
                if path and path.exists():
                    # At most the newest 2 MB, then the newest 1000 complete events.
                    with path.open("rb") as source:
                        source.seek(max(0, path.stat().st_size - 2_000_000))
                        if source.tell():
                            source.readline()
                        for raw in source:
                            try:
                                events.append(json.loads(raw))
                            except ValueError:
                                continue
                self._json(events[-1000:])
                return
            if route == "/api/manifest":
                path = tailer.current / "manifest.json" if tailer.current else None
                self._json(json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else {})
                return
            if route == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                client = bus.subscribe()
                try:
                    while client in bus.clients:
                        try:
                            event = client.get(timeout=10)
                        except queue.Empty:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                            continue
                        if event is None:
                            break
                        self.wfile.write(b"data: " + json.dumps(event, allow_nan=False).encode() + b"\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    bus.unsubscribe(client)
                return
            path = (frontend / route.lstrip("/")).resolve() if route != "/" else frontend / "index.html"
            if not path.is_relative_to(frontend.resolve()) or not path.is_file():
                path = frontend / "index.html"  # Vite client-side route fallback
            if not path.is_file():
                self._json({"error": "dashboard frontend not built; run scripts/dashboard_build.ps1"}, 503)
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", MIME.get(path.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler


def run_dashboard_server(host: str = "127.0.0.1", port: int = 8765,
                         runs_root: Path = Path("runtime/lab-runs"),
                         frontend: Path = Path("dashboard/dist")) -> None:
    bus = TelemetryBus()
    tailer = EventTailer(runs_root, bus)
    tailer.start()
    server = ThreadingHTTPServer((host, port), make_handler(bus, tailer, frontend))
    LOG.info("Combat Learning Lab dashboard: http://%s:%s", host, port)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        tailer.close()
