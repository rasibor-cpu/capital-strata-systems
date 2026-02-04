@echo off
setlocal

REM ops\kill_now.cmd
REM Creates runtime\kill.switch to force engine stop.

echo.
echo === REA KILL NOW (CMD) ===

if not exist runtime (
  mkdir runtime
)

echo kill> runtime\kill.switch

echo KILL SET: runtime\kill.switch
echo If the engine is running, it should stop on its next gate/check.
