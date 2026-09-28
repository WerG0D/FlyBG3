"""Optional speech side channel, invoked only after the motor action is published."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Callable, Mapping

from flybg3.bridge.atomic_io import atomic_write_json, read_json
from flybg3.config import SpeechConfig
from .decoder import SpeechDecoder
from .model import SpeechIntent
from .queue import SpeechEvent, SpeechQueue
from .tts import TTSProvider, make_provider
from .verbalizer import TemplateSpeechVerbalizer

LOG = logging.getLogger("FlyBG3")


class SpeechGate:
    def __init__(self, cooldown_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.last_intent = SpeechIntent.SILENT
        self.last_spoken_at = -float("inf")

    def allow(self, intent: SpeechIntent) -> bool:
        if intent is SpeechIntent.SILENT:
            self.last_intent = intent
            return False
        now = self.clock()
        if intent == self.last_intent and now - self.last_spoken_at < self.cooldown_seconds:
            return False
        self.last_intent, self.last_spoken_at = intent, now
        return True

    def reset(self) -> None:
        self.last_intent = SpeechIntent.SILENT
        self.last_spoken_at = -float("inf")


class SpeechRuntime:
    def __init__(self, config: SpeechConfig, directory: Path,
                 log_event: Callable[[dict], None], provider: TTSProvider | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.config = config
        self.directory = directory
        self.log_event = log_event
        self.decoder = SpeechDecoder(config)
        self.verbalizer = TemplateSpeechVerbalizer()
        self.gate = SpeechGate(config.cooldown_seconds, clock)
        self.file_lock = threading.Lock()
        self.queue = SpeechQueue(provider or make_provider(config), config.queue_size, self._complete)

    def reset(self) -> None:
        self.gate.reset()

    def handle(self, session_id: str, request_id: int, rates_hz: Mapping[str, float]) -> dict:
        started = time.perf_counter()
        state = self.decoder.decode(request_id, rates_hz)
        decoded = time.perf_counter()
        text = self.verbalizer.verbalize(state)
        verbalized = time.perf_counter()
        should_queue = text is not None and self.gate.allow(state.intent)
        if text is None:
            self.gate.allow(SpeechIntent.SILENT)
        payload = {"schema_version": 1, "session_id": session_id, **state.to_dict(),
                   "text": text, "queued": should_queue, "spoken": False,
                   "status": "queued" if should_queue else ("silent" if text is None else "suppressed"),
                   "recorded_at": datetime.now(timezone.utc).isoformat(),
                   "timings": {"speech_decode_ms": (decoded-started)*1000,
                               "verbalization_ms": (verbalized-decoded)*1000,
                               "queue_enqueue_ms": 0.0}}
        dropped = ()
        with self.file_lock:
            if should_queue:
                enqueue_start = time.perf_counter()
                accepted, dropped = self.queue.enqueue(SpeechEvent(session_id, request_id, state.intent.value, text))
                payload["timings"]["queue_enqueue_ms"] = (time.perf_counter()-enqueue_start)*1000
                if not accepted:
                    payload["queued"], payload["status"] = False, "queue_closed"
            atomic_write_json(self.directory / "speech.json", payload)
            self.log_event({"type": "speech", **payload})
        for old in dropped:
            self.log_event({"type": "speech", "session_id": old.session_id,
                            "request_id": old.request_id, "intent": old.intent,
                            "text": old.text, "spoken": False, "status": "coalesced"})
        if text:
            LOG.info("Speech intent: %s; text=%r; status=%s", state.intent.upper(), text, payload["status"])
        return payload

    def _complete(self, event: SpeechEvent, played: bool, error: str | None) -> None:
        status = "spoken" if played else ("failed" if error else "null_provider")
        update = {"type": "speech", "session_id": event.session_id, "request_id": event.request_id,
                  "intent": event.intent, "text": event.text, "spoken": played, "status": status}
        if error:
            update["error"] = error
        with self.file_lock:
            current = read_json(self.directory / "speech.json")
            if current and (current.get("session_id"), current.get("request_id")) == (event.session_id, event.request_id):
                current["spoken"], current["status"] = played, status
                atomic_write_json(self.directory / "speech.json", current)
        self.log_event(update)

    def close(self) -> None:
        self.queue.close()
