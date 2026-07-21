# Phase 180A — CSS Mobile PWA Icon Remediation

## Outcome

Source remediation is implemented and certified. The prior launcher balance
failures and report-rendering stall were corrected during RC1.1 remediation.
Phase 180C.3 subsequently verified the authoritative bounded suite at 205 passed
with no failures, skips, or deselections.

Execution posture remains:

- `DISABLED`
- `BLOCKED`
- `FAIL_CLOSED`
- `ADVISORY_ONLY`

## Root cause and installation classification

The repository already contained approved CSS PNG and ICO artwork. In-memory
inspection of the tracked baseline confirmed the 180×180, 192×192 and 512×512
PNGs and a multi-frame ICO, with no Chrome or Google artwork embedded.

The Chrome badge was therefore not part of the CSS image. It was Android/
Chrome's visual treatment for a website shortcut created through **Add to Home
screen**, rather than the icon treatment of an installed PWA.

Consequences:

1. The dynamic manifest used `application/json`, not the canonical
   `application/manifest+json` response required by this phase.
2. The mobile manifest combined `purpose: any maskable` rather than supplying
   separate regular and maskable artwork.
3. PWA identity, start route and cache versioning were split between dynamic
   mobile and launcher manifests.
4. The prior service worker cached `/login` and used a broad fetch fallback,
   while manifest and icon update behavior was inconsistent.
5. Operator guidance did not clearly distinguish **Install app** from
   **Add to Home screen**.

Based on both the repository evidence and the badge, the affected phone entry
was a Chrome-created website shortcut. The remediation cannot transform an
existing shortcut in place; it must be removed and reinstalled as directed.

## Canonical brand asset family

The existing approved
`assets/branding/css_icon_1024x1024.png` is the sole canonical source. It
contains the established dark rounded-square, gold/platinum CSS monogram,
growth arrow and Capital Strata Systems wordmark. No replacement logo was
designed.

| Asset | Dimensions | Purpose |
|---|---:|---|
| `favicon-16x16.png` | 16×16 | Browser favicon |
| `favicon-32x32.png` | 32×32 | Browser favicon |
| `favicon.ico` | 16×16 and 32×32 frames | Browser/desktop favicon |
| `apple-touch-icon.png` | 180×180 | Apple touch icon |
| `css-icon-192.png` | 192×192 | PWA regular icon |
| `css-icon-512.png` | 512×512 | PWA regular icon |
| `css-icon-maskable-192.png` | 192×192 | PWA maskable icon |
| `css-icon-maskable-512.png` | 512×512 | PWA maskable icon |

The regular artwork is resized from that source and fills the canvas without
outer transparent padding. Maskable exports composite the same source at 78%
inside a matching opaque background to preserve the maskable safe zone. No
Chrome, Google or browser artwork is present. Legacy asset names are generated
from the same source.

The family is deterministic and can be regenerated with:

```powershell
.venv\Scripts\python.exe tools\generate_css_pwa_icons.py
```

## Manifest

The canonical manifest is `dashboard/mobile/manifest.webmanifest` and is served
as `application/manifest+json` from `/manifest.webmanifest`.

Validated source contract:

- Name: `Capital Strata Systems Mission Control`
- Short name: `CSS Mission Control`
- ID: `/css-mission-control`
- Start URL: `/dashboard`
- Scope: `/`
- Display: `standalone`
- Display override: window-controls-overlay, standalone, minimal-ui
- Orientation: any
- Separate `any` and `maskable` 192×192 and 512×512 PNG entries
- Branding version: `180a1`

## Routes and shared HTML head

The mobile FastAPI application serves only allow-listed branding files:

- `/manifest.webmanifest`
- `/favicon.ico`
- `/favicon-16x16.png`
- `/favicon-32x32.png`
- `/apple-touch-icon.png`
- `/pwa/css-icon-192.png`
- `/pwa/css-icon-512.png`
- `/pwa/css-icon-maskable-192.png`
- `/pwa/css-icon-maskable-512.png`
- `/service-worker.js`

`_pwa_head()` is the shared metadata source for login, dashboard and
authenticated mobile pages. It includes manifest, favicon, Apple touch,
application-name, standalone-capability, theme-color and viewport metadata.
Service-worker registration is also centralized and requests version `180a1`
with `updateViaCache: "none"`.

## Service-worker security review

Cache name: `css-mobile-pwa-180a1`.

Only public branding assets and the static `/pwa-offline` response are
pre-cached. Protected paths—including login, dashboard, API, reports, Mission
Control, broker, positions, trades, runtime, sessions, users and audit—are
network-only and are never written to cache. There is no runtime `cache.put`
path. Activation removes only obsolete caches owned by the
`css-mobile-pwa-` namespace and leaves unrelated browser caches untouched.

The service worker does not alter cookies, authentication, RBAC, readiness,
broker state, runtime telemetry or execution authority.

## Files changed

- `assets/branding/README.txt`
- Canonical and compatibility binary files under `assets/branding/`
- `tools/generate_css_pwa_icons.py`
- `dashboard/mobile/manifest.webmanifest`
- `dashboard/mobile/mobile_app.py`
- `dashboard/enterprise_shell/mobile_landing.py`
- `launcher/css_mobile_launcher.py`
- `launcher/static/css_launcher_icon.svg`
- `launcher/static/css_launcher_manifest.json`
- `launcher/templates/mobile_launcher.html`
- `launcher/templates/mobile_dashboard.html`
- `tests/test_phase180a_mobile_pwa_icon_remediation.py`
- Related existing PWA/mobile regression tests
- `docs/operations/CSS_MOBILE_PWA_INSTALLATION_GUIDE.md`
- This report

## Verification evidence

| Check | Result |
|---|---|
| Icon generator | PASS — exit 0; source transforms and dimensions verified |
| Focused Phase 180A/icon suite | PASS — 7 passed, exit 0, 1.84s |
| Relevant Phase 176 mobile/PWA regression | PASS — 29 passed, exit 0, 3.43s |
| Launcher manifest/icon route | PASS — 1 passed, exit 0, 7.45s |
| Broad launcher suite | FAIL — 48 passed, 22 failed; unrelated `None` balance/template comparisons |
| Combined UI suite | INCOMPLETE — 39 tests completed, then report-route test stalled; terminated after 1077.411s |
| Compileall | PASS — exit 0, 6.170s |
| `git diff --check` | PASS — exit 0, no output |
| `git diff --stat` | PASS — 37 tracked files, 820 insertions, 298 deletions; untracked files excluded |
| `git status --short` | PASS — completed; all changes unstaged, with existing broader RC1.1 work present |

The one pytest warning is a pre-existing Python `crypt` deprecation warning.
No passing result is claimed without command output and exit status.

## Phone reinstall

Follow `docs/operations/CSS_MOBILE_PWA_INSTALLATION_GUIDE.md`. Remove the old
shortcut first, open the configured canonical CSS mobile URL in Chrome, and use
**Install app** rather than **Add to Home screen** where both are offered.

## Safety confirmation

This phase changes branding assets, PWA metadata, safe static routes,
installation caching and documentation only. It does not enable live trading,
paper execution, OAuth, broker authentication, credential retrieval, runtime
restart, order submission or micro-pilot arming. No authorization, RBAC,
readiness or fail-closed control is weakened.
