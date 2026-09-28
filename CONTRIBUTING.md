# Contributing to FlyBG3

Use Python 3.11–3.13 and create the project virtual environment before running tests:

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
```

Keep MaleCNS frozen. Changes to the encoder, neural groups, decoder, reward, or protocol must include a deterministic test or experiment and must state whether evidence is synthetic or from a real BG3 save. Do not add a direct observation-to-action shortcut.

Keep the Python bridge process separate from BG3. Preserve atomic JSON writes, monotonic request IDs, session checks, heartbeat timeouts, and safe `IDLE` behavior. BG3 Lua changes must use documented BG3SE or Osiris APIs and include the relevant source in `docs/RESEARCH.md`.

Run Python tests, the `brain` marker when the dataset is installed, `npm --prefix dashboard run build`, and `git diff --check` before opening a change. Do not commit save-specific UUIDs, generated PAK files, neural datasets, runtime logs, or local credentials.

Use Conventional Commits. Keep commits focused and do not rewrite shared history without an explicit request.
