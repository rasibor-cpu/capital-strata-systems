# CSS Mobile Web

The mobile entry is a FastAPI/PWA shell for phone access to CSS.

Start it from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
```

Then open `http://<your-pc-ip>:8090` from the phone while it is on the same network.

This mobile surface uses the same CSS sign-on and password rules as the desktop dashboard. Authenticated users can access the dashboard and submit mobile trade tickets. Live broker tickets still route through CSS credentials, broker availability, live-order flags, explicit `EXECUTE` confirmation, and audit logging.
