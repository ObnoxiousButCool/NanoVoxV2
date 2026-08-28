@echo off
setlocal enabledelayedexpansion

rem Runs every quality gate the CI pipeline runs, in the same order.
rem Anything that fails here fails the build. Run this before committing.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\Code\Backend"
set "FRONTEND=%ROOT%\Code\Frontend"
set "FAILED="

echo === NanoVox verification ===

if not exist "%BACKEND%\.venv" (
    echo ERROR: backend virtual environment missing. Run scripts\start.bat first.
    exit /b 1
)

set "PY=%BACKEND%\.venv\Scripts\python.exe"

echo.
echo --- Backend: format ---
pushd "%BACKEND%"
"%PY%" -m ruff format --check .
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: lint ---
"%PY%" -m ruff check .
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: types ---
"%PY%" -m mypy
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: architecture contracts ---
"%BACKEND%\.venv\Scripts\lint-imports.exe"
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: tests and coverage ---
"%PY%" -m pytest --cov
if errorlevel 1 set "FAILED=1"
popd

echo.
echo --- Frontend: lint ---
pushd "%FRONTEND%"
call npm run lint
if errorlevel 1 set "FAILED=1"

echo.
echo --- Frontend: types ---
call npm run typecheck
if errorlevel 1 set "FAILED=1"

echo.
echo --- Frontend: tests and coverage ---
call npm run test:coverage
if errorlevel 1 set "FAILED=1"
popd

echo.
if defined FAILED (
    echo RESULT: one or more gates FAILED. See the output above.
    exit /b 1
)
echo RESULT: all gates passed.
endlocal
