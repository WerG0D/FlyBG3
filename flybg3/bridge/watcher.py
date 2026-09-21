"""Tolerant reads and durable at-most-once claims before neural execution."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from .atomic_io import read_json
from .protocol import validate_observation


class RequestJournal:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (session TEXT PRIMARY KEY, last_id INTEGER NOT NULL)")
        self.db.commit()

    def claim(self, session: str, rid: int) -> bool:
        with self.db:
            cursor = self.db.execute("INSERT INTO requests VALUES (?, ?) ON CONFLICT(session) DO UPDATE SET last_id=excluded.last_id WHERE excluded.last_id > requests.last_id", (session, rid))
        return cursor.rowcount == 1

    def close(self) -> None:
        self.db.close()


def observation_at(path: Path, max_bytes: int) -> dict | None:
    data = read_json(path, max_bytes)
    return validate_observation(data) if data else None


@contextmanager
def single_instance(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    f = (directory / "bridge.lock").open("a+b")
    f.seek(0, os.SEEK_END)
    if f.tell() == 0:
        f.write(b"0")
        f.flush()
    f.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        f.close()
        raise RuntimeError(f"Another bridge owns {directory}") from e
    try:
        yield
    finally:
        f.close()  # OS releases lock, including after crashes
