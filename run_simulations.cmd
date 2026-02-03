@echo off
setlocal

REM Always run from repo root
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found on PATH.
  echo Install Python 3.14+ and reopen CMD.
  exit /b 1
)

echo Running profit-taking simulator (governance lock verification)...
python -m simulations.profit_taking_simulator
echo.
echo Done.
endlocal

