# Learning capability of the installed MaleCNS stack

Inspected on 2026-09-25 with `flybrain==0.1.0` and compared with the official [fly.ai repository](https://github.com/alextitonis/fly.ai). The installed API is `FlyBrain(..., seed, device, batch, dt)` and `step(eye_drive=None, inject=())` returns indices that fired. Upstream documents a frozen brain and an external linear readout.

| Question | Evidence | Conclusion |
| --- | --- | --- |
| Do synaptic weights change in `step()`? | The implementation updates voltage, firing, last-spike time, and step count, not `weights` or `_W`. | No |
| Is STDP or reward-modulated plasticity present? | No synapse update operation exists in the installed dynamics. | Not implemented |
| Is reward or functional neuromodulation implemented? | The LIF model has tonic, noise, visual/injected current, threshold, and reset, but no reward input. | Not implemented |
| Does state persist? | Voltage, fired indices, step count, last-spike state, and RNG are instance attributes; `reset(seed)` clears them. | Yes, until reset |
| What is trained? | An external readout is available; FlyBG3 uses its own linear policy over descending rates. | Readout only |

The local `brain.npz` contains 166,700 IDs, cell types, sides, superclasses, and positions. `weights.npz` supplies the sparse connectivity indexed by that metadata. Dashboard coordinates and edges are samples, not a complete rendering of the connectome. Source data: [MaleCNS v1.0](https://male-cns.janelia.org/).

The scientifically accurate claim is “a combat policy readout trained from simulated MaleCNS dynamics.” It is not evidence that the fly, the connectome, or a subjective experience learned to play BG3. The policy sees rates derived from spikes; the encoder may transform observations into stimuli and the reward engine observes consequences after an action.
