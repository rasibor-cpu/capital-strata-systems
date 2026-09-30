@echo off
setlocal

title Capital Strata Systems Web UAT Server
set "CSS_ROOT=%~dp0.."
cd /d "%CSS_ROOT%"

rem DEVELOPMENT/UAT ONLY. Serves the operator web dashboard over plain HTTP on
rem this machine only (127.0.0.1), so session cookies are not marked Secure
rem (CSS_ENV=development). A real deployment must terminate TLS and must not
rem set CSS_ENV=development. No broker execution, charging or money movement
rem is reachable from this server.
set "CSS_ENV=development"
if not defined CSS_COMMERCIAL_DB set "CSS_COMMERCIAL_DB=%CSS_ROOT%\data\css_commercial_uat.sqlite3"
if not defined CSS_AUTH_AUDIT_DB set "CSS_AUTH_AUDIT_DB=%CSS_ROOT%\data\css_auth_audit.sqlite3"

echo Capital Strata Systems web UAT server
echo   Open: http://127.0.0.1:8000/login
echo   Stop: press Ctrl+C in this window
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn dashboard.web.web_app:app --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn dashboard.web.web_app:app --host 127.0.0.1 --port 8000
)

set "CSS_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%CSS_EXIT_CODE%"=="0" echo CSS web UAT server exited with code %CSS_EXIT_CODE%.
pause
exit /b %CSS_EXIT_CODE%
