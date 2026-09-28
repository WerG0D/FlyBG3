# Neural lab dashboard

The local backend at `127.0.0.1:8765` tails the newest synthetic run under `runtime/lab-runs` and streams `schema_version=1` events through Server-Sent Events at `/events`. React does not read files every frame. `/api/history` returns recent events, `/api/manifest` returns provenance, and `/api/status` reports the active run. The dashboard is a separate process; a browser failure cannot stop the runner, and JSONL remains the durable source.

```powershell
.\scripts\dashboard_build.ps1
python -m flybg3 dashboard --config config/combat-lab.toml
python -m flybg3 arena --config config/combat-lab.toml --mode eval --policy frozen --episodes 2
```

Open <http://127.0.0.1:8765>. For frontend development, run `.scripts\dashboard_dev.ps1`. Node/npm are needed only to build; Python serves the compiled frontend. Regenerate the real connectome sample with `python -m flybg3 export-connectome`.

The visualization samples 1,400 finite soma positions and up to 2,000 real edges. Up to 300 neurons that fired in the current window and 200 links are highlighted. This is a sample, not a rendering of all 25 million contacts. Colors identify annotated cell types; they do not encode intent or valence.

Panels show the synthetic environment, raw group rates, policy action, exploration, run status, reward breakdown, metrics, and timeline. There are no real BG3 combat events in this lab yet. Pause, resume, save checkpoint, and reset episode operate on the active synthetic run only. Do not expose the server beyond localhost without authentication.

Per-client queues are bounded. Fast snapshots may be replaced; critical events detach a stalled client and remain recoverable through `/api/history`. Visualization overhead is recorded separately and cannot change neural spikes, policy output, or the BG3 adapter.
