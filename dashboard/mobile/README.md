# CSS Mobile Web

The mobile entry is a FastAPI/PWA shell for phone access to CSS.

Start it from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
```

Then open `http://<your-pc-ip>:8090` from the phone while it is on the same network.

This mobile surface is intentionally read-only. It uses the same CSS sign-on and password rules as the desktop dashboard, but it does not expose live trading actions.
