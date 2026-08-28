#!/usr/bin/env bash
# Runs every quality gate the CI pipeline runs, in the same order.
# Anything that fails here fails the build. Run this before committing.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/Code/Backend"
FRONTEND="$ROOT/Code/Frontend"
FAILED=0

if [ ! -d "$BACKEND/.venv" ]; then
  echo "ERROR: backend virtual environment missing. Run ./scripts/start.sh first."
  exit 1
fi

if [ -x "$BACKEND/.venv/bin/python" ]; then
  PY="$BACKEND/.venv/bin/python"
  BIN="$BACKEND/.venv/bin"
else
  PY="$BACKEND/.venv/Scripts/python.exe"
  BIN="$BACKEND/.venv/Scripts"
fi

run() {
  echo
  echo "--- $1 ---"
  shift
  if ! "$@"; then
    FAILED=1
  fi
}

echo "=== NanoVox verification ==="

cd "$BACKEND"
run "Backend: format" "$PY" -m ruff format --check .
run "Backend: lint" "$PY" -m ruff check .
run "Backend: types" "$PY" -m mypy
run "Backend: architecture contracts" "$BIN/lint-imports"
run "Backend: tests and coverage" "$PY" -m pytest --cov

cd "$FRONTEND"
run "Frontend: lint" npm run lint
run "Frontend: types" npm run typecheck
run "Frontend: tests and coverage" npm run test:coverage

echo
if [ "$FAILED" -ne 0 ]; then
  echo "RESULT: one or more gates FAILED. See the output above."
  exit 1
fi
echo "RESULT: all gates passed."
