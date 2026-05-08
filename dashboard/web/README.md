# CSS Institutional Web Dashboard

This package provides a read-only institutional web dashboard surface for CSS.

The web layer is intentionally fed by:

```text
DashboardHydrationCoordinator -> DashboardState -> frontend_contract -> API/websocket
```

Rules:

- No direct broker calls from the frontend.
- No credential rendering.
- DashboardState remains the canonical bridge.
- Production integrations should inject a state provider into `create_app()`.
- The default app uses deterministic demo payloads for local smoke access.

Local run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard.web.web_app:app --host 0.0.0.0 --port 8091
```
