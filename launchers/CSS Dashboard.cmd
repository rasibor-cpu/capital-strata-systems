@echo off
setlocal

title Capital Strata Systems
set "CSS_ROOT=%~dp0.."
cd /d "%CSS_ROOT%"

set "CSS_AUTH_UI=gui"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\css_live_dashboard.py
) else (
    python scripts\css_live_dashboard.py
)

set "CSS_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%CSS_EXIT_CODE%"=="0" echo CSS exited with code %CSS_EXIT_CODE%.
pause
exit /b %CSS_EXIT_CODE%
