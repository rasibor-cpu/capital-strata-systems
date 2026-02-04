@echo off
setlocal

REM ops\clear_kill.cmd
REM Removes runtime\kill.switch so engine can run again.

echo.
echo === REA CLEAR KILL (CMD) ===

if exist runtime\kill.switch (
  del /f /q runtime\kill.switch
  echo KILL CLEARED: runtime\kill.switch
) else (
  echo KILL NOT PRESENT: runtime\kill.switch
)
