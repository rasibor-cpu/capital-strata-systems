# CSS Mobile Web

The mobile entry is a FastAPI/PWA shell for phone access to CSS.

Start it from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
```

Then open `http://<your-pc-ip>:8090` from the phone while it is on the same network.

## Architecture

The mobile backend connects to the unified core CSS infrastructure.

- **Frontend:** Server-side rendered HTML (`ui/ibkr/mobile.html`)
- **Backend:** FastAPI (`mobile_app.py`)
- **Execution:** Canonical (`TradeDecisionOrchestrator` -> `ExecutionGate` -> `TradeLedger`)

**Important Security Note**: Direct broker REST execution has been eradicated from the mobile interface. All trades are routed through the central, institutional governance gates. Default state is strictly `MOBILE_READ_ONLY`.

This mobile surface uses the same CSS sign-on and password rules as the desktop dashboard. Authenticated users see only the actions allowed by their CSS role.

- `/controls` lets a `SUPER_USER` switch mobile runtime between paper/live, enable or disable order submission, and set the displayed engine mode.
- `/users` lets a `SUPER_USER` create additional CSS users with role-based authority and required first sign-on password changes.
- Every mobile screen shows system mode, engine mode, order state, and live broker gate state.

Live broker tickets still route through CSS credentials, broker availability, live-order flags, explicit `MOBILE LIVE` confirmation, and audit logging.
