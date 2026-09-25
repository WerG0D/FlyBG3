"""Local Windows SAPI via the built-in Windows PowerShell/.NET Framework host."""
from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
from typing import Protocol

from flybg3.config import SpeechConfig

LOG = logging.getLogger("FlyBG3")


class TTSProvider(Protocol):
    def speak(self, text: str) -> None: ...


class NullTTSProvider:
    def speak(self, text: str) -> None:
        pass


class WindowsSpeechProvider:
    """Speak in a separate process; the caller must run this on the audio worker."""

    def __init__(self, rate: int = 0, volume: int = 100):
        if os.name != "nt":
            raise RuntimeError("Windows System.Speech requires Windows")
        executable = shutil.which("powershell.exe")
        if not executable:
            raise RuntimeError("Windows PowerShell 5.1 unavailable")
        self.executable = executable
        self.rate = rate
        self.volume = volume
        self._run("Add-Type -AssemblyName System.Speech; "
                  "$v = [System.Speech.Synthesis.SpeechSynthesizer]::new(); "
                  "try { if ($v.GetInstalledVoices().Count -lt 1) { exit 2 } } finally { $v.Dispose() }")

    def _run(self, script: str) -> None:
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        result = subprocess.run([self.executable, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        if result.returncode:
            error = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Windows TTS failed ({result.returncode}): {error[:300]}")

    def speak(self, text: str) -> None:
        if not text or len(text) > 200:
            raise ValueError("TTS phrase must contain 1..200 characters")
        # Base64 prevents speech text from becoming executable PowerShell syntax.
        encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$v = [System.Speech.Synthesis.SpeechSynthesizer]::new(); "
                  "try { "
                  f"$v.Rate = {self.rate}; $v.Volume = {self.volume}; "
                  "$v.SetOutputToDefaultAudioDevice(); "
                  f"$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_text}')); "
                  "$v.Speak($t) } finally { $v.Dispose() }")
        self._run(script)


def make_provider(config: SpeechConfig) -> TTSProvider:
    if config.provider == "null":
        return NullTTSProvider()
    try:
        return WindowsSpeechProvider(config.voice.rate, config.voice.volume)
    except Exception as exc:
        LOG.warning("Neural speech audio unavailable; using NullTTSProvider: %s", exc)
        return NullTTSProvider()
