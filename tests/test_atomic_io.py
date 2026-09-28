import threading
import pytest
from flybg3.bridge.atomic_io import atomic_write_json, read_json
from flybg3.bridge.watcher import single_instance


def test_atomic_readers_never_see_partial(tmp_path):
    path = tmp_path / "action.json"
    atomic_write_json(path, {"id": 0, "body": "x" * 5000})
    errors = []
    accepted = []
    stop = threading.Event()
    def reader():
        while not stop.is_set():
            data = read_json(path)
            if data is not None:
                accepted.append(data)
            if data is not None and data.get("body") != "x" * 5000:
                errors.append(data)
    t = threading.Thread(target=reader)
    t.start()
    try:
        for i in range(20):
            atomic_write_json(path, {"id": i, "body": "x" * 5000})
    finally:
        stop.set()
        t.join()
    assert not errors
    assert accepted
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("content", ['{"x":', 'broken', '[]', '{"x":NaN}', '\ufeff{"x":'])
def test_corrupt_or_incomplete(tmp_path, content):
    path = tmp_path / "observation.json"
    path.write_text(content, encoding="utf-8")
    assert read_json(path) is None
    path.unlink()
    assert read_json(path) is None


def test_sharing_violation_retries(tmp_path, monkeypatch):
    import os
    original = os.replace
    attempts = []
    def replace(a, b):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("reader holds file")
        return original(a, b)
    monkeypatch.setattr(os, "replace", replace)
    atomic_write_json(tmp_path / "a.json", {"x": 1})
    assert read_json(tmp_path / "a.json") == {"x": 1}
    assert len(attempts) == 3


def test_lock(tmp_path):
    with single_instance(tmp_path):
        with pytest.raises(RuntimeError):
            with single_instance(tmp_path):
                pass
