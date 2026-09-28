# Neural speech

Neural speech is an optional observer of MaleCNS output. It never controls the brain and never changes the motor action:

```text
MaleCNS
  ├── MotorDecoder ──► BG3 action
  └── SpeechDecoder ─► SpeechIntent ─► template verbalizer ─► async TTS
```

`SpeechDecoder` receives neural firing rates only: DNa02 L/R, DNp01 L/R, DNg100 L/R, and MDN L/R. It does not receive observation, HP, distance, angle, UUID, position, combat state, or the motor action label. It never calls `brain.step()` or injects a stimulus.

## Intents and thresholds

The decoder emits `SILENT`, `IDLE`, `LEFT`, `RIGHT`, `DANGER`, `DANGER_LEFT`, `DANGER_RIGHT`, `RETREAT`, or `APPROACH`. Escape activity has priority over lateral steering. Strong lateral dominance is measured by:

```text
confidence = abs(L - R) / max(L + R, epsilon)
urgency = min(1, max(DNp01_L, DNp01_R) / urgency_scale_hz)
```

Low confidence or low activity becomes `SILENT`. `min_confidence`, `min_activity_hz`, `escape_threshold_hz`, and `urgency_scale_hz` are configurable. `TemplateSpeechVerbalizer` produces short deterministic phrases such as `Left.`, `Right.`, `Danger.`, `Danger. Left.`, `Danger. Right.`, `Away.`, and `Closer.`

## Cooldown and TTS

`SpeechGate` prefers edge-triggered speech. Repeated identical intents are suppressed until `cooldown_seconds` elapses; `SILENT` resets the active intent. `SpeechQueue` is bounded and coalesces pending directional events. The currently speaking event is not interrupted.

Windows uses local System.Speech through PowerShell 5.1. `NullTTSProvider` is used in tests or with `provider = "null"`. Provider startup and audio errors become warnings and never stop the bridge. `speech.json` records the latest intent, confidence, urgency, source groups, text, and status. The session JSONL records enqueue, coalescing, and completion events.

```powershell
python -m flybg3 speech-test
python -m flybg3 --config config/default.toml --speech
```

The generated sentences are symbolic verbalizations of simulated neural activity. They are not evidence that the simulated fly has language, subjective thoughts, fear, pleasure, or consciousness.
