# FlyBG3 roadmap

## Current milestone: public reproducibility

- BG3SE → atomic JSON → Python → MaleCNS → JSON;
- frozen and inspectable MaleCNS v1.0;
- abstract encoder, motor decoder, and aggregated telemetry;
- optional neural speech with asynchronous TTS;
- synthetic lab with TD, REINFORCE, zero, and shuffled controls;
- BG3 combat probe that records a candidate action without replacing `action.json`.

## Next milestone: controlled real observations

- repeat the probe in a known arena and save real observations;
- compare descending rates, motor decisions, and combat readout for the same `request_id`;
- measure latency, heartbeat failures, stale responses, and residual state;
- keep `physical_actions_enabled = false` during collection.

## Attack milestone: only after validation

- confirm the BG3SE API and signature for a Mud Mephit action;
- validate target, range, line of sight, resources, turn ownership, and AP cost in the game;
- expose an attack behind explicit configuration and a safe fallback;
- test in log-only mode, then in a disposable save;
- record success and failure reasons without leaving vanilla AI in a contradictory state.

## Research milestone

- real holdouts and replay synchronized with telemetry;
- multiple hostiles and allies in the encoder;
- independent neural state per NPC;
- sensitivity analysis for candidate groups;
- comparison of linear readouts and external reservoirs without altering the connectome.

## Experimental product milestone

- multiple independent Flyman NPCs;
- replay of observations, actions, aggregated spikes, and audio;
- automated packaging and BG3SE compatibility checks;
- CI for Python tests, schemas, and dashboard builds;
- an explicit redistribution license before broad publication.

Synthetic arena results must never be presented as evidence of learned BG3 behavior. Each integration milestone must identify the data source, connectome state, and quantities measured directly in the game.
