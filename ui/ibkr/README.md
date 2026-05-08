# CSS Institutional UI Shadow Console

This UI phase adds a static institutional console that consumes the `DashboardState.to_dict()` shape through `/api/v1/dashboard-state` when available, then falls back to local shadow sample data.

## Scope

- Web console: `ui/ibkr/index.html`
- Mobile console: `ui/ibkr/mobile.html`
- No direct broker calls
- No live order routing
- Shadow ticket actions only
- DashboardState remains the frontend bridge

## Local Use

Open `ui/ibkr/index.html` for desktop web or `ui/ibkr/mobile.html` for phone-sized testing. If the FastAPI UI backend is running at `http://127.0.0.1:8000`, the console will poll `/api/v1/dashboard-state`; otherwise it renders the bundled shadow sample.
