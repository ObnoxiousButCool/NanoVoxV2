#!/usr/bin/env bash
# NanoVox one-shot setup + run script (macOS / Linux).
# Clone the repo, run `./scripts/start.sh` — it creates the backend venv,
# installs backend + frontend dependencies, seeds .env files from
# .env.example if missing, then launches both servers and opens the
# dashboard in your default browser. Ctrl+C stops both servers.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/Code/Backend"
FRONTEND="$ROOT/Code/Frontend"

echo "=== NanoVox setup (macOS/Linux) ==="

# --- Locate a Python interpreter ---
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: Python 3.11+ was not found on PATH. Install it and re-run this script."
    exit 1
fi

# --- Backend: venv + dependencies ---
if [ ! -d "$BACKEND/.venv" ]; then
    echo "Creating backend virtual environment..."
    "$PY" -m venv "$BACKEND/.venv"
fi

# shellcheck disable=SC1091
source "$BACKEND/.venv/bin/activate"
echo "Installing backend dependencies..."
pip install --upgrade pip >/dev/null
pip install -r "$BACKEND/requirements.txt"

if [ ! -f "$BACKEND/.env" ]; then
    echo "Creating backend/.env from .env.example — the defaults work for a local run."
    cp "$BACKEND/.env.example" "$BACKEND/.env"
fi
deactivate

# --- Frontend: dependencies ---
if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js was not found on PATH. Install Node 18+ and re-run this script."
    exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd "$FRONTEND" && npm install)
fi

if [ ! -f "$FRONTEND/.env" ] && [ -f "$FRONTEND/.env.example" ]; then
    echo "Creating frontend/.env from .env.example..."
    cp "$FRONTEND/.env.example" "$FRONTEND/.env"
fi

# --- Launch both servers, stop both on exit ---
cleanup() {
    echo ""
    echo "Stopping NanoVox..."
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://127.0.0.1:8000 ..."
(cd "$BACKEND" && source .venv/bin/activate && exec python -m uvicorn frameworks_drivers.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:5173 ..."
(cd "$FRONTEND" && exec npm run dev) &
FRONTEND_PID=$!

sleep 6
if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:5173"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:5173"
fi

echo ""
echo "NanoVox is running. Press Ctrl+C to stop both servers."
wait
