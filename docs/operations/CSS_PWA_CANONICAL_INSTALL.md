# CSS PWA Canonical Install Authority (AR-025)

**Programme:** Release Gate 2 — Wave 2  
**Status:** ACTIVE  
**Date:** 2026-07-21

## Canonical install identity

| Surface | Manifest | Canonical? |
| --- | --- | --- |
| Mission Control Mobile | `/manifest.webmanifest` (`id=/css-mission-control`) | **YES — production PWA identity** |
| Mobile Launcher shell | `/manifest.json` (`id=/css-mobile-launcher`) | **NO — local operator shell only** |

Do not install the launcher manifest for production or commercial distribution.

## Secure-context requirement

Android / Chromium PWA install requires a **secure context**:

- `https://` operator origin, **or**
- `http://localhost` / `http://127.0.0.1` for local development only

LAN HTTP (`http://0.0.0.0:8765` / private-IP HTTP) is **unsupported** for production installability claims.

## Operator HTTPS path

1. Terminate TLS at a reverse proxy (nginx, Caddy, IIS, cloud LB) in front of the CSS mobile host.
2. Forward to the local CSS process over localhost HTTP if needed.
3. Set `CSS_FORCE_SECURE_COOKIES=1` when the app is served behind HTTPS terminators that present HTTP to the app.
4. Confirm `/manifest.webmanifest` is reachable on the HTTPS origin before Android install acceptance.

## Acceptance checklist (operator-signed)

- [ ] HTTPS origin documented for the deployment
- [ ] Only `/manifest.webmanifest` used for install
- [ ] Launcher `/manifest.json` labeled non-canonical in ops runbooks
- [ ] Physical Android install smoke performed on the HTTPS origin (procedural; not automated here)

## Non-claims

- This document does not ship in-repo TLS certificates.
- This document does not authorize live trading or production certification.
