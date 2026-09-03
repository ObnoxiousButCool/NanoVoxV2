# Deploying NanoVox

One process serves the whole application — the API and the frontend, on one
port. There is no web server to configure, no CORS to get right and no second
origin, because there is only one.

## Deploy

**Windows**, from an **elevated** PowerShell:

```powershell
git clone <repo-url> C:\NanoVox
cd C:\NanoVox
.\scripts\deploy.ps1
```

**macOS**, with `sudo` — the service is a LaunchDaemon in `/Library/LaunchDaemons`:

```bash
git clone <repo-url> ~/NanoVox
cd ~/NanoVox
sudo ./scripts/deploy.sh
```

That is the whole deployment. The script installs dependencies, migrates the
database, builds the frontend, registers a startup task and verifies the result,
printing the URL to open.

## Update

```powershell
cd C:\NanoVox
git pull
.\scripts\deploy.ps1
```

```bash
cd ~/NanoVox
git pull
sudo ./scripts/deploy.sh
```

Same script. Every step is idempotent, so running it again is the update path.

## Prerequisites

Installed once on the machine, nothing else:

- **Python 3.10, 3.11 or 3.12** — Windows: python.org, ticking *Add to PATH* and
  *py launcher*. macOS: `brew install python@3.12`.
- **Node 20+** — nodejs.org, or `brew install node`.
- **Git**.

The script checks all three and stops with an actionable message if one is
missing.

## Options

| | |
|---|---|
| Windows | macOS | |
|---|---|---|
| `-Port 8080` | `--port 8080` | Listen on a different port. Default 8000. |
| `-BindAddress 127.0.0.1` | `--bind 127.0.0.1` | Reachable only from this machine. Default `0.0.0.0`. |
| `-NoService` | `--no-service` | Set everything up but do not register the service. Prints the command to run it in the foreground. Also the only mode needing no elevation. |

```powershell
.\scripts\deploy.ps1 -Port 8080 -BindAddress 127.0.0.1
```

```bash
./scripts/deploy.sh --port 8080 --bind 127.0.0.1
```

## Configuration

The script creates `Code\Backend\.env` from `.env.example` on the first run and
**leaves it alone afterwards**, except for `APP_HOST`, `APP_PORT` and `APP_ENV`,
which it owns.

Edit that file to set anything else, then re-run the script (or restart the
task) to apply it:

```ini
LLM_PROVIDER=openai            # ollama | openai | anthropic
OPENAI_API_KEY=sk-...          # only if a cloud provider is used
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Everything else has a working default resolved from the repository's own
location, so paths do not need setting.

**Config files stay editable.** `Code\Backend\config\*.yaml` hold the
vocabularies, scoring rubric and dashboard rules. Change a label or a threshold
there and restart — no rebuild. Changing a category's `code` rather than its
`label` orphans every stored call and needs the corpus re-running.

## Managing it

```powershell
Stop-ScheduledTask  -TaskName 'NanoVox'
Start-ScheduledTask -TaskName 'NanoVox'
Get-ScheduledTaskInfo -TaskName 'NanoVox'
```

```bash
sudo launchctl bootout   system/com.technossus.nanovox
sudo launchctl bootstrap system /Library/LaunchDaemons/com.technossus.nanovox.plist
sudo launchctl print     system/com.technossus.nanovox | head
```

Logs are in `Logs\`:

| file | contents |
|---|---|
| `nanovox-app.log` | startup, errors, configuration |
| `nanovox-access.log` | one line per request |
| `nanovox-llm-audit.log` | every model call, with tokens and outcome |

## Firewall

`0.0.0.0` binds all interfaces, but Windows still blocks the port. Once:

```powershell
New-NetFirewallRule -DisplayName "NanoVox" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

macOS has no equivalent step: its firewall prompts on the first bind, or is off.
If the application firewall is on and the prompt was declined, allow the Python
binary under **System Settings → Network → Firewall → Options**.

## Backups

`Data\nanovox.db` is the entire application state. Copy it — plus any `-wal` and
`-shm` siblings, or stop the task first so they are folded back in — before any
update that migrates the schema.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Run this from an elevated PowerShell" | Registering a SYSTEM task needs admin. Elevate, or use `-NoService`. |
| "No Python 3.10-3.12 found" | Not installed, or installed without the py launcher. `py -0` lists what is registered. |
| Script ends "did not answer within 20s" | Read `Logs\nanovox-app.log`; a configuration error is logged with the offending key. |
| `npm ci` fails with EPERM | Something is holding `node_modules` — usually a dev server. Stop it and re-run. |
| Provider list slow, one shows unavailable | A provider is unreachable. Bounded by `LLM_PROBE_TIMEOUT_SECONDS`, default 5. Others still work. |
| Reachable locally, not from other machines | Firewall rule missing, or the bind address was set to `127.0.0.1`. |
| macOS: "Registering the service ... needs root" | Run with `sudo`, or pass `--no-service`. |
| macOS: `bad interpreter: ... bash^M` | The script was checked out with CRLF endings. `.gitattributes` pins `*.sh` to LF; re-clone or run `dos2unix scripts/deploy.sh`. |

## Before going live

- [ ] API keys set in `.env`, which is git-ignored — never commit it
- [ ] HTTPS in front of it if reachable beyond a trusted network; transcripts are
      member health conversations, and the API sends them to the selected provider
- [ ] A billable provider is the default only if intended — a corpus run is
      100 calls × 5 layers = **500 model calls**
- [ ] `Data\nanovox.db` included in the machine's backup schedule

---

## Appendix: putting IIS in front

Not required. Add it only if policy demands IIS terminate connections, or the
machine already serves other sites on port 80. Install **URL Rewrite** and
**Application Request Routing**, point a site at any empty folder, and give it a
single rule:

```xml
<rule name="NanoVox" stopProcessing="true">
  <match url="(.*)" />
  <action type="Rewrite" url="http://127.0.0.1:8000/{R:1}" />
</rule>
```

Then run the app with `-BindAddress 127.0.0.1` so it is reachable only through
IIS. No `web.config` SPA rule is needed — the application handles client-side
routes itself.

**Set `responseBufferLimit` to `0` on that rule.** The corpus screen consumes
Server-Sent Events, and ARR buffers responses by default, which makes run
progress arrive in bursts or not at all.
