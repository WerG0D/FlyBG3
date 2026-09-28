# Combat readout validation

Five seeded conditions (`random`, `frozen`, `trainable`, `shuffled`, `zero`) share the same initial arena state for each seed and episode index. Each episode resets MaleCNS; neural dynamics continue within an episode. The trainable policy retains its external weights between episodes, explores during training, and uses ε=0 during evaluation. `shuffled` permutes rate/type correspondence and `zero` supplies zero rates while still executing MaleCNS.

The first validation used:

```powershell
python -m flybg3 validate-learning --config config/combat-lab.toml --train-episodes 3 --eval-episodes 3 --seeds 42 43 44
```

The structured result is [experiments/learning_validation.json](../experiments/learning_validation.json). Three episodes per seed are a feasibility test, not statistical inference. The validator therefore reports `INCONCLUSIVE` even when a small mean improves.

The trained readout won 9/9 initial evaluations against opponent A, but the zero control won 6/9. All actions were `BASIC_ATTACK`; opponent A advances into range, so repeating the attack is an environment shortcut. Against B, the same checkpoints won 2/3, 1/3, and 0/3 for seeds 42/43/44. Against kiting opponent C, all seeds won 0/3 and continued choosing `BASIC_ATTACK` out of range.

Continuation on A won 23/24 training episodes and 6/6 evaluation episodes, still using only `BASIC_ATTACK`. Continuation on C failed to produce victories with the one-step TD readout. The D curriculum produced exploration wins but later evaluation selected `IDLE`; paired zero and shuffled controls produced the same actions. These are negative learning results, not evidence that MaleCNS is disconnected.

The later REINFORCE experiment is documented in [POLICY_GRADIENT.md](POLICY_GRADIENT.md). No physical attack is enabled in BG3. A positive neural learning claim requires multiple seeds, stronger holdouts, ablations, and a separately instrumented BG3 evaluation.
