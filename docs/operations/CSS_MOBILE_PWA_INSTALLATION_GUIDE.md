# CSS Mobile PWA Installation Guide

## Canonical installation surface

Install **Capital Strata Systems Mission Control** only from the operator-approved
CSS mobile public origin (the configured `CSS_MOBILE_PUBLIC_URL`) and its
`/dashboard` path. Do not install from an API URL, a report URL, or the separate
launcher service.

The installed application should appear as **CSS Mission Control**, open in a
standalone window, and use the dark navy and gold CSS icon without a Chrome
badge.

## Samsung / Android reinstall

1. Touch and hold the existing CSS icon on the Home screen.
2. Select **Remove** or **Uninstall**. If Android identifies it as a Chrome
   shortcut, remove the shortcut.
3. Open Google Chrome and navigate to the operator-approved CSS mobile URL.
4. Confirm the URL is the CSS origin and that the page is not under `/api/`.
5. Sign in if the application requests authentication.
6. Open Chrome's menu.
7. Select **Install app** when available. Do not select **Add to Home screen**
   when Chrome offers both choices.
8. Confirm the name **CSS Mission Control** and complete installation.
9. Launch the installed application. Confirm:
   - it opens in standalone mode;
   - the initial application route resolves from `/dashboard`;
   - the icon is the dark navy and gold CSS logo;
   - no Chrome badge appears on the icon;
   - authentication, RBAC and read-only safety controls remain active.

## If the old icon persists

Use these steps only after removing the old shortcut/application:

1. In Android Settings, open **Apps → Chrome → Storage**.
2. Prefer Chrome's per-site controls: open Chrome
   **Settings → Site settings → All sites**, select the CSS origin, and choose
   **Clear & reset**.
3. Do not clear unrelated site data unless required by the operator.
4. Reopen the canonical CSS mobile URL.
5. Wait for the page to finish loading so Chrome retrieves manifest version
   `180a1` and the versioned icon URLs.
6. Use **Install app** again.

Clearing CSS site data removes the local CSS web session and requires a new
sign-in. It does not change broker credentials, execution authority, runtime
readiness or trading controls.

## Operator verification

- `GET /manifest.webmanifest` returns `application/manifest+json`.
- The manifest identifies `/css-mission-control` and starts at `/dashboard`.
- Regular and maskable 192×192 and 512×512 icon URLs return HTTP 200.
- `GET /service-worker.js` reports version `180a1`.
- The service worker caches only public branding files and `/pwa-offline`.
- Login, dashboard, API, reports, broker data and runtime telemetry are never
  placed in the PWA cache.
