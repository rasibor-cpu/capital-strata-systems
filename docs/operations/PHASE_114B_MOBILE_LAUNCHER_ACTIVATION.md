# Phase 114B Mobile Launcher Activation

**Date:** 2026-06-21
**Environment:** Control Branch `css-evening-consolidation-2026-06-09`

## Objective
Activate and validate the Phase 114A mobile-enabled CSS launcher so it can be reached from a mobile browser and installed as a phone home-screen icon using the PWA manifest.

## Results & Required Questions Answered

**1. What exact URL opens the CSS mobile launcher?**
The exact URL to open the mobile launcher is:
`http://0.0.0.0:8765/` or `http://0.0.0.0:8765/mobile-launcher`
*(Assuming the device connects to the host machine's IP instead of 0.0.0.0 from a remote device, e.g., `http://<LAPTOP_IP>:8765/`)*

**2. What command starts the launcher server?**
The launcher server can be started directly via Python using:
```bash
python -m launcher.css_mobile_launcher
```

**3. Is the launcher connected to the existing CSS mobile dashboard?**
Yes, the launcher provides a button linking directly to the CSS mobile dashboard URL configured via the `CSS_DASHBOARD_URL` environment variable (which defaults to `/mobile`).

**4. Can Android "Add to Home Screen" detect the manifest and icon?**
Yes. The `/manifest.json` correctly serves the `css_launcher_manifest.json` declaring `standalone` display mode, and the `/static/css_launcher_icon.svg` provides the generic vector icon for the Home Screen. Instructions are also displayed if the user navigates directly on Android.

**5. What happens if the backend/supervisor state files are unavailable?**
The launcher strictly fails open safely.
- If files are entirely missing, it returns a safe "UNKNOWN" or "OFFLINE" status without crashing.
- If files contain invalid JSON, it catches the `json.JSONDecodeError` explicitly, displays an "ERROR" status with the decoder error string, and still successfully loads the launcher interface.

## Functionality Validated
- API routes (`/health`, `/status`, `/manifest.json`, `/static/css_launcher_icon.svg`) added and working.
- Standard PWA support included.
- Automated API unit tests using FastAPI `TestClient` have verified the routes and payload shapes.
- No direct authentication bypassing or risk logic changes have been made.

## Next Steps
In future deployments, the `css_mobile_launcher` API router could be mounted alongside the core `dashboard` web instance instead of running as a standalone `uvicorn` instance, or could be run as a lightweight supervisor service.
