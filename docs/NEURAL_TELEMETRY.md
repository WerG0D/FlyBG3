# Neural telemetry

Telemetry is a passive observer of spikes already produced by the decision window. It aggregates relevant groups instead of serializing the full 166,700-neuron state. The monitor and dashboard cannot inject current, call `brain.step()`, alter weights, or change the decoder.

## Groups

The validated display includes steering (`DNa02` left/right), escape (`DNp01`), grooming (`DNg84`), PAM, PPL1, and optional individual groups such as `DNp02`, `DNp11`, `DNg11`, `DNg12`, `DNg29`, `DNg84`, `DNg100`, `MDN`, and `DNp09` when present in MaleCNS metadata. Group names are resolved from the installed dataset; missing optional groups are disabled rather than invented.

For a group with `n` neurons and a window of `T` seconds:

```text
rate_hz = spike_count / (n × T)
```

The raw rate is written to `telemetry.json`. Display bars use configurable visual scales and optional exponential smoothing. Active neuron counts and total spikes are recorded per decision. The visualization samples real coordinates and edges but does not claim to render the full connectome.

## Run

```powershell
python -m flybg3 telemetry
python -m flybg3 telemetry --debug
```

`--debug` adds individual groups and perception context for diagnosis. `telemetry.json` is written atomically after the action is published. The bridge measures neural simulation, telemetry collection, and write costs separately. Tests compare a real MaleCNS decision with telemetry enabled and disabled and require identical spikes, rates, scores, action, and `brain.step()` count.

The telemetry dashboard is not a controller. Use `!flybg3_physical off` in BG3 when collecting log-only observations.
