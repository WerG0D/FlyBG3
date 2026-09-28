# Episodic policy-gradient readout

This is a second hypothesis for the external combat readout. MaleCNS, its weights, and its LIF dynamics remain unchanged. The policy receives only 14 descending rates; the environment computes reward after the action. It never receives distance, HP, angle, position, UUID, or raw BG3 state.

For normalized neural vector `z_t`, the stochastic policy is `π(a|z_t) = softmax((W_a · z_t)/T)`. A completed episode supplies discounted return `G_t`; `b_t` is the action-independent mean return from previous episodes at the same step. The update is:

```text
gradient_a = Σ_t [(G_t - b_t) / (S · T)] · [1(a_t=a) - π(a|z_t)] · z_t
W ← W + α · clip_norm(gradient, C)
```

`α`, `γ`, `T`, `S`, and `C` are configured in `config/combat-reinforce.toml`. Training samples from the seeded softmax. Evaluation uses argmax and does not update the readout or baseline. Checkpoints include weights, baselines, counts, seed, and RNG state.

This is a small [REINFORCE](https://doi.org/10.1007/BF00992696) implementation with a linear policy. Sparse rewards, few episodes, compressed neural features, and an artificial arena do not guarantee convergence or transfer to BG3.

```powershell
python -m flybg3 arena --config config/combat-reinforce.toml --mode train --policy trainable --opponent D --episodes 60 --eval-episodes 10
python tools/evaluate_checkpoints.py CHECKPOINT_D60 CHECKPOINT_C100 --config config/combat-reinforce.toml --opponent C --seed 42 --first-episode 1001 --episodes 10 --output experiments/policy_gradient_holdout.json
```

## Observed seed-42 results

| Readout / condition | Training | Evaluation | Wins |
| --- | --- | --- | ---: |
| REINFORCE, D | 60 D episodes | D, IDs 61–70 | 6/10 |
| TD, D | 60 D episodes | D, IDs 61–70 | 6/10 |
| REINFORCE, zero rates | D/60 checkpoint | D, IDs 61–70 | 0/10 |
| REINFORCE, shuffled rates | D/60 checkpoint | D, IDs 61–70 | 3/10 |
| REINFORCE, no C adaptation | D/60 checkpoint | C, IDs 61–70 | 0/10 |
| TD, no C adaptation | D/60 checkpoint | C, IDs 61–70 | 0/10 |
| REINFORCE, adapted on C | +40 C episodes | C, IDs 101–110 | 10/10 |
| Adapted, zero rates | C/100 checkpoint | C, IDs 101–110 | 0/10 |
| Adapted, shuffled rates | C/100 checkpoint | C, IDs 101–110 | 1/10 |

On the same ten unseen C arenas, the D/60 checkpoint won 0/10 and the C/100 checkpoint won 10/10. The result is one seed and one synthetic opponent family. It does not validate physical attack in BG3. Detailed machine-readable results are in [policy_gradient_holdout.json](../experiments/policy_gradient_holdout.json) and [policy_gradient_ablation.json](../experiments/policy_gradient_ablation.json).
