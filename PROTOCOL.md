# File protocol

The bridge directory is normally `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3\`.

An observation contains `schema_version`, `session_id`, `request_id`, `sample_time_ms`, `npc`, `combat`, `nearest_hostile`, and `stimuli`. Python accepts only the configured NPC UUID and a fresh BG3 heartbeat. A request is processed at most once per session/request pair.

An action contains the same `schema_version`, `session_id`, `request_id`, NPC UUID, action name, confidence, and debug data. BG3 rejects an action whose session or request is older than its pending observation. Python publishes action after auditing the session record and uses an atomic temporary-file replace.

`heartbeat_bg3.json` and `heartbeat_brain.json` include `alive`, timestamps, session ID, and the last request. A stale bridge cannot block the game. `telemetry.json`, `speech.json`, and `combat_observe.json` are side-channel snapshots; none is an input to the motor decoder.

The stable protocol is intentionally filesystem-based for the MVP. Named pipes or sockets can be added later without changing the schema contract.
