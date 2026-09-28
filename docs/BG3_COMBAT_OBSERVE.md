# BG3 combat probe: observation only

The C-trained checkpoint can be applied to neural rates produced by a real BG3 observation without issuing an attack or replacing the movement decoder.

```text
BG3 observation.json → SensoryEncoder → MaleCNS → 14 descending rates
                                               ├→ movement decoder → action.json
                                               └→ frozen readout    → combat_observe.json
```

`CombatShadowProbe.inspect` accepts only `neural_activity`, `session_id`, and `request_id`. It does not receive HP, distance, position, target identity, or the raw observation. The checkpoint is deterministic and frozen. The bridge publishes `action.json` before computing the shadow candidate, so a probe failure cannot block the existing response.

## Run it

No PAK rebuild is required. Stop any bridge using the Script Extender directory, then run:

```powershell
.\.venv\Scripts\Activate.ps1
$checkpoint = (Get-ChildItem 'runtime/lab-runs/run_manual_f8725c01/checkpoints' -Filter 'policy_final_*.json' | Select-Object -First 1).FullName
python -m flybg3 --config config/combat-bg3-observe.toml --combat-observe-checkpoint $checkpoint
```

Replace the example path with a valid REINFORCE checkpoint if the run directory was moved. Use `--combat-observe-checkpoint`, not the synthetic arena `--checkpoint` option. The bridge prints `Combat readout loaded in OBSERVE ONLY mode` and writes:

```text
%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3\combat_observe.json
```

In the BG3SE server console, keep physical actions disabled:

```text
!flybg3_physical off
!flybg3_combat_move off
!flybg3_auto_end off
!flybg3_status
!flybg3_observe
```

For each request, compare `[FlyBG3] Observation #N sent`, the neural decision, and `Combat shadow #N` in the Python log. The candidate is never sent as a game action. Consumers must check both session and request IDs to reject stale state.

## Suggested cases and limits

Record no visible target, a distant target, a nearby target, high and low Flyman HP, repeated observations, and a target change. Compare `candidate_action`, `features_hz`, motor decision, IDs, and the JSONL session record.

The current observation exposes Flyman's HP and the nearest visible hostile's distance, angle, and relative speed. The target's HP is not exposed. Game values affect the readout only through the encoder and MaleCNS dynamics; the shadow decoder sees neural rates only. Synthetic arena C does not model AP, Mephit range, pathfinding, or real turn rules. A consistent candidate does not authorize `BASIC_ATTACK`. The next gate is repeated log-only evidence followed by explicit target, range, AP, and Script Extender validation.
