# Architecture

```text
BG3 Script Extender Lua
    │ atomic observation.json
    ▼
Python BridgeService
    │ SensoryEncoder
    ▼
FlyBrainAdapter → frozen MaleCNS / flybrain
    │ descending rates
    ├── MotorDecoder → action.json → BG3 action executor
    ├── SpeechDecoder → speech.json → asynchronous TTS
    ├── telemetry collector → telemetry.json
    └── CombatShadowProbe → combat_observe.json
```

BG3 and Python are separate processes. Lua never simulates the connectome, and Python never calls a game API. The bridge uses heartbeats, a persistent request journal, atomic writes, stale-response checks, and a bounded poll loop. The game remains responsive if Python exits.

The encoder is the only boundary that receives world observations. Motor, speech, and combat readouts receive neural features only. The connectome is reset manually or on a new session, not on every observation; simulation steps preserve temporal state.

The combat lab runs the same encoder and MaleCNS against a synthetic arena. Its trainable parameters are external readout weights. The web dashboard consumes persisted events and is outside the decision path.
