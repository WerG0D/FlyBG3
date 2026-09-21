"""Same-directory replace with bounded Windows sharing-violation retries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time

REPLACE_RETRY_SECONDS = 1.0
REPLACE_RETRY_INITIAL_SECONDS = 0.005
REPLACE_RETRY_MAX_SECONDS = 0.05


def atomic_write_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        deadline = time.monotonic() + REPLACE_RETRY_SECONDS
        delay = REPLACE_RETRY_INITIAL_SECONDS
        while True:
            try:
                os.replace(name, path)
                break
            except PermissionError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(delay, remaining))
                delay = min(delay * 2, REPLACE_RETRY_MAX_SECONDS)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path: Path, max_bytes: int = 262144) -> dict | None:
    try:
        with Path(path).open("rb") as f:
            raw = f.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None
