from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import time
from urllib.request import urlopen, Request

import numpy as np

from flybg3.combat.dashboard_server import TelemetryBus, EventTailer, make_handler
from flybg3.combat.experiment import RunStore
from flybg3.bridge.atomic_io import atomic_write_json, read_json
from flybg3.telemetry.connectome import active_snapshot, structural_sample
from http.server import ThreadingHTTPServer


def event(kind, request=1):
    return {"schema_version": 1, "event": kind, "episode_id": 1,
            "request_id": request, "timestamp": "", "payload": {"request": request}}


def test_bus_latest_state_and_critical_backpressure():
    bus = TelemetryBus(queue_size=2)
    client = bus.subscribe()
    bus.publish(event("neural_state", 1))
    bus.publish(event("neural_state", 2))
    bus.publish(event("neural_state", 3))
    assert client in bus.clients
    assert client.get_nowait()["request_id"] in {2, 3}
    bus.publish(event("reward", 4))
    bus.publish(event("episode_end", 5))
    bus.publish(event("reward", 6))
    assert client not in bus.clients
    new = bus.subscribe()
    assert new.get_nowait()["request_id"] == 3
    bus.reset_run()
    assert bus.latest == {}
    assert new.empty()


def test_tailer_reads_complete_jsonl_and_reconnects(tmp_path):
    root = tmp_path / "runs"
    run = root / "run_test"
    run.mkdir(parents=True)
    events = run / "events.jsonl"
    bus = TelemetryBus()
    client = bus.subscribe()
    tailer = EventTailer(root, bus)
    tailer.start()
    try:
        events.write_text(json.dumps(event("reward")) + "\n", encoding="utf-8")
        deadline = time.monotonic() + 2
        received = []
        while time.monotonic() < deadline:
            try:
                received.append(client.get(timeout=.1))
            except queue.Empty:
                pass
            if any(e["event"] == "reward" for e in received):
                break
        assert any(e["event"] == "reward" for e in received)
        with events.open("a", encoding="utf-8") as file:
            file.write('{"schema_version":1,"event":"episode_end"')
        time.sleep(.15)
        assert not any(e.get("event") == "episode_end" for e in received)
        with events.open("a", encoding="utf-8") as file:
            file.write(',"episode_id":1,"request_id":2,"timestamp":"","payload":{}}\n')
        assert client.get(timeout=2)["event"] == "episode_end"
    finally:
        tailer.close()


def test_http_dashboard_serves_history_and_status(tmp_path):
    root = tmp_path / "runs"
    run = root / "run_test"
    run.mkdir(parents=True)
    (run / "events.jsonl").write_text(json.dumps(event("reward")) + "\n", encoding="utf-8")
    (run / "manifest.json").write_text('{"schema_version":1}', encoding="utf-8")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<h1>FlyBG3</h1>", encoding="utf-8")
    bus, tailer = TelemetryBus(), EventTailer(root, TelemetryBus())
    tailer.current = run
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bus, tailer, frontend))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert "FlyBG3" in urlopen(base + "/").read().decode()
        assert json.load(urlopen(base + "/api/status"))["connected"] is True
        assert json.load(urlopen(base + "/api/history"))[0]["event"] == "reward"
        assert json.load(urlopen(base + "/api/manifest"))["schema_version"] == 1
        with urlopen(base + "/events", timeout=2) as stream:
            deadline = time.monotonic() + 2
            while not bus.clients and time.monotonic() < deadline:
                time.sleep(.01)
            assert bus.clients
            bus.publish(event("reward", 9))
            assert b'"request_id": 9' in stream.readline()
        request = Request(base + "/api/control", data=b'{"command":"pause"}', method="POST",
                          headers={"Content-Type": "application/json"})
        assert json.load(urlopen(request))["accepted"] is True
        assert read_json(run / "control.json")["command"] == "pause"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class TinyBrain:
    def __init__(self):
        self.positions = np.array([[0., 0., 0.], [1., 0., 0.], [np.nan, 0., 0.]])
        self.ids = np.array([101, 102, 103])
        self.cell_type = np.array(["DNa02", "LC4", "other"])
        self.side = np.array(["L", "R", "M"])
        self.indptr = np.array([0, 1, 1, 1])
        self.indices = np.array([1])
        self.weights = np.array([.5])
        self.n = 3


def test_connectome_uses_only_real_finite_positions_and_edges():
    brain = TinyBrain()
    structural = structural_sample(brain, 3, 3)
    assert [n["neuron_id"] for n in structural["nodes"]] == [101, 102]
    assert structural["edges"] == [{"source": 0, "target": 1, "weight_abs": .5}]
    active = active_snapshot(brain, np.array([True, True, True]), 3, 3)
    assert active["total_active"] == 3
    assert active["sampled_active"] == 2


def test_pause_resume_checkpoint_and_reset_commands(tmp_path):
    from flybg3.combat.policy import TrainableNeuralReadoutPolicy
    store = RunStore(tmp_path / "run_test", {"schema_version": 1})
    policy = TrainableNeuralReadoutPolicy()
    atomic_write_json(store.root / "control.json", {"schema_version": 1, "token": "pause", "command": "pause"})
    result = []
    worker = threading.Thread(target=lambda: result.append(store.before_decision(policy, 1, 1)))
    worker.start()
    time.sleep(.2)
    assert worker.is_alive()
    atomic_write_json(store.root / "control.json", {"schema_version": 1, "token": "resume", "command": "resume"})
    worker.join(timeout=2)
    assert not worker.is_alive() and result == [None]
    atomic_write_json(store.root / "control.json", {"schema_version": 1, "token": "save", "command": "checkpoint"})
    assert store.before_decision(policy, 1, 2) is None
    assert len(list((store.root / "checkpoints").glob("policy_manual_*.json"))) == 1
    atomic_write_json(store.root / "control.json", {"schema_version": 1, "token": "reset", "command": "reset_episode"})
    assert store.before_decision(policy, 1, 3) == "reset_episode"


import pytest


@pytest.mark.brain
def test_dashboard_probe_does_not_change_real_brain_or_action(observation):
    from flybg3.brain.simulation import Simulation
    from flybg3.config import Config
    from copy import deepcopy

    off = Config()
    on = deepcopy(off)
    on.dashboard.enabled = True
    a, b = Simulation(off), Simulation(on)
    action_a, record_a = a.decide(observation)
    action_b, record_b = b.decide(observation)
    assert record_a["neural_activity"] == record_b["neural_activity"]
    assert record_a["neural_activity"]["steps_total"] == record_b["neural_activity"]["steps_total"]
    assert record_a["scores"] == record_b["scores"]
    assert action_a.action == action_b.action
    from flybg3.combat.features import NeuralFeatureExtractor
    from flybg3.combat.policy import FrozenPolicy
    features_a = NeuralFeatureExtractor().extract(record_a["neural_activity"])
    features_b = NeuralFeatureExtractor().extract(record_b["neural_activity"])
    assert features_a == features_b
    assert FrozenPolicy(seed=42).select_action(features_a, training=False) == FrozenPolicy(seed=42).select_action(features_b, training=False)
    from flybg3.combat.policy_gradient import FrozenPolicyGradient
    assert (FrozenPolicyGradient(seed=42).select_action(features_a, training=False)
            == FrozenPolicyGradient(seed=42).select_action(features_b, training=False))
    assert "visualization" in record_b and "visualization" not in record_a
