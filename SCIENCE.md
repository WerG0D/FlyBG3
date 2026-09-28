# Scientific scope

FlyBG3 is an experimental NPC controller using a spiking simulation whose connectivity is derived from the MaleCNS connectome of *Drosophila melanogaster*. This wording is intentionally narrower than saying that a biological fly is playing the game.

The connectome supplies a structural network. `flybrain` supplies point-neuron LIF dynamics and frozen weights. The sensory encoder is an engineered abstraction over BG3 observations; it is not a retinal model. The motor and speech decoders are software readouts of descending activity. External readouts may be trained, but this does not imply synaptic plasticity in MaleCNS.

The project does not claim language, fear, pleasure, subjective thought, agency, or consciousness. Short phrases such as `Danger. Right.` are deterministic labels chosen by software from neural rates. They are not translations of private experience.

Synthetic arena results are useful for testing causal plumbing, readout dependence, and reproducibility. They do not establish transfer to BG3. Real-game claims require real observations, explicit provenance, repeated trials, and controls for target identity, AP, range, pathfinding, turn state, and other party actors.
