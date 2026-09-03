#!/usr/bin/env bash
# Deploys NanoVox on this machine, and updates it. Run it again to redeploy.
#
# The macOS counterpart to deploy.ps1, doing the same seven things: check
# prerequisites, install dependencies, write the deployment's own settings,
# migrate the database, build the frontend, register a service, verify.
#
# One process serves the whole application — the API and the built frontend on
# a single port. There is no web server to configure, no CORS to get right and
# no second origin, because there is only one.
#
# Every step is idempotent, so running this after a `git pull` is the update
# path.
#
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --port 8080 --bind 127.0.0.1
#   ./scripts/deploy.sh --no-service          # set up, don't register a service
set -euo pipefail

PORT=8000
BIND=0.0.0.0
NO_SERVICE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --port)       PORT="$2"; shift 2 ;;
        --bind)       BIND="$2"; shift 2 ;;
        --no-service) NO_SERVICE=1; shift ;;
        -h|--help)    sed -n '2,17p' "$0"; exit 0 ;;
        *)            echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

# Resolved from this script's own location, so the checkout works wherever it
# lives and the script can be run from any directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/Code/Backend"
FRONTEND="$ROOT/Code/Frontend"
PYTHON="$BACKEND/.venv/bin/python"
LABEL="com.technossus.nanovox"
PLIST="/Library/LaunchDaemons/$LABEL.plist"

step() { printf '\n\033[36m=== %s\033[0m\n' "$1"; }
note() { printf '    \033[90m%s\033[0m\n' "$1"; }

OS="$(uname -s)"

# --- 1. Prerequisites ------------------------------------------------------
step 'Checking prerequisites'

# Checked before several minutes of installing and building: a LaunchDaemon is
# written to /Library, which needs root, and discovering that at the end would
# waste the whole run.
if [ "$NO_SERVICE" -eq 0 ] && [ "$OS" = "Darwin" ] && [ "$(id -u)" -ne 0 ]; then
    echo "Registering the service writes to $PLIST, which needs root." >&2
    echo "Re-run with sudo, or pass --no-service to set everything up without it:" >&2
    echo "    sudo ./scripts/deploy.sh" >&2
    echo "    ./scripts/deploy.sh --no-service" >&2
    exit 1
fi

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        # `python3` alone may be any version, so every candidate is checked
        # rather than trusted by name.
        if "$candidate" -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info < (3,13) else 1)'; then
            PYTHON_BIN="$candidate"
            note "Python $("$candidate" -c 'import platform; print(platform.python_version())') at $(command -v "$candidate")"
            break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "No Python 3.10-3.12 found. Install one (brew install python@3.12) and re-run." >&2
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo "Node.js was not found on PATH. Install Node 20+ (brew install node) and re-run." >&2
    exit 1
fi
note "Node $(node --version)"

# --- 2. Backend dependencies ----------------------------------------------
step 'Installing backend dependencies'
if [ ! -x "$PYTHON" ]; then
    note 'Creating virtual environment'
    "$PYTHON_BIN" -m venv "$BACKEND/.venv"
fi
"$PYTHON" -m pip install --upgrade pip --quiet
"$PYTHON" -m pip install -r "$BACKEND/requirements.txt" --quiet

# --- 3. Configuration ------------------------------------------------------
step 'Configuring'
ENV_FILE="$BACKEND/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$BACKEND/.env.example" "$ENV_FILE"
    note "Created $ENV_FILE from the template"
    note 'Set OPENAI_API_KEY / ANTHROPIC_API_KEY in it if you intend to use a cloud provider.'
else
    note "Keeping the existing $ENV_FILE"
fi

# Written every time: these three are the deployment's own settings, and a stale
# port or bind address in .env would silently override the arguments given here.
#
# Done in Python rather than sed: BSD sed on macOS and GNU sed on Linux disagree
# about in-place editing, and this file holds API keys — a portable edit is worth
# more than a clever one-liner.
"$PYTHON" - "$ENV_FILE" "$BIND" "$PORT" <<'PY'
import pathlib, re, sys

path, bind, port = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
deployed = {"APP_HOST": bind, "APP_PORT": port, "APP_ENV": "prod"}
lines = path.read_text(encoding="utf-8").splitlines()

for key, value in deployed.items():
    replacement = f"{key}={value}"
    for index, line in enumerate(lines):
        if re.match(rf"\s*{key}\s*=", line):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
note "APP_HOST=$BIND  APP_PORT=$PORT  APP_ENV=prod"

# --- 4. Database -----------------------------------------------------------
step 'Applying database migrations'
# SQLite creates the file on first connect but not the tables in it. A no-op
# once the schema is current.
(cd "$BACKEND" && "$PYTHON" -m alembic upgrade head)

# --- 5. Frontend -----------------------------------------------------------
step 'Building the frontend'
(
    cd "$FRONTEND"
    # `npm ci` is the reproducible install, but it deletes node_modules first,
    # which fails if anything is holding a file in there. Used only on a clean
    # tree; an existing one is updated in place, which needs no delete.
    if [ -f package-lock.json ] && [ ! -d node_modules ]; then
        npm ci --silent
    else
        npm install --silent
    fi
    # .env.production sets VITE_API_BASE_URL=/api/v1 — the API is this same
    # process, so the bundle is host-independent and never needs rebuilding
    # because an address changed.
    npm run build
)
[ -f "$FRONTEND/dist/index.html" ] || { echo "Frontend build produced no dist/index.html." >&2; exit 1; }
note 'Built. The API process will serve it.'

RUN_COMMAND="$PYTHON -m uvicorn frameworks_drivers.main:app --host $BIND --port $PORT"

# --- 6. Service ------------------------------------------------------------
if [ "$NO_SERVICE" -eq 1 ]; then
    step 'Skipping service registration (--no-service)'
    printf '\n\033[32mStart it in the foreground with:\033[0m\n'
    printf '    cd "%s" && %s\n\n' "$BACKEND" "$RUN_COMMAND"
    exit 0
fi

if [ "$OS" != "Darwin" ]; then
    # launchd is macOS. Rather than ship an untested systemd unit, this says so
    # and hands over the command — the rest of the deployment is already done.
    step 'Service registration is macOS-only'
    note "This is $OS, where the equivalent is a systemd unit rather than launchd."
    printf '\n    Everything else is deployed. Run it with:\n'
    printf '    cd "%s" && %s\n\n' "$BACKEND" "$RUN_COMMAND"
    exit 0
fi

step 'Registering the launch daemon'
# A LaunchDaemon rather than a LaunchAgent: an agent only runs while a user is
# logged in, which is not what a server does. KeepAlive restarts the process if
# it dies; RunAtLoad starts it at boot.
mkdir -p "$ROOT/Logs"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>frameworks_drivers.main:app</string>
        <string>--host</string>
        <string>$BIND</string>
        <string>--port</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BACKEND</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$ROOT/Logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$ROOT/Logs/launchd-stderr.log</string>
</dict>
</plist>
PLIST_EOF

chown root:wheel "$PLIST"
chmod 644 "$PLIST"

# Unload before load: a redeploy must not leave the previous build running.
launchctl bootout "system/$LABEL" 2>/dev/null || true
sleep 2
launchctl bootstrap system "$PLIST"
launchctl kickstart -k "system/$LABEL"

# --- 7. Verify -------------------------------------------------------------
step 'Verifying'
if [ "$BIND" = "0.0.0.0" ]; then PROBE=127.0.0.1; else PROBE="$BIND"; fi
BASE="http://$PROBE:$PORT"

READY=0
for _ in $(seq 1 20); do
    sleep 1
    if curl -fsS --max-time 3 "$BASE/api/v1/health" >/dev/null 2>&1; then READY=1; break; fi
done
if [ "$READY" -eq 0 ]; then
    echo "The application did not answer on $BASE within 20s." >&2
    echo "Check $ROOT/Logs/nanovox-app.log and $ROOT/Logs/launchd-stderr.log." >&2
    exit 1
fi
note "API healthy at $BASE/api/v1/health"

# The one check that catches a broken deployment which still looks fine: a
# client-side route has no file behind it, so it proves the SPA fallback works.
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE/calls")"
[ "$CODE" = "200" ] || { echo "Client-side route /calls returned $CODE." >&2; exit 1; }
note 'Client-side routing works'

printf '\n\033[32mNanoVox is running.\033[0m\n'
printf '    Local:   %s\n' "$BASE"
for interface in en0 en1 en2; do
    address="$(ipconfig getifaddr "$interface" 2>/dev/null || true)"
    [ -n "$address" ] && printf '    Network: http://%s:%s\n' "$address" "$PORT"
done
cat <<SUMMARY

    Manage:  sudo launchctl bootout system/$LABEL
             sudo launchctl bootstrap system $PLIST
    Status:  sudo launchctl print system/$LABEL | head
    Logs:    $ROOT/Logs
    Update:  git pull && sudo ./scripts/deploy.sh

SUMMARY
