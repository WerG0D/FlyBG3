# FlyBG3

> A Baldur's Gate 3 NPC driven by a spiking neural simulation whose connectivity is derived from the MaleCNS v1.0 connectome of *Drosophila melanogaster*.

[![Python](https://img.shields.io/badge/python-3.11--3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Status](https://img.shields.io/badge/status-experimental-f0b35b)](#status)

FlyBG3 keeps the game and the neural process separate. BG3 Script Extender writes an observation, the Python bridge encodes it as an abstract sensory stimulus, runs the frozen MaleCNS network, and returns an action. The game remains responsible for validating turn state and executing the result.

```text
BG3.exe
   │ Lua server-side / BG3 Script Extender
   ▼
observation.json ──► Python bridge ──► sensory encoder
                                      │
                                      ▼
                         flybrain / MaleCNS v1.0
                                      │ descending spikes and rates
                                      ├──► MotorDecoder ──► action.json ──► BG3
                                      └──► SpeechDecoder ─► optional TTS
```

## Status

The real neural pipeline, atomic file bridge, telemetry, speech side channel, and experimental lateral movement have been exercised in a real save. The synthetic combat lab trains only an external linear readout; MaleCNS weights remain frozen.

| Component | Status |
| --- | --- |
| MaleCNS v1.0 through `flybrain` | Validated: 166,700 neurons, 25,582,938 aggregated connections, 1,314 descending neurons |
| BG3 observation to abstract stimulus | Implemented |
| Motor decoder | `IDLE`, `TURN_LEFT`, `TURN_RIGHT`, `APPROACH`, `RETREAT` |
| Atomic bridge and heartbeats | Implemented |
| Physical test movement | Validated for lateral steps with BG3SE v32 |
| SpeechDecoder and Windows TTS | Optional, asynchronous, validated |
| Combat Learning Lab | Synthetic only; MaleCNS frozen |
| BG3 combat shadow probe | Implemented in observation-only mode |
| Physical Mud Mephit attack | Not integrated |

Synthetic arena results are not evidence of learned combat in BG3. The latest REINFORCE run reached 10/10 on the adapted C holdout while the previous checkpoint reached 0/10. See [POLICY_GRADIENT.md](docs/POLICY_GRADIENT.md), [LEARNING_VALIDATION.md](docs/LEARNING_VALIDATION.md), and [BG3_COMBAT_OBSERVE.md](docs/BG3_COMBAT_OBSERVE.md).

## Installation

Requirements: Windows 10/11, Python 3.11–3.13 (3.12 is recommended), [BG3 Script Extender](https://github.com/Norbyte/bg3se), [LSLib/Divine](https://github.com/Norbyte/lslib) for mod packaging, and Node.js/npm for the dashboard build.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m flybrain download
python tools\inspect_brain.py --verify-hashes --output docs\brain-inspection.json
```

The official download uses `%USERPROFILE%\fly-data` by default. Set `FLY_DATA` to choose another directory. `device = "auto"` selects CUDA only when a compatible CuPy device is available.

## Run the synthetic pipeline

```powershell
python tools\fake_bg3.py --experiment
python tools\fake_bg3.py --scenario left
```

The experiment updates [experiments/results.json](experiments/results.json) and [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md). To exercise the file bridge in two terminals:

```powershell
python -m flybg3 --directory runtime\fake --once
python tools\fake_bg3.py --bridge-dir runtime\fake --scenario left
```

This verifies `observation.json → FlyBrain → action.json`, monotonic request IDs, heartbeats, duplicate protection, and atomic writes.

## Combat lab and dashboard

```powershell
.\scripts\dashboard_build.ps1
python -m flybg3 dashboard --config config\combat-lab.toml
python -m flybg3 arena --config config\combat-lab.toml --mode train --policy trainable --episodes 10
```

Open <http://127.0.0.1:8765>. The dashboard is read-only with respect to decisions: it does not select actions, inject stimuli, or alter the connectome.

```powershell
python -m flybg3 arena --config config\combat-lab.toml --mode eval --policy frozen --episodes 10
python -m flybg3 validate-learning --config config\combat-lab.toml --train-episodes 3 --eval-episodes 3 --seeds 42 43 44
```

Read [COMBAT_LEARNING.md](docs/COMBAT_LEARNING.md), [REWARD_DESIGN.md](docs/REWARD_DESIGN.md), and [DASHBOARD.md](docs/DASHBOARD.md) before interpreting results.

## Telemetry and neural speech

```powershell
python -m flybg3 telemetry --debug
python -m flybg3 speech-test
python -m flybg3 --config config\default.toml --speech
```

`SpeechDecoder` receives neural firing rates only and feeds deterministic templates through an asynchronous local TTS queue. Speech is disabled by default. Set `provider = "null"` to test without audio. Speech never calls `brain.step()`, injects stimuli, or changes `action.json`. See [NEURAL_SPEECH.md](docs/NEURAL_SPEECH.md) and [NEURAL_TELEMETRY.md](docs/NEURAL_TELEMETRY.md).

## Baldur's Gate 3 integration

Start the bridge before loading a save:

```powershell
.\.venv\Scripts\Activate.ps1
python -m flybg3 --config config\default.toml
```

In the BG3SE server console:

```text
!flybg3_spawn
!flybg3_status
!flybg3_observe
```

The mod creates or recovers Flyman, a mod-owned Mud Mephit template, and adds it as a party follower. The game supplies the real instance UUID; no save UUID is hardcoded. Use `FLYBG3_NPC_UUID` or `[bridge].npc_uuid` to restrict the bridge to one instance.

Communication files normally live under `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3\`:

```text
observation.json  action.json  telemetry.json  speech.json
heartbeat_bg3.json  heartbeat_brain.json  requests.sqlite3
```

Expected log-only output:

```text
[FlyBG3] Observation #1 sent
[FlyBG3] Neural decision #1: TURN_RIGHT
```

Physical movement is opt-in:

```text
!flybg3_physical on
!flybg3_combat_move on
```

`!flybg3_combat_move on` can bypass AP/turn economy and is intended only for test saves. The next game milestone remains observation-only: compare the trained readout with real telemetry before evaluating a physical attack.

Package the mod with:

```powershell
.\scripts\build_mod.ps1 -DivineExe "C:\path\to\LSLib\Packed\Tools\Divine.exe"
.\scripts\install_mod.ps1
```

The Toolkit arena workflow is documented in [TOOLKIT_ARENA.md](docs/TOOLKIT_ARENA.md). The API evidence and known limitations are collected in [RESEARCH.md](docs/RESEARCH.md).

## Science and limitations

This is a spiking neural simulation whose connectivity is derived from a real connectome. It is not a complete biological fly: the model uses point-neuron LIF dynamics and abstract sensory detectors, without detailed dendrites, full neuromodulation, biological plasticity, or evidence of consciousness.

The connectome remains frozen. When learning is enabled, only an external linear readout is updated from neural rates and synthetic arena rewards. The motor decoder receives neural activity rather than raw position, distance, direction, or HP. The encoder is the boundary where game observations become stimuli.

## Tests

```powershell
python -m pytest -q
python -m pytest -q -m brain
npm --prefix dashboard run build
git diff --check
```

Basic tests do not require the dataset. `brain` tests load MaleCNS and verify counts, temporal continuity, stimulus causality, and the absence of a sensory bypass. A real BG3 state requires the manual procedure in [BG3_COMBAT_OBSERVE.md](docs/BG3_COMBAT_OBSERVE.md).

## Roadmap

The detailed roadmap is [ROADMAP.md](docs/ROADMAP.md):

1. repeat the observation-only BG3 probe and publish real observations;
2. measure the readout on controlled saves with target, range, and turn context;
3. validate target, range, AP, and preconditions before any physical attack;
4. add a Mud Mephit attack behind an explicit configuration gate;
5. record real episodes and replays while keeping MaleCNS frozen;
6. support independent NPC brains, multiple targets, and neural replay.

## Contributing and licensing

Read [CONTRIBUTING.md](../CONTRIBUTING.md), [SCIENCE.md](../SCIENCE.md), and [PROTOCOL.md](../PROTOCOL.md) when those project guides are added. Changes to stimuli, readout groups, or rewards should include a reproducible experiment and identify whether evidence is synthetic or from BG3.

This repository does not yet declare a redistribution license. Do not assume that code, connectome data, or BG3 resources may be redistributed without checking their respective licenses.
