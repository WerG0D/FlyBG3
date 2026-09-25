"""Bounded latest-state audio worker; no audio work on the BG3 bridge loop."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
import threading
import time
from typing import Callable

from .tts import NullTTSProvider, TTSProvider

LOG = logging.getLogger("FlyBG3")


@dataclass(frozen=True)
class SpeechEvent:
    session_id: str
    request_id: int
    intent: str
    text: str


class SpeechQueue:
    def __init__(self, provider: TTSProvider, capacity: int = 2,
                 on_complete: Callable[[SpeechEvent, bool, str | None], None] | None = None):
        if capacity < 1:
            raise ValueError("speech queue capacity must be positive")
        self.provider = provider
        self.capacity = capacity
        self.on_complete = on_complete
        self.pending: deque[SpeechEvent] = deque()
        self.condition = threading.Condition()
        self.stopped = False
        self.busy = False
        self.thread = threading.Thread(target=self._work, name="FlyBG3Speech", daemon=True)
        self.thread.start()

    def enqueue(self, event: SpeechEvent) -> tuple[bool, tuple[SpeechEvent, ...]]:
        """Replace stale queued events; the currently speaking item is not interrupted."""
        with self.condition:
            if self.stopped:
                return False, ()
            dropped = []
            # Directional states supersede earlier direction words, including
            # RIGHT -> DANGER_RIGHT; only pending audio can be replaced.
            def category(intent: str) -> str:
                return "direction" if intent in {"left", "right", "danger_left", "danger_right"} else intent
            for prior in tuple(self.pending):
                if category(prior.intent) == category(event.intent):
                    self.pending.remove(prior)
                    dropped.append(prior)
            while len(self.pending) >= self.capacity:
                dropped.append(self.pending.popleft())
            self.pending.append(event)
            self.condition.notify()
            return True, tuple(dropped)

    def _work(self) -> None:
        while True:
            with self.condition:
                while not self.pending and not self.stopped:
                    self.condition.wait()
                if self.stopped:
                    return
                event = self.pending.popleft()
                self.busy = True
            played, error = False, None
            try:
                self.provider.speak(event.text)
                played = not isinstance(self.provider, NullTTSProvider)
            except Exception as exc:
                error = str(exc)
                LOG.warning("Neural speech TTS failed for request #%s: %s", event.request_id, exc)
            if self.on_complete:
                try:
                    self.on_complete(event, played, error)
                except Exception:
                    LOG.exception("Neural speech completion callback failed")
            with self.condition:
                self.busy = False
                self.condition.notify_all()

    def wait_idle(self, timeout: float) -> bool:
        """Only for one-shot test mode; the continuous bridge never waits for audio."""
        deadline = time.monotonic() + timeout
        with self.condition:
            while (self.pending or self.busy) and not self.stopped:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            return not self.pending and not self.busy

    def close(self) -> None:
        with self.condition:
            self.stopped = True
            self.pending.clear()
            self.condition.notify_all()
        self.thread.join(timeout=0.1)
