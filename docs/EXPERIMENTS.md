# Connectome experiments

Generated on `2026-09-22` with `flybrain 0.1.0`, 166,700 neurons, 25,582,938 connections, and the CPU backend. Each row aggregates five fixed seeds. Standalone scenarios reset the brain, encoder, and decoder; phases within a scenario preserve voltage, spikes, encoder state, and decoder smoothing. Rates are spikes per neuron per simulated second. The decoder receives only DNa02, DNp01, DNg100, and MDN rates.

| Scenario / phase | DNa02 L | DNa02 R | DNp01 | DNg100 | MDN | Decision | Consistency | Latency |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| threat left / low | 3.80 | 0.20 | 0.80 | 0.10 | 0.30 | turn_left | 100% | 214.6 ms |
| threat left / medium | 4.00 | 0.00 | 17.80 | 0.10 | 0.50 | retreat | 100% | 215.5 ms |
| threat left / high | 4.20 | 0.20 | 43.00 | 0.10 | 0.80 | retreat | 100% | 221.2 ms |
| threat right / low | 0.20 | 3.00 | 0.40 | 0.20 | 0.35 | turn_right | 100% | 210.3 ms |
| threat right / medium | 0.00 | 3.60 | 16.80 | 0.20 | 0.45 | retreat | 100% | 219.1 ms |
| threat right / high | 0.00 | 4.00 | 39.20 | 0.10 | 0.70 | retreat | 100% | 217.6 ms |
| threat front | 2.20 | 2.00 | 45.60 | 0.30 | 0.85 | retreat | 100% | 220.8 ms |
| approaching slowly | 1.20 | 1.20 | 2.40 | 0.20 | 0.50 | retreat | 100% | 210.1 ms |
| approaching quickly | 2.20 | 2.00 | 45.60 | 0.30 | 0.85 | retreat | 100% | 220.1 ms |
| moving away | 1.00 | 1.00 | 0.00 | 0.20 | 0.30 | idle | 100% | 206.0 ms |
| stationary | 1.00 | 1.00 | 0.00 | 0.20 | 0.30 | idle | 100% | 205.5 ms |
| no stimulus | 0.00 | 0.40 | 0.00 | 0.10 | 0.35 | idle | 100% | 202.7 ms |
| left → right / left | 3.80 | 0.20 | 0.80 | 0.10 | 0.30 | turn_left | 100% | 208.2 ms |
| left → right / right | 0.40 | 3.00 | 0.20 | 0.00 | 0.25 | turn_right | 100% | 217.8 ms |
| threat → silence / threat | 4.20 | 0.20 | 43.00 | 0.10 | 0.80 | retreat | 100% | 217.2 ms |
| threat → silence / silence | 1.00 | 0.40 | 1.00 | 0.00 | 0.45 | retreat | 100% | 217.1 ms |

The artifact [experiments/results.json](../experiments/results.json) contains stimuli, spikes, rates, action, latency, and residual state for each run. `other_DNs` records the strongest optional candidate probe; it is diagnostic only and is not an action rule. The persistence phase shows that a residual state can outlast the stimulus window, so it must be reported rather than interpreted as a direct world-state rule.

Recreate the data with:

```powershell
python tools\fake_bg3.py --experiment
```

These are synthetic observations of the frozen simulation, not evidence of a biological fly or BG3 combat performance.
