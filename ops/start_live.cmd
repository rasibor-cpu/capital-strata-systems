@echo off
setlocal enabledelayedexpansion

REM ops\start_live.cmd
REM REA Capital Trading Engine — LIVE launcher (CMD)
REM Fail-closed: requires explicit typed confirmation phrase.
REM Blocks if runtime\kill.switch exists.

echo.
echo === REA START LIVE (CMD) ===
echo Repo: %CD%
echo.

if not exist run_live_guarded.py (
  echo ABORT: run_live_guarded.py not found. Run this from repo root.
  exit /b 2
)

if exist runtime\kill.switch (
  echo ABORT: kill switch is set (runtime\kill.switch). Clear it first.
  exit /b 3
)

if not exist runtime (
  mkdir runtime
)

set REA_ENGINE_ENTRYPOINT=engine.run_engine:main
set REA_ENGINE_MODE=LIVE

echo REA_ENGINE_ENTRYPOINT=%REA_ENGINE_ENTRYPOINT%
echo REA_ENGINE_MODE=%REA_ENGINE_MODE%
echo.

set PHRASE=I UNDERSTAND LIVE TRADING RISK
set /p INPUTPHRASE=TYPE EXACTLY: %PHRASE% :

if NOT "%INPUTPHRASE%"=="%PHRASE%" (
  echo ABORT: confirmation phrase mismatch. LIVE not started.
  exit /b 4
)

echo.
echo CONFIRMED. Starting LIVE guarded engine...
python run_live_guarded.py
set EXITCODE=%ERRORLEVEL%

echo.
echo === REA START LIVE DONE === exitCode=%EXITCODE%
exit /b %EXITCODE%
