@echo off
setlocal

title Capital Strata Systems Mobile Server
set "CSS_ROOT=%~dp0.."
cd /d "%CSS_ROOT%"

echo Capital Strata Systems mobile server
echo.
echo Open this from your phone on the same network:
for /f "tokens=14" %%i in ('ipconfig ^| findstr /i "IPv4"') do echo   http://%%i:8090
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
) else (
    python -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
)

set "CSS_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%CSS_EXIT_CODE%"=="0" echo CSS mobile server exited with code %CSS_EXIT_CODE%.
pause
exit /b %CSS_EXIT_CODE%
