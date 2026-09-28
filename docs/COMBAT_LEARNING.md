# Combat Learning Lab

MaleCNS v1.0 remains fixed. The first environment is a synthetic 1v1 arena using the same `SensoryEncoder`, `Simulation`/`FlyBrainAdapter`, and `NeuralFeatureExtractor` intended for a later BG3 integration. The arena executes an action, reports the outcome, and only then computes reward.

```text
Arena observation → SensoryEncoder → MaleCNS (50 × 20 ms)
                                          ↓ descending rates
                               NeuralFeatureExtractor
                                          ↓
                                linear combat readout
                                          ↓ action
                             arena.step(action) → outcome
                                          ↓
                                     RewardEngine
                                          ↓ reward
                              next observation → update
```

`CombatPolicy.select_action(features: NeuralFeatures, training=...)` accepts neural features only. It never accepts observation, position, HP, distance, combat state, or cooldown. The 14 fixed features are DNa02 L/R, DNp01 L/R, DNg100 L/R, MDN L/R, DNp02 L/R, DNp11 L/R, and aSP22 L/R. The last six are candidate probes, not validated attack commands. `BASIC_ATTACK` is a learned association over rates, not the meaning of one named neuron.

## Synthetic action space

`IDLE`, `APPROACH`, `RETREAT`, `BASIC_ATTACK`, and `END_TURN`. Flyman starts with 22 HP, the enemy has 14–20 HP, and separation is 2–6 m. Approach changes distance by 2 m; retreat changes it by 2 m; a basic attack is valid at 1.5 m or less and deals 3–6 HP. These are environment rules, not policy shortcuts. Invalid attacks return an explicit status and reason. Episodes end at victory, defeat, or `max_turns` (24); timeout receives terminal reward −1.

## TD policy and controls

`TrainableNeuralReadoutPolicy` uses one linear row per action, seeded epsilon-greedy exploration, and one-step TD after the next neural window is available:

```text
δ = r + γ max_a Q_a(x') − Q_action(x)
w_action ← w_action + α δ x
```

Default `α=0.05` and `γ=0.9`. Evaluation forces ε=0 and never updates weights. Controls are seeded random, frozen initial weights, trainable, shuffled rates, and zero rates. MaleCNS still runs in both ablations; they test dependence on neural information.

## Run

```powershell
python -m flybg3 arena --config config/combat-lab.toml --mode eval --policy frozen --episodes 2
python -m flybg3 arena --config config/combat-lab.toml --mode train --policy trainable --episodes 10
python -m flybg3 validate-learning --config config/combat-lab.toml --train-episodes 3 --eval-episodes 3 --seeds 42 43 44
```

Use `--checkpoint` to continue a readout; recent checkpoints preserve the random state. Runs contain `manifest.json`, `events.jsonl`, `episodes.jsonl`, `metrics.json`, and checkpoints under `runtime/lab-runs/`. The synthetic arena is not BG3 evidence. Physical combat, target HP attribution, AP, pathfinding, and real turn economy remain future work.
