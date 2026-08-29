# Deploying NanoVox to 10.30.1.34

Frontend on **IIS**, backend as a **standalone Windows executable** (PyInstaller),
supervised by **Task Scheduler** — no NSSM, no service wrapper.

Target host: `10.30.1.34` (Windows). Everything below is run on that machine
unless a step says *build machine*.

---

## 0. What you are deploying

| Component | Runs as | Listens on | Served from |
|---|---|---|---|
| Frontend | Static files | port 80 (IIS) | `C:\inetpub\NanoVox` |
| Backend | `nanovox-api.exe` | `10.30.1.34:8000` | `C:\NanoVox\api` |
| Database | SQLite file | — | `C:\NanoVox\data\nanovox.db` |
| Ollama *(optional)* | Existing service | `127.0.0.1:11434` | already on this VM |

The frontend is a single-page app that calls the backend across an origin
boundary, so the backend's `CORS_ORIGINS` must name the IIS origin exactly.
Section 8 covers an optional reverse-proxy setup that removes CORS entirely.

---

## 1. Prerequisites on the VM

Install once:

- **IIS** with **Static Content** and **URL Rewrite 2.1**
  ([download](https://www.iis.net/downloads/microsoft/url-rewrite)).
  URL Rewrite is **not optional** — see section 6.
- **Visual C++ Redistributable 2015–2022 (x64)**. PyInstaller binaries need it.
- Nothing else. Python and Node are **not** required on the VM; both artefacts
  are built elsewhere.

Enable the IIS features from an elevated PowerShell:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole, IIS-StaticContent, IIS-DefaultDocument, IIS-HttpErrors, IIS-HttpLogging -All
```

Open the API port:

```powershell
New-NetFirewallRule -DisplayName "NanoVox API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## 2. Build the backend executable *(build machine)*

Run from `Code\Backend` on a machine with the project's Python 3.10 virtualenv.

### 2.1 Install PyInstaller

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller
```

### 2.2 Create the entry point

The app is normally started by the `uvicorn` CLI, which a frozen binary cannot
use. Create `Code\Backend\serve.py`:

```python
"""Console entry point for the packaged backend.

PyInstaller freezes a callable, not a command line, so uvicorn is started
programmatically. Reload is deliberately absent: it forks a second process,
which a Windows service context cannot supervise.
"""

from __future__ import annotations

import sys

import uvicorn

from frameworks_drivers.main import create_app
from infrastructure.config.settings import get_settings


def main() -> int:
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,  # The application configures its own JSON logging.
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 2.3 Create the migration entry point

Schema changes must be applied on the VM, and there is no Python there. Create
`Code\Backend\migrate.py`:

```python
"""Applies database migrations, using the same configuration the app reads."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> int:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    config = Config()
    config.set_main_option("script_location", str(root / "migrations"))
    # The URL is not set here: migrations/env.py reads it from the same
    # settings object the application uses, so the two cannot disagree.
    command.upgrade(config, "head")
    print("Migrations applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 2.4 Build both binaries

The prompt templates are loaded from a path derived from `__file__`, so they
must be bundled. The YAML config files are **not** bundled — they stay editable
on the VM (section 4.3).

```powershell
.venv\Scripts\pyinstaller.exe --onefile --name nanovox-api `
  --add-data "infrastructure/llm/prompts;infrastructure/llm/prompts" `
  serve.py
```

```powershell
.venv\Scripts\pyinstaller.exe --onefile --name nanovox-migrate `
  --add-data "infrastructure/persistence/migrations;migrations" `
  migrate.py
```

Both appear in `Code\Backend\dist\`.

> **If the build fails on a missing module**, add `--hidden-import`. The usual
> suspects are `aiosqlite`, `uvicorn.loops.auto`, `uvicorn.protocols.http.auto`
> and `uvicorn.lifespan.on`. Example:
> `--hidden-import aiosqlite --hidden-import uvicorn.loops.auto`

Smoke-test on the build machine before copying anything:

```powershell
dist\nanovox-api.exe
```

It should log `Application startup complete`. Stop it with Ctrl+C.

---

## 3. Build the frontend *(build machine)*

**`VITE_API_BASE_URL` is compiled into the bundle.** It is read at build time,
not at runtime, so it must be correct *before* you build. Editing it afterwards
does nothing — you would have to rebuild.

From `Code\Frontend`:

```powershell
Set-Content -Path .env.production -Encoding utf8 -Value @'
VITE_API_BASE_URL=http://10.30.1.34:8000/api/v1
VITE_APP_NAME=NanoVox
'@
```

```powershell
npm ci
npm run build
```

The output is `Code\Frontend\dist\`. Confirm the address was baked in — this
must print at least one match:

```powershell
Select-String -Path dist\assets\*.js -Pattern "10.30.1.34" | Select-Object -First 1
```

If it prints nothing, the build used the wrong env file. Fix and rebuild.

---

## 4. Lay out the backend on the VM

### 4.1 Create the directories

```powershell
New-Item -ItemType Directory -Force C:\NanoVox\api, C:\NanoVox\data, C:\NanoVox\logs, C:\NanoVox\config, C:\NanoVox\samples
```

### 4.2 Copy the artefacts

| From (build machine) | To (VM) |
|---|---|
| `Code\Backend\dist\nanovox-api.exe` | `C:\NanoVox\api\` |
| `Code\Backend\dist\nanovox-migrate.exe` | `C:\NanoVox\api\` |
| `Code\Backend\config\*.yaml` | `C:\NanoVox\config\` |
| `Samples\call_*.md` | `C:\NanoVox\samples\` |
| `Code\Frontend\dist\*` | `C:\inetpub\NanoVox\` |

### 4.3 Why the YAML files sit outside the executable

`taxonomy.yaml`, `rubric.yaml` and `dashboard.yaml` define the vocabularies and
scoring rules. Keeping them beside the exe means a label or threshold can be
changed by editing a file and restarting — no rebuild, no redeploy. Bundling
them would forfeit that.

**Editing them requires a restart.** They are read once at startup.

Changing a category **`label`** is display-only and safe. Changing a category
**`code`** orphans every stored call and requires re-running the corpus.

---

## 5. Configure the backend

### 5.1 Configuration comes from environment variables, not `.env`

This is the single most common way to get this deployment wrong.

The app resolves its `.env` location from the source tree's position on disk.
Inside a PyInstaller binary that path points into a temporary extraction folder,
so **a `.env` file placed next to `nanovox-api.exe` is silently ignored**.

Real environment variables are read normally and take precedence, so set
everything as **machine-level** variables. This is also better practice: the API
keys never land in a file next to the web root.

### 5.2 Set the variables

Run once, elevated. Substitute your real keys.

```powershell
$vars = @{
  'APP_ENV'                   = 'prod'
  'APP_HOST'                  = '0.0.0.0'
  'APP_PORT'                  = '8000'
  'API_PREFIX'                = '/api/v1'
  'CORS_ORIGINS'              = 'http://10.30.1.34'
  'DATABASE_URL'              = 'sqlite+aiosqlite:///C:/NanoVox/data/nanovox.db'
  'TAXONOMY_PATH'             = 'C:/NanoVox/config/taxonomy.yaml'
  'RUBRIC_PATH'               = 'C:/NanoVox/config/rubric.yaml'
  'DASHBOARD_PATH'            = 'C:/NanoVox/config/dashboard.yaml'
  'CORPUS_PATH'               = 'C:/NanoVox/samples'
  'LOG_DIR'                   = 'C:/NanoVox/logs'
  'LOG_LEVEL'                 = 'INFO'
  'LOG_FORMAT'                = 'json'
  'LOG_TO_CONSOLE'            = 'false'
  'LLM_PROVIDER'              = 'openai'
  'LLM_TIMEOUT_SECONDS'       = '120'
  'LLM_PROBE_TIMEOUT_SECONDS' = '5'
  'LLM_MAX_RETRIES'           = '2'
  'LLM_MAX_OUTPUT_TOKENS'     = '4096'
  'OPENAI_MODEL'              = 'gpt-4o-mini'
  'ANTHROPIC_MODEL'           = 'claude-opus-5'
  'OLLAMA_BASE_URL'           = 'http://127.0.0.1:11434'
  'OLLAMA_MODEL'              = 'qwen2.5:7b-instruct'
  'OPENAI_API_KEY'            = 'sk-REPLACE-ME'
  'ANTHROPIC_API_KEY'         = 'sk-ant-REPLACE-ME'
  'CORPUS_RUN_CONCURRENCY'    = '2'
}
foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k], 'Machine') }
```

Then **open a new PowerShell window** — the current one will not see them.

### 5.3 Points that bite

- **`DATABASE_URL` uses forward slashes.** SQLAlchemy URLs are POSIX-style on
  every platform. `C:\NanoVox\...` will not parse.
- **`CORS_ORIGINS` must match the browser's address exactly** — scheme, host and
  port, with no trailing slash. If you reach the site as
  `http://nanovox.internal`, that is what belongs here, not the IP. Multiple
  origins are comma-separated.
- **`APP_HOST=0.0.0.0`**, not `127.0.0.1`. Bound to loopback, the API is
  unreachable from any browser but one running on the VM itself.
- **`APP_ENV=prod` disables `/docs` and `/openapi.json`.** Intentional. Set
  `dev` temporarily if you need the interactive docs to diagnose something.
- **Ollama is on this VM**, so `127.0.0.1` is right. If it is not running,
  leave the variable as it is — the provider list reports it unavailable in
  5 seconds and the other providers still work.

---

## 6. Publish the frontend on IIS

### 6.1 Create the site

```powershell
Import-Module WebAdministration
New-WebAppPool -Name NanoVox
# No managed code: this serves static files only.
Set-ItemProperty IIS:\AppPools\NanoVox -Name managedRuntimeVersion -Value ''
New-Website -Name NanoVox -Port 80 -PhysicalPath C:\inetpub\NanoVox -ApplicationPool NanoVox -Force
```

If the Default Web Site already holds port 80, stop it:
`Stop-Website -Name "Default Web Site"`.

### 6.2 The SPA fallback rule — required

The app uses `BrowserRouter`, so `/calls`, `/brokers` and `/corpus` are
client-side routes with no file behind them. Requested directly — or after a
refresh — IIS returns **404** unless it is told to serve `index.html` instead.

Create `C:\inetpub\NanoVox\web.config`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <!-- Client-side routes have no file behind them. Anything that is not a
             real file or directory is handed to the SPA, which reads the path
             itself. Without this, refreshing /calls returns 404. -->
        <rule name="SPA fallback" stopProcessing="true">
          <match url=".*" />
          <conditions logicalGrouping="MatchAll">
            <add input="{REQUEST_FILENAME}" matchType="IsFile" negate="true" />
            <add input="{REQUEST_FILENAME}" matchType="IsDirectory" negate="true" />
          </conditions>
          <action type="Rewrite" url="/index.html" />
        </rule>
      </rules>
    </rewrite>
    <staticContent>
      <remove fileExtension=".json" />
      <mimeMap fileExtension=".json" mimeType="application/json" />
      <!-- Hashed asset filenames change on every build, so they are safe to
           cache hard. index.html must not be, or clients pin to an old bundle. -->
      <clientCache cacheControlMode="UseMaxAge" cacheControlMaxAge="365.00:00:00" />
    </staticContent>
  </system.webServer>
</configuration>
```

Then stop `index.html` being cached, or a redeploy will not reach anyone:

```powershell
Add-WebConfigurationProperty -PSPath 'IIS:\Sites\NanoVox' -Filter "system.webServer/staticContent" -Name "." -Value @{fileExtension='.html'; mimeType='text/html'} -ErrorAction SilentlyContinue
Set-WebConfigurationProperty -PSPath 'IIS:\Sites\NanoVox' -Filter "system.webServer/staticContent/clientCache" -Name "cacheControlMode" -Value "DisableCache" -Location "index.html"
```

---

## 7. Run the backend without NSSM

### 7.1 Apply migrations first

```powershell
C:\NanoVox\api\nanovox-migrate.exe
```

Expect `Migrations applied.` This creates `nanovox.db` if absent. Re-run it after
every deployment that includes schema changes; it is a no-op when already
current.

### 7.2 Register the startup task

Task Scheduler supervises the process using only built-in Windows features.

```powershell
$action  = New-ScheduledTaskAction -Execute 'C:\NanoVox\api\nanovox-api.exe' -WorkingDirectory 'C:\NanoVox\api'
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'NanoVox API' -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Force
```

`-ExecutionTimeLimit ([TimeSpan]::Zero)` means *no limit*. Without it the task
is killed after 3 days, and a corpus run started near that boundary dies with it.

Start it now rather than waiting for a reboot:

```powershell
Start-ScheduledTask -TaskName 'NanoVox API'
```

### 7.3 Grant write access

The task runs as `SYSTEM`, which can already write these. If you switch it to a
service account, grant that account **Modify** on:

- `C:\NanoVox\data` — SQLite writes `nanovox.db`, plus `-wal` and `-shm`
  siblings. Permission on the file alone is not enough; it needs the directory.
- `C:\NanoVox\logs` — daily rotation creates new files.

### 7.4 Managing it

```powershell
Get-ScheduledTaskInfo -TaskName 'NanoVox API'   # last result, last run time
Stop-ScheduledTask   -TaskName 'NanoVox API'
Start-ScheduledTask  -TaskName 'NanoVox API'
```

A restart is required after editing any YAML config or environment variable.

---

## 8. Optional: put the API behind IIS (no CORS)

Steps 1–7 leave the browser talking to two origins, which is why `CORS_ORIGINS`
matters. If you would rather expose only port 80, install
**Application Request Routing** and proxy `/api` to the backend.

Add inside `<rules>` in `web.config`, **above** the SPA fallback rule:

```xml
<rule name="API proxy" stopProcessing="true">
  <match url="^api/(.*)" />
  <action type="Rewrite" url="http://127.0.0.1:8000/api/{R:1}" />
</rule>
```

Then:

- Enable the proxy: `Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter "system.webServer/proxy" -Name "enabled" -Value "True"`
- Rebuild the frontend with `VITE_API_BASE_URL=http://10.30.1.34/api/v1` (no port).
- Set `APP_HOST=127.0.0.1` and close port 8000 in the firewall.
- `CORS_ORIGINS` becomes irrelevant — same origin.

**Do not enable this for the corpus progress stream without testing it.** The run
screen consumes Server-Sent Events, and ARR buffers responses by default, which
makes progress arrive in bursts or not at all. If you proxy, set
`responseBufferLimit` to `0` on the API route.

---

## 9. Verify the deployment

Run on the VM, then repeat from another machine.

```powershell
# 1. API is alive
curl.exe -s http://10.30.1.34:8000/api/v1/health

# 2. Configuration resolved — paths, not defaults
curl.exe -s http://10.30.1.34:8000/api/v1/corpus

# 3. Providers are reachable (should answer in ~5s, not 25s)
Measure-Command { curl.exe -s http://10.30.1.34:8000/api/v1/providers } | Select-Object TotalSeconds

# 4. Frontend loads
curl.exe -s -o NUL -w "%{http_code}`n" http://10.30.1.34/

# 5. SPA fallback works — this is the one people forget
curl.exe -s -o NUL -w "%{http_code}`n" http://10.30.1.34/calls
```

Expected: `200` for every one, `/api/v1/corpus` reporting
`"total_calls": 100` from `C:\NanoVox\samples`, and step 5 returning **200**,
not 404.

Then open `http://10.30.1.34/` in a browser and confirm:

- The Overview page renders charts rather than an error panel.
- The Corpus screen's provider dropdown populates (this proves CORS is right —
  a CORS failure shows as "The NanoVox API could not be reached").
- Refreshing while on `/brokers` stays on the page.

---

## 10. Redeploying

| Change | Steps |
|---|---|
| Frontend only | Rebuild (§3), replace `C:\inetpub\NanoVox`, keep `web.config` |
| Backend only | Rebuild (§2.4), `Stop-ScheduledTask`, replace the exe, `Start-ScheduledTask` |
| Schema change | As above, plus `nanovox-migrate.exe` before starting |
| YAML config | Edit in `C:\NanoVox\config`, restart the task |
| API key or setting | Set the machine variable, restart the task |

**Back up `C:\NanoVox\data\nanovox.db` before any deployment that migrates.**
Copy the `-wal` and `-shm` files too, or stop the task first so they are folded
back in.

---

## 11. Troubleshooting

| Symptom | Cause |
|---|---|
| "The NanoVox API could not be reached" | `CORS_ORIGINS` does not match the browser's address exactly, or the API is down. Check the browser console for a CORS error before assuming the API is down. |
| Site loads, every API call fails | The frontend was built with the wrong `VITE_API_BASE_URL`. It is compiled in — rebuild, do not edit files on the VM. |
| 404 on refresh, fine when navigating | URL Rewrite is missing or `web.config` was overwritten by a redeploy. |
| Exe starts then exits immediately | Read `C:\NanoVox\logs\nanovox-app.log`. A configuration error is logged with the offending key before exit. |
| `no such table: analysis_runs` | Migrations were never applied. Run `nanovox-migrate.exe`. |
| `unable to open database file` | The account lacks **Modify** on `C:\NanoVox\data` — the directory, not just the file. |
| Provider list takes ~25s | Predates `LLM_PROBE_TIMEOUT_SECONDS`; confirm the variable is set and the process was restarted. |
| Corpus shows 0 calls | `CORPUS_PATH` is wrong or the `call_*.md` files were not copied. |
| Nothing in the logs at all | `LOG_DIR` is not writable, or `LOG_ENABLED` was set to `false`. |

Logs, all under `C:\NanoVox\logs`:

- `nanovox-app.log` — startup, errors, configuration
- `nanovox-access.log` — one line per request
- `nanovox-llm-audit.log` — every model call, with token counts and outcome

---

## 12. Before going live

- [ ] `APP_ENV=prod` (disables interactive API docs)
- [ ] API keys set as **machine** environment variables, not in any file under
      `C:\inetpub`
- [ ] `C:\inetpub\NanoVox` contains no `.env`, `.map` or source files
- [ ] HTTPS configured if the site is reachable beyond this subnet — transcripts
      are member health conversations, and the API sends them to whichever
      provider is selected
- [ ] A billable provider is the default only if that is intended; a corpus run
      is 100 calls × 5 layers = **500 model calls**
- [ ] `nanovox.db` included in the machine's backup schedule
