@echo off
setlocal

:: Determine the directory where the script is located
set "REPO_ROOT=%~dp0"

:: Remove trailing backslash if present (safe for concatenations later)
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

:: Set PYTHONPATH
set "PYTHONPATH=%REPO_ROOT%"

:: Change to repo root
cd /d "%REPO_ROOT%"

:: Launch the runtime launcher
.venv\Scripts\python.exe -m launcher.css_runtime_launcher

endlocal
