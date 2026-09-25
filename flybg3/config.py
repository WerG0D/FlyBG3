"""Validated, centralized parameters; no game UUID is provided by default."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class BrainConfig:
    simulation_steps: int = 50
    dt: float = 0.02
    seed: int = 42
    data: str = ""
    warmup_steps: int = 10


@dataclass
class EncoderConfig:
    max_distance: float = 30.0
    object_radius: float = 0.5
    looming_gain: float = 10.0
    left_right_gain: float = 1.0
    damage_gain: float = 0.8
    tracking_gain: float = 0.6
    cap: float = 0.8
    minimum_sample_seconds: float = 0.05
    maximum_sample_seconds: float = 10.0


@dataclass
class DecoderConfig:
    minimum_activity: float = 0.1
    rate_scale_hz: float = 10.0
    decision_window: int = 50
    smoothing: float = 0.25  # previous-output contribution
    hysteresis: float = 0.05
    minimum_action_decisions: int = 1


@dataclass
class PerformanceConfig:
    device: str = "auto"
    cpu_threads: int = 4
    decision_timeout_ms: int = 3000
    poll_ms: int = 100


@dataclass
class BridgeConfig:
    directory: str = ""
    npc_uuid: str = ""
    log_directory: str = "logs"
    log_level: str = "INFO"
    max_json_bytes: int = 262144


@dataclass
class TelemetryScaleConfig:
    steering_max_hz: float = 10.0
    escape_max_hz: float = 50.0
    grooming_max_hz: float = 10.0
    dopamine_max_hz: float = 50.0


@dataclass
class TelemetryConfig:
    enabled: bool = True
    smoothing: float = 0.25  # display EMA: current-sample contribution
    scale: TelemetryScaleConfig = field(default_factory=TelemetryScaleConfig)


@dataclass
class SpeechVoiceConfig:
    rate: int = 0  # System.Speech range: -10..10
    volume: int = 100  # 0..100


@dataclass
class SpeechConfig:
    enabled: bool = False
    provider: str = "windows"
    cooldown_seconds: float = 2.0
    min_confidence: float = 0.35
    min_activity_hz: float = 1.0
    escape_threshold_hz: float = 3.0
    urgency_scale_hz: float = 20.0
    queue_size: int = 2
    speak_idle: bool = False
    voice: SpeechVoiceConfig = field(default_factory=SpeechVoiceConfig)


@dataclass
class Config:
    brain: BrainConfig = field(default_factory=BrainConfig)
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    decoder: DecoderConfig = field(default_factory=DecoderConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    bridge: BridgeConfig = field(default_factory=BridgeConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)

    def validate(self) -> None:
        import math
        for section in (self.brain, self.encoder, self.decoder, self.performance, self.bridge,
                        self.telemetry, self.telemetry.scale, self.speech, self.speech.voice):
            defaults = type(section)()
            for f in fields(section):
                v, default = getattr(section, f.name), getattr(defaults, f.name)
                if isinstance(default, TelemetryScaleConfig):
                    if not isinstance(v, TelemetryScaleConfig):
                        raise ValueError("telemetry.scale must be a table")
                elif isinstance(default, SpeechVoiceConfig):
                    if not isinstance(v, SpeechVoiceConfig):
                        raise ValueError("speech.voice must be a table")
                elif isinstance(default, bool):
                    if type(v) is not bool:
                        raise ValueError(f"{f.name} must be boolean")
                elif isinstance(default, int) and (type(v) is not int):
                    raise ValueError(f"{f.name} must be integer")
                if isinstance(default, float) and (type(v) not in (float, int) or not math.isfinite(v)):
                    raise ValueError(f"{f.name} must be finite number")
                if isinstance(default, str) and not isinstance(v, str):
                    raise ValueError(f"{f.name} must be string")
        for v in (self.brain.simulation_steps, self.brain.dt, self.encoder.max_distance,
                  self.encoder.object_radius, self.decoder.rate_scale_hz, self.decoder.decision_window,
                  self.performance.cpu_threads, self.performance.decision_timeout_ms,
                  self.performance.poll_ms, self.bridge.max_json_bytes,
                  self.encoder.minimum_sample_seconds, self.encoder.maximum_sample_seconds):
            if v <= 0:
                raise ValueError("steps, scales, limits and timings must be positive")
        if self.brain.warmup_steps < 0 or self.brain.seed < 0 or self.decoder.minimum_action_decisions < 1:
            raise ValueError("invalid seed, warmup or action duration")
        if self.decoder.decision_window > self.brain.simulation_steps:
            raise ValueError("decision_window exceeds simulation_steps")
        if self.encoder.maximum_sample_seconds < self.encoder.minimum_sample_seconds:
            raise ValueError("invalid sample interval")
        if self.performance.device not in {"cpu", "cuda", "auto"}:
            raise ValueError("device must be cpu, cuda or auto")
        if not 0 <= self.decoder.smoothing < 1:
            raise ValueError("smoothing must be in [0,1)")
        if any(getattr(self.encoder, k) < 0 for k in ("looming_gain", "left_right_gain", "damage_gain", "tracking_gain", "cap")):
            raise ValueError("encoder gains must be nonnegative")
        if self.decoder.minimum_activity < 0 or self.decoder.hysteresis < 0:
            raise ValueError("decoder thresholds must be nonnegative")
        if not 0 <= self.telemetry.smoothing <= 1:
            raise ValueError("telemetry.smoothing must be in [0,1]")
        if any(getattr(self.telemetry.scale, f.name) <= 0 for f in fields(self.telemetry.scale)):
            raise ValueError("telemetry visual scales must be positive")
        if self.speech.provider not in {"windows", "null"}:
            raise ValueError("speech.provider must be windows or null")
        if self.speech.cooldown_seconds < 0 or self.speech.min_activity_hz < 0 or self.speech.escape_threshold_hz < 0:
            raise ValueError("speech thresholds and cooldown must be nonnegative")
        if self.speech.urgency_scale_hz <= 0 or self.speech.queue_size < 1:
            raise ValueError("speech urgency scale and queue size must be positive")
        if not 0 <= self.speech.min_confidence <= 1:
            raise ValueError("speech.min_confidence must be in [0,1]")
        if not -10 <= self.speech.voice.rate <= 10 or not 0 <= self.speech.voice.volume <= 100:
            raise ValueError("speech voice rate or volume out of range")

    def directory(self) -> Path:
        if self.bridge.directory:
            return Path(self.bridge.directory).expanduser()
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise ValueError("Set bridge.directory outside Windows")
        return Path(root) / "Larian Studios/Baldur's Gate 3/Script Extender/FlyBG3"


def load_config(path: str | Path | None = None) -> Config:
    config = Config()
    if path is not None:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        for name, values in raw.items():
            if name not in {f.name for f in fields(config)}:
                raise ValueError(f"Unknown section: {name}")
            cls = type(getattr(config, name))
            if name == "telemetry" and "scale" in values:
                values = dict(values)
                values["scale"] = TelemetryScaleConfig(**values["scale"])
            if name == "speech" and "voice" in values:
                values = dict(values)
                values["voice"] = SpeechVoiceConfig(**values["voice"])
            setattr(config, name, cls(**values))
    if os.environ.get("FLYBG3_NPC_UUID"):
        config.bridge.npc_uuid = os.environ["FLYBG3_NPC_UUID"].lower()
    config.validate()
    return config
