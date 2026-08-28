@echo off
setlocal enabledelayedexpansion

rem NanoVox one-shot setup + run script (Windows).
rem Clone the repo, double-click this file (or run it from a terminal) - it
rem creates the backend venv, installs backend + frontend dependencies,
rem seeds .env files from .env.example if missing, then launches both
rem servers in their own windows and opens the dashboard in your browser.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\Code\Backend"
set "FRONTEND=%ROOT%\Code\Frontend"

echo === NanoVox setup (Windows) ===

rem --- Locate a Python interpreter ---
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python was not found on PATH. Install Python 3.11+ from python.org and re-run this script.
        exit /b 1
    )
    set "PY=py"
) else (
    set "PY=python"
)

rem --- Backend: venv + dependencies ---
if not exist "%BACKEND%\.venv" (
    echo Creating backend virtual environment...
    %PY% -m venv "%BACKEND%\.venv"
)

call "%BACKEND%\.venv\Scripts\activate.bat"
echo Installing backend dependencies...
python -m pip install --upgrade pip >nul
pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo ERROR: backend dependency install failed. See output above.
    exit /b 1
)

if not exist "%BACKEND%\.env" (
    echo Creating backend\.env from .env.example - the defaults work for a local run.
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
)
call "%BACKEND%\.venv\Scripts\deactivate.bat"

rem --- Frontend: dependencies ---
where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js was not found on PATH. Install Node 18+ from nodejs.org and re-run this script.
    exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
    echo Installing frontend dependencies...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        echo ERROR: frontend dependency install failed. See output above.
        popd
        exit /b 1
    )
    popd
)

if not exist "%FRONTEND%\.env" (
    if exist "%FRONTEND%\.env.example" (
        echo Creating frontend\.env from .env.example...
        copy "%FRONTEND%\.env.example" "%FRONTEND%\.env" >nul
    )
)

rem --- Launch both servers, each in its own window ---
echo Starting backend on http://127.0.0.1:8000 ...
start "NanoVox Backend" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate.bat && python -m uvicorn frameworks_drivers.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting frontend on http://127.0.0.1:5173 ...
start "NanoVox Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo Waiting for the frontend to come up...
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo NanoVox is running in two new windows - "NanoVox Backend" and "NanoVox Frontend".
echo Close those windows (or Ctrl+C inside them) to stop the servers.
endlocal
