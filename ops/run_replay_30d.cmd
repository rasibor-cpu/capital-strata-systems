@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==========================================================
REM CSS – 30-Day Replay Runner (SAFE MODE)
REM - No brokers
REM - No live execution
REM - Deterministic logs
REM ==========================================================

cd /d %~dp0\..

REM Safety switches (must remain OFF for live)
set DEV_FORCE_ALLOW=0
set LIVE_TRADING=0
set EXECUTE_TRADES=0
set MODE=REPLAY_30D

REM Log folder
if not exist ops\logs mkdir ops\logs

REM Timestamped log
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (
  set MM=%%a
  set DD=%%b
  set YY=%%c
)
for /f "tokens=1-3 delims=:." %%h in ("%time%") do (
  set HH=%%h
  set MN=%%i
  set SS=%%j
)

set TS=%YY%-%MM%-%DD%_%HH%%MN%%SS%
set LOG=ops\logs\replay30d_%TS%.log

echo [ops] Starting 30-day replay (SAFE MODE) > "%LOG%"
echo [ops] Repo: %cd%>> "%LOG%"
echo [ops] DEV_FORCE_ALLOW=%DEV_FORCE_ALLOW%>> "%LOG%"
echo [ops] LIVE_TRADING=%LIVE_TRADING%>> "%LOG%"
echo [ops] EXECUTE_TRADES=%EXECUTE_TRADES%>> "%LOG%"
echo [ops] MODE=%MODE%>> "%LOG%"
echo.>> "%LOG%"

REM ----------------------------------------------------------
REM Run your test harness / replay driver here
REM Adjust this line if your runner is different
REM ----------------------------------------------------------
python run_engine_loop.py >> "%LOG%" 2>&1

echo.>> "%LOG%"
echo [ops] Done. Log written to %LOG%
type "%LOG%" | more

endlocal
