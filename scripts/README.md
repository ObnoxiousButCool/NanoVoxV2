# NanoVox setup scripts

One-shot scripts to go from a fresh clone to a running app, plus the verification
gate that CI runs.

## Running the app

- **Windows:** double-click `start.bat`, or run it from a terminal:
  ```bat
  scripts\start.bat
  ```
- **macOS / Linux:**
  ```bash
  ./scripts/start.sh
  ```

Each script:

1. Creates the backend virtual environment (`Code/Backend/.venv`) if missing.
2. Installs backend dependencies from `Code/Backend/requirements.txt`.
3. Copies `Code/Backend/.env.example` → `.env` if no `.env` exists yet.
4. Installs frontend dependencies (`npm install`) if `node_modules` is missing.
5. Copies `Code/Frontend/.env.example` → `.env` if no `.env` exists yet.
6. Starts the backend (uvicorn, port 8000) and frontend (Vite, port 5173), then
   opens the app in your browser.

Re-running is safe and fast: it skips venv creation and `npm install` once they
exist, and never overwrites an existing `.env`.

## Verifying before you commit

```bat
scripts\verify.bat
```

```bash
./scripts/verify.sh
```

Runs every gate the CI pipeline runs, in the same order: backend format, lint,
strict typing, Clean Architecture dependency contracts, tests with a coverage
floor; then frontend lint, strict typing, and tests with coverage thresholds.
Requires the dev tooling, which `verify` expects in the venv:

```bash
Code/Backend/.venv/Scripts/python.exe -m pip install -r Code/Backend/requirements-dev.txt
```

## Prerequisites

- **Python 3.10+** on `PATH`. The backend deliberately avoids 3.11-only syntax so
  it runs on the interpreter most machines already have.
- **Node.js 18+** on `PATH` (CI uses 20).

## Configuration

`Code/Backend/.env` and `Code/Frontend/.env` are generated from the matching
`.env.example`, and the defaults work for a local run with no editing.

The backend validates its configuration at startup and fails immediately with a
message naming the offending variable, so a mistake here is obvious rather than
mysterious. An automated test keeps `.env.example` and the settings class in
sync, so no setting can be added without being documented.

Model provider settings (Ollama, OpenAI, Anthropic) arrive in P2 and will be
documented in `.env.example` at that point. Azure AI Foundry is registered but
not implemented in this build, and fails fast with an explicit message if
selected.

## Stopping the servers

- **Windows:** close the two spawned windows ("NanoVox Backend" / "NanoVox
  Frontend"), or press Ctrl+C in each.
- **macOS / Linux:** Ctrl+C in the terminal running `start.sh` stops both.
