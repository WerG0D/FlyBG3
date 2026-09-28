# Technical research record

This document records the APIs and evidence used by FlyBG3. It distinguishes verified behavior from plans and from observations that require a real BG3 save.

## Sources

- [fly.ai](https://github.com/alextitonis/fly.ai) and the installed `flybrain==0.1.0` package;
- [MaleCNS v1.0](https://male-cns.janelia.org/);
- [BG3 Script Extender](https://github.com/Norbyte/bg3se) and its [Lua API](https://github.com/Norbyte/bg3se/blob/main/Docs/API.md);
- [official BG3 scripting documentation](https://docs.baldursgate3.game/);
- [LSLib/Divine](https://github.com/Norbyte/lslib).

## Installed neural API

The installed package exposes `FlyBrain(data=None, seed=..., device=..., batch=1, dt=...)`, `step(eye_drive=None, inject=())`, `reset(seed)`, `cells(types, side=...)`, and `info`-compatible metadata. `step()` returns indices of neurons that fired. The local MaleCNS dataset reports 166,700 neurons, 25,582,938 aggregated connections, and 1,314 descending neurons. We use point-neuron LIF dynamics with `dt=0.02` and keep the connectome weights frozen.

Required sensory types verified in the dataset are `LC4`, `LPLC2`, `LPLC1`, and `LC10a`. Motor readout groups are `DNa02`, `DNp01`, `DNg100`, and `MDN`. Additional candidate groups are exposed only as research probes; names are resolved from metadata and missing optional groups are disabled.

The encoder maps abstract observations to sensory current. It does not choose an action. The motor decoder reads descending firing rates only. Speech and combat shadow decoders are parallel consumers of those rates and cannot call `step()` or inject current.

## File bridge

The bridge uses `Ext.IO.SaveFile`, `Ext.IO.LoadFile`, and `Ext.Json` in the server-side Lua mod. Python writes JSON through a temporary file and replace operation. Every observation and action includes `schema_version`, `session_id`, and monotonic `request_id`. A SQLite journal rejects duplicates. The action must match the current session and request; BG3 ignores stale responses.

Heartbeats are written to `heartbeat_bg3.json` and `heartbeat_brain.json`. The Python worker never blocks the BG3 main thread. A stale or absent bridge produces `IDLE` or leaves vanilla control, according to configuration.

## BG3 observation

The Lua collector uses documented engine queries and BG3SE entity enumeration to obtain Flyman's UUID, position, heading, HP, combat turn, and the nearest visible hostile. It computes distance, relative angle, and closing speed from successive samples. The current collector does not claim a complete visibility model or target HP. The encoder receives these values; decoders receive only neural activity.

## Movement APIs

The physical executor validates a destination with `Ext.Level.BeginPathfindingImmediate`, `Ext.Level.FindPath`, and `Ext.Level.ReleasePath`, then calls the BG3SE Osiris proxy `Osi.CharacterMoveToPosition`. The native `glm::vec3` boundary requires a positional Lua table `{x, y, z}`. The executor calls Osiris proxies through `pcall` because BG3SE exposes them as callable proxy values rather than ordinary Lua functions.

The movement milestone was validated by the user in BG3SE v32: neural `TURN_RIGHT` and `TURN_LEFT` decisions produced corresponding physical steps. Movement is disabled by default in combat because `CharacterMoveToPosition` can bypass AP/turn economy and can fall back to teleport-like behavior when a destination is blocked. `!flybg3_combat_move on` is a disposable-save test option.

## Turn and party control

`CreateAtObject(template, anchor, temporary, playSpawn, event, matchOrientation)` creates the mod-owned Flyman template. `GetTemplate` verifies identity. `AddPartyFollower` is used because `MakePlayer` did not establish player control for the tested Mud Mephit save. `IsPartyFollower`, `IsPlayer`, `CharacterJoinedParty`, `GetHostCharacter`, and `IsInCombat` are used as state checks. The adapter refuses to control an unverified or uncontrolled entity.

`EndTurn(character)` and `EntityEvent` are documented options for a future turn executor. `UseSpell` is not treated as a basic attack because documented precondition/resource behavior does not provide the desired action semantics. No attack is currently sent to BG3.

## Mod packaging and Toolkit

The Mud Mephit root template inherits `MEPHIT_Mud_A` from the installed `Shared.pak`. LSLib converts LSX/LOCA sources to LSF/LOCA and builds the PAK. `FlyBG3Arena` is a separate Toolkit module for `Basic_Level_A`; it must not replace the neural module or Script Extender files. The current Toolkit USER MODE does not create a new closed level, so the inherited level is the supported test field.

## Real-save evidence

The real save produced `Observation #1` and a matching Python decision. A later turn with a visible hostile produced `TURN_RIGHT` and `TURN_LEFT`, matching request/session IDs and physical movement after pathfinding fixes. A Mud Mephit instance joined the party as `follower=1`, received a turn, and was protected by the template-scoped immortality test option. Bridge-offline timeouts were reproduced and fixed by starting the Python process and checking the heartbeat.

These observations validate the bridge and movement milestone only. They do not validate learned combat, biological interpretation, consciousness, or an attack policy. The current next experiment is the observation-only combat shadow probe described in [BG3_COMBAT_OBSERVE.md](BG3_COMBAT_OBSERVE.md).

## Scientific limits

The connectome is derived from electron microscopy and is not a complete biological brain model. The simulation omits detailed dendrites, graded signals, full neuromodulation, plasticity, and many physiological variables. Visual input is an abstract detector rather than pixels. A symbolic action or speech phrase is a software readout of simulated activity; it is not a report of subjective experience.
