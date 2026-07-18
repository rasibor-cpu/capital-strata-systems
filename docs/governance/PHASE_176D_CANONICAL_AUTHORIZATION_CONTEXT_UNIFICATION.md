# Phase 176D — Canonical Authorization Context Unification

**Baseline:** `f171dc8127af24541f79b45965198761ac23994e` (Phase 176C)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Complete
**Date:** 2026-07-18

## Verified root cause

Mission Control HTML and Mission Control Reports APIs used **divergent identity sources**:

| Surface | Identity used (pre-176D) | Outcome |
|---|---|---|
| `GET /mission-control/reports` | `governance.role` from DashboardState / launcher frontend session | Trading artifact lacked RBAC role → defaulted to **`TRADER`**, or when unavailable the page silently fell back to **`ADMIN`** |
| `GET /mission-control/api/reports/home` | Hardcoded `role="ADMIN"` | Always `reports_view=true` (not a real check) |
| `/api/v1/reports/*` | Raw `X-CSS-*` headers with VIEWER default | Worked when headers present; inconsistent with HTML |
| Mobile `/reports*` | Login `user_ctx` | Correct when signed on |

Operator symptom: runtime authenticated as `00000` / `SUPER_USER`, API “allowed”, HTML showed **Access denied: reports_view permission required** (when governance carried `TRADER`) — or HTML/API both “allowed” via unsafe ADMIN shortcuts that did not reflect the real session.

## Old authorization flow

```
CLI auth 00000/SUPER_USER → css_auth_session.json / session_user_ctx
        ↘ (not used by MC HTML)
DashboardState.session.role ← css_session_state_pcnrass (no role) → "TRADER"
        → reports_center._role_from_state → ReportsCenterService.home(role)
        → Access denied

MC API reports/home → ReportsCenterService.home(role="ADMIN") → always allow
```

## New canonical flow

```
Request (MC HTML | MC API | /api/v1/reports | mobile)
  → resolve_authorization_context()
       1. explicit override (tests)
       2. trusted internal headers (CSS_TRUST_INTERNAL_AUTH_HEADERS only)
       3. session bridge: css_auth_session.json (restore_login_session)
          else recovery session_user_ctx (freshness-checked)
       4. fail closed
  → CSSAuthorizationContext
  → ReportsAccessControl / PermissionEngine (single evaluation)
  → pages consume reports_authorization; APIs consume same context
```

No silent ADMIN. Empty `user_id` is never treated as `00000`. Forged headers denied unless trust flag is set.

## Session bridge

- Module: `dashboard/auth/session_bridge.py`
- Primary: `dashboard.auth.css_sign_on.restore_login_session()` → `artifacts/css_auth_session.json`
- Secondary: `artifacts/css_session_recovery.json` → `session_user_ctx` (max age 24h)
- Launcher frontend identity: `_launcher_auth_identity()` no longer invents `TRADER`

## Header / cookie / session policy

| Mode | Behavior |
|---|---|
| Production default | Session bridge only; `X-CSS-Role` / `X-CSS-User-Id` **ignored** (forged-header denial if present) |
| `CSS_TRUST_INTERNAL_AUTH_HEADERS=1` | Trusted internal/test mechanism; headers require non-empty user_id + role |
| Cookies | Mobile continues to use existing login session; MC uses bridge + optional trusted headers |

**Limitation:** Desktop MC does not yet issue a browser session cookie; it bridges the CLI/runtime auth artifact. Production hardening may add a signed cookie later without a parallel identity store.

## Reports HTML / API / mobile parity

- HTML: `dashboard/mission_control/pages/reports_center.py` consumes `reports_authorization` only
- MC API: no hardcoded ADMIN
- `/api/v1/reports`: resolver-based identity
- Mobile: existing `ReportsAccessControl` via login `user_ctx`; PWA cache **`css-mobile-shell-v176d`**

## Authorization diagnostics

`backend/security/auth_diagnostics.py` logs privacy-safe denials: correlation_id, route, user_id, role, permission, identity/permission source, denial reason, timestamp. No tokens/secrets.

## Sub-tabs

Primary live defect was authorization divergence (Reports appeared broken). Registry COMING_SOON / DISABLED / FAIL_CLOSED controls remain intentionally non-operable and must stay labeled — not clickable success placeholders.

## Tests

`tests/test_phase176d_canonical_authorization_context.py` plus conftest isolation (stub live session; enable trusted headers for unit tests). Marker `live_session` opts into real bridge.

## Operational restart

```text
.\.venv\Scripts\python.exe -m uvicorn dashboard.web.web_app:app --host 0.0.0.0 --port 8000
.\.venv\Scripts\python.exe -m uvicorn dashboard.mobile.mobile_app:app --host 0.0.0.0 --port 8090
```

Ensure `artifacts/css_auth_session.json` is a valid active session for `00000` / `SUPER_USER` (or sign on via CLI). Soft-refresh mobile PWA once to pick up `css-mobile-shell-v176d`.

## Rollback

```text
git checkout 0313fe30daf4cf1364bec08d5a97d0c3f9a4fd09   # Phase 176B
# or Phase 176C:
git checkout f171dc8127af24541f79b45965198761ac23994e
```

Restart uvicorn hosts after checkout. Do not enable live trading.

## Safety

Preserved: `advisory_only=true`, `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`.
