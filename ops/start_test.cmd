@echo off
setlocal enabledelayedexpansion

REM ops\start_test.cmd
REM REA Capital Trading Engine — TEST launcher (CMD)
REM Starts guarded wrapper in TEST mode with a deterministic entrypoint.

echo.
echo === REA START TEST (CMD) ===
echo Repo: %CD%
echo.

REM Ensure repo root
if not exist run_live_guarded.py (
  echo ABORT: run_live_guarded.py not found. Run this from repo root.
  exit /b 2
)

REM Ensure runtime dir exists
if not exist runtime (
  mkdir runtime
)

REM Authoritative TEST settings
set REA_ENGINE_ENTRYPOINT=engine.run_engine:main
set REA_ENGINE_MODE=TEST

echo REA_ENGINE_ENTRYPOINT=%REA_ENGINE_ENTRYPOINT%
echo REA_ENGINE_MODE=%REA_ENGINE_MODE%
echo.

python run_live_guarded.py
set EXITCODE=%ERRORLEVEL%

echo.
echo === REA START TEST DONE === exitCode=%EXITCODE%
exit /b %EXITCODE%
