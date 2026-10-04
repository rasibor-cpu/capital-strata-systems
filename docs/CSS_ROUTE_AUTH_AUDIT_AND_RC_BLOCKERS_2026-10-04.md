# CSS Route Authentication Audit (COM-016) and Release-Candidate Blocker Status — 2026-10-04

_Claude engineering lane. Continues PR #101 (`css-operator-auth-2026-09-28`, head `57404a4a`) on branch `claude/great-keller-w2m36y`. This file records evidence, not intentions. It uses the verification levels defined in `docs/CSS_COMMERCIAL_CLOSURE_EVIDENCE.md`._

## Starting state

| Item | Value |
|---|---|
| Starting HEAD | `57404a4ad2a673109dbaa05e37e118754a87f2f9` (PR #101 head: production-authorization BLOCKED record) |
| PR #100 | OPEN, base `css-v1-completion-2026-09-13`; its head `653b45c0` is an ancestor of this branch |
| PR #101 | OPEN, stacked on PR #100; all COM-011..015 commits are present on this branch |
| Working tree at start | clean |
| Baseline suite at start (local, Python 3.11, no `httpx`, same as CI) | **2567 passed / 0 failed** |

## Safety posture (unchanged by this work)

R7 unified trade gate, R14F thresholds, AntiBleedGuard and the paper position caps (CRYPTO 3, FX 3, OPTIONS 2, FUTURES 2) are not touched. Mission Control stays read-only and Questrade stays read-only. Source defaults are unchanged: `execution_allowed=false`, `live_trading_blocked=true` and `advisory_only=true` (`dashboard/runtime/mission_control_state.py`). No test was weakened, and no authentication bypass was added for tests.

## Method

The audit enumerated the routes **programmatically**, not by grep. It built every servable FastAPI app, with the commercial governance API mounted (`CSS_COMMERCIAL_DB` set). It then sent each route an anonymous request, a request with a forged bearer token and a request with a forged cookie. Any route that did not fail closed was read by hand. `tests/test_route_auth_inventory.py` now turns that probe into a standing test. Every route must be classified there, so a new route fails CI until someone classifies it (default deny for new surface).

Servable apps: `dashboard.web.web_app:app` (launchers `CSS Dashboard.cmd` and `CSS Web UAT Server.cmd`), `dashboard.mobile.mobile_app:app` (`CSS Mobile Server.cmd`), and `backend.app.main:app` (no launcher, but `docs/governance/CSS_RUNTIME_AUTHORITY_MAP.md` names it a canonical runtime owner). Non-servable: root `main.py` (`ModuleNotFoundError: taxonomy`) and `backend/app/api.py` (`ImportError: orchestrate`). `ui/backend/app/main.py` is a dev shadow console that serves synthetic sample state only, and its login fails closed when default credentials are in use.

## Findings fixed in this pass

| # | Severity | Route | Finding | Fix | Evidence |
|---|---|---|---|---|---|
| F1 | **HIGH** | `POST /engine/headless/run` (`backend/app/main.py`) | **Unauthenticated, state-changing engine run.** An anonymous POST returned `200 {"ok":true,"steps_executed":5}`. LIVE was already blocked by `HeadlessConfig(allow_live=False)`, but anyone who could reach the port could drive the engine with client-supplied equity and position figures. | Bearer-only `require_engine_operator` dependency. Identity and role come from the server session. The permission check uses the existing `PermissionEngine` grant `manage_system` (SUPER_USER only) through the existing `actor_from_bearer`, so every 403 is audited as `AUTHORIZATION_DENIED`. A cookie is never accepted, so the route has no CSRF exposure. Authentication grants a run, never live execution: a LIVE request is still refused. | 401 for anonymous, forged, expired, malformed, spoofed-header and cookie-only requests; 403 for ADMIN/TECH/HEAD_TECH/TRADER/RISK/AUDIT/FINCON/VIEWER/unknown roles; 200 for SUPER_USER; denial audited once |
| F2 | MEDIUM | `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` on web, mobile and engine apps | Interactive API docs and the full schema were served anonymously in every configuration, a debug surface reachable in production. Nothing in the repository consumes them. | `api_docs_kwargs()` in `backend/app/auth/operator_login_router.py`, next to `cookie_secure_default` and using the same rule: docs are served only when `CSS_ENV=development` is declared. In-process `app.openapi()` still works, and the existing schema tests still pass. Declaring development exposes the schema, never the data behind it. | 404 by default on all three apps; 200 only with `CSS_ENV=development`, while protected data routes still return 401 |
| F3 | LOW | mobile `GET /api/margin-snapshot` | Anonymous callers got **HTTP 200** with an `AUTH_REQUIRED` body. No data leaked, but the status code failed open for any client that checks status. | Returns 401 with the same body. | Tested with anonymous, forged, expired-cookie, web-cookie and spoofed-header requests |

Full local suite after the change: **2730 passed / 0 failed** (2567 baseline + 163 new, `tests/test_route_auth_inventory.py`). `dashboard/web/web_smoke_test.py` PASSES. `dashboard/mobile/mobile_smoke_test.py` fails on its login-page status-strip assertion **identically on the unmodified starting head** `57404a4a`. It is pre-existing, not run by any workflow, and not touched here.

All three are AUTOMATED-TEST VERIFIED. With the three code changes reverted, 19 of the 163 new tests fail. With the changes in place, all 163 pass. They are not yet CI-VERIFIED: CI must run on the pushed head.

## Route classification

Columns: ROUTE | AUTH REQUIRED | ROLE/CLAIM REQUIRED | STATE CHANGING? | CURRENT STATUS | FIX REQUIRED.

### Web dashboard (`dashboard/web/web_app.py`)

| Route | Auth | Role / claim | State-changing | Status | Fix |
|---|---|---|---|---|---|
| `GET /` | No | — | No (303 → /dashboard) | OK | — |
| `GET /login`, `POST /login` | No | Credentials (lockout, disabled check) | Creates session | OK; login is CSRF-exempt by design (no session yet) | — |
| `POST /logout` | Session (cookie) + CSRF | — | Revokes session | OK (COM-015) | — |
| `GET /health` | No | — | No | ACCEPTED: liveness only (`ok`, engine `session_id`, `resolved_mode`, `engine_mode`); no account or financial data; key set pinned by test | — |
| `GET /dashboard`, `/positions`, `/execution`, `/risk-governance`, `/market-opportunities`, `/broker`, `/margin`, `/billing`, `/trial-contract`, `/commercialization-operations`, `/approvals` | Session (cookie or bearer) | Any operator | No | OK: 303 → /login for anonymous, forged, expired and spoofed callers | — |
| `GET /api/v1/{dashboard-state, frontend-state, account-summary, positions, risk, governance, opportunities, broker, broker-reconciliation, broker-state, broker-continuity, questrade/account-summary, session10-readiness, runtime-health, runtime-alerts, margin-snapshot, report-export}` | Session | Any operator | No (read-only; Questrade read-only) | OK: 401 | — |
| `GET /api/v1/mission-control` | Session | Any operator (OPEN product decision #11) | No (read-only; no execution capability) | OK: 401 | — |
| `WS /ws/v1/dashboard-state` | Session at handshake | Any operator | No | OK (`tests/test_dashboard_websocket_auth.py`) | — |
| `POST /auth/operator/login` | No | Credentials | Creates session | OK | — |
| `POST /auth/operator/change-password` | Current password | Credentials | Yes | OK (shares `_verify_credentials_or_raise`, COM-015) | — |
| `POST /auth/operator/logout` | Session + CSRF if cookie-backed | — | Revokes | OK | — |
| `GET /auth/operator/me` | Session | — | No | OK | — |
| `POST /auth/operator/admin/users/{id}/disable` and `/enable` | Session + CSRF if cookie-backed | SUPER_USER | Yes | OK: 403 for ADMIN/AUDIT/HEAD_FINCON/TRADER | Maker-checker for identity admin: OPEN governance decision #15 |
| `GET /api/v1/client-earnings-{summary,history}`, `customer-profitability-summary`, `advice-profitability-history` (billing / profitability attribution) | Session (cookie or bearer) | `commercial_view_obligations` | No | OK: 401 / 403 | — |
| `GET /api/v1/withdrawable-funds-summary` | Session | Commercial view | No (client-supplied, non-authoritative) | OK | — |
| `GET /api/v1/commercial-trial/{agreement,status}` | Session | Commercial view | No | OK | — |
| `POST /api/v1/commercial-trial/{enroll,cancel}` | Session + CSRF if cookie-backed + idempotency key | `commercial_trial_enroll` / `_cancel` (FINCON, HEAD_FINCON) | Creates a **PENDING** maker-checker request only | OK: 403 for TRADER/AUDIT/SUPER_USER/ADMIN/TECH; 201 PENDING for FINCON; `execution_authority=false`, `money_movement_allowed=false` | — |
| `GET /api/v1/{production-charging/readiness, commercialization-release/readiness, commercialization-operations/status, payment-collection/preflight, customer-notifications/preflight, launch-dossier/export}` | Session (bearer; ops-status also cookie) | Commercial view | No | OK | — |
| `GET /api/v1/commercial/{safety-posture, reconciliation/exceptions, controlled-actions, customers/{id}/statement, audit}` | Bearer (controlled-actions list also cookie) | Commercial view / `commercial_view_audit` | No | OK | — |
| `POST /api/v1/commercial/reconciliation/exceptions/{id}/resolution-requests` | Bearer | `commercial_prepare_action` | Creates a PENDING request | OK | — |
| `POST /api/v1/commercial/controlled-actions/{id}/{approve,reject}` | Session + CSRF if cookie-backed | `commercial_approve_action` (HEAD_FINCON, HEAD_COMPLIANCE); maker ≠ checker | Yes | OK: 403 for FINCON/AUDIT/TRADER/SUPER_USER | — |
| `/docs`, `/redoc`, `/openapi.json` | — | — | No | **Was: anonymous in production → FIXED (F2)** | Done |

### Mobile (`dashboard/mobile/mobile_app.py`; separate session store, re-validated per request since COM-015)

| Route | Auth | Role / claim | State-changing | Status | Fix |
|---|---|---|---|---|---|
| `GET /`, `GET/POST /login`, `GET /manifest.webmanifest`, `/service-worker.js`, `/icon.svg` | No | — | Login creates session | OK | — |
| `GET/POST /password-change` | Possession cookie + CSRF | — | Yes | OK (COM-014) | — |
| `POST /logout` | Session + CSRF | — | Revokes | OK | — |
| `GET /api/status` | No | — | No | ACCEPTED: the same posture fields the sign-in status strip already shows before authentication (system, engine, orders, kill switch, broker gate; `live_orders_enabled` is always false); no account, position or financial data; key set pinned by test | Narrowing it is a product decision |
| `GET /dashboard`, `/positions`, `/history`, `/risk`, `/governance`, `/opportunities`, `/market`, `/broker`, `/margin`, `/audit`, `/trade-status`, `/controls`, `/trade`, `/users` | Session | Any operator (`/audit`, `/users` gated further in-page) | No | OK: 303 → /login | — |
| `POST /controls` | Session + CSRF | `_can_manage_mobile_controls` | **Yes: trading controls** | OK (COM-014 CSRF, COM-015 re-validation) | — |
| `POST /trade` | Session + CSRF | `_can_submit_trade` | **Yes: trade ticket** (live orders remain blocked by kill switch and broker gate) | OK | — |
| `POST /users` | Session + CSRF | `can_manage_users` | Yes | OK | — |
| `GET /api/audit/{export,replay}` | Session | `_can_view_audit_logs` | No | OK: 401 / 403 | — |
| `GET /api/margin-snapshot` | Session | Any operator | No | **Was: HTTP 200 for anonymous → FIXED (F3)** | Done |
| `/docs`, `/redoc`, `/openapi.json` | — | — | No | **FIXED (F2)** | Done |

### Engine API (`backend/app/main.py`)

| Route | Auth | Role / claim | State-changing | Status | Fix |
|---|---|---|---|---|---|
| `GET /health` | No | — | No | LOW, OPEN: echoes import-error text (class and message) when the headless entry fails to import; no secrets | Optional hardening |
| `POST /engine/headless/run` | **Bearer** | **`manage_system` (SUPER_USER)** | **Yes** | **Was: anonymous → FIXED (F1)** | Done |
| `/docs`, `/redoc`, `/openapi.json` | — | — | No | **FIXED (F2)** | Done |

### Non-servable or dev-only

| App | Status |
|---|---|
| root `main.py` `POST /orchestrate` (takes `user_id` from the body) | Not importable (missing `taxonomy`). Pinned by `test_legacy_orchestrate_entrypoints_are_not_servable`, so a partial revival fails CI instead of exposing an unauthenticated posting route |
| `backend/app/api.py` `POST /orchestrate` | Not importable (`orchestrate` missing from `backend.app.main`). Same pin |
| `ui/backend/app/main.py` (shadow console) | Dev only, with no launcher. Read-only synthetic sample state; login fails closed with default credentials. Not mounted anywhere |

### Bypass review

The audit found no header, cookie or environment flag that grants access. Every protected route was re-driven with spoofed identity headers (`X-Forwarded-User`, `X-User-Id`/`X-Role: SUPER_USER`, `X-CSS-Role`, `X-Remote-User`, `X-Debug`/`X-Internal-Request`/`X-Auth-Bypass`, loopback `X-Forwarded-For`). It was also driven with nine malformed `Authorization` forms and under 13 bypass-looking environment variables, including `CSS_ENV=development`, `DEBUG`, `CSS_AUTH_DISABLED`, `SKIP_AUTH`, `HEADLESS_DEV_MODE`, `REA_ALLOW_DEFAULT_CREDS` and `PYTEST_CURRENT_TEST`. Every one still fails closed. The only behavior `CSS_ENV=development` changes is the cookie `Secure` flag and, now, the docs pages.

### Restart

An app rebuilt with a fresh session store keeps every route protected. Sessions issued before the restart are rejected by bearer and by cookie, for web and mobile alike, and the engine route's auth holds across module reloads. Operator sessions are still in memory (OPEN item #23, restart-safe sessions), so operators sign in again after a restart. That is fail-safe.

## Soak / reliability evidence

**No valid continuous endurance (soak) certification exists for any CSS line, and none exists for this release candidate.** All figures below come from the committed reports. The raw evidence packages (`runtime_reports/operational_validation/...`) are in local custody and are not in git, so this review could not re-hash them.

| Run | Branch / freeze | Wall-clock | Outcome |
|---|---|---|---|
| OV-002 Attempt 1 (`OV002-20260722T043023Z`) | `css-unified-consolidation-2026-07-13` @ `34503b15` | ~25.19 h of 72 h; 304 snapshots | **INVALIDATED.** The monitor failed closed on `active_commit_changed` (HEAD moved to `0457c24e`). Stop causality beyond that is unknown. No traceback evidenced; live execution blocked throughout |
| OV-002 Attempt 2 (`OV002-20260723T062225Z`) | same branch @ `0ff97cba` | **72.03 h**; 863 snapshots; no commit drift; mobile PID 26152 / port 8765 continuous | **INVALIDATED.** **8 unexpected runtime exits/restarts** (06:24–06:43 UTC on 07-23; `restart_count=8` against `max_restart_limit=3`, so limit enforcement is weak). **2 CRITICAL `ENGINE_HEARTBEAT_LOST`** alerts (06:34:09Z and 06:53:25Z, each 600 s). Supervisor identity discontinuity (`started_at` reset to 06:43:24Z). The monitor's provisional "PASS WITH RESIDUALS" was rejected |
| Phase 115A paper session (2026-06-16) | `css-evening-consolidation-2026-06-09` | ~141 cycles; **no wall-clock duration recorded** | Narrative only, with no hashed artifacts. Not soak evidence |
| ER-001 untimed desktop instance | `css-unified-consolidation-2026-07-13` | Unknown | Plan only; allows at most OBSERVATIONAL_STABILITY credit |

Answers to the requested soak questions, for Attempt 2, the latest evidenced run:

| Question | Answer |
|---|---|
| Continuous runtime | 72.03 h of HTTP availability, but runtime continuity was **not** established |
| Restarts | 8 unexpected |
| `ENGINE_HEARTBEAT_LOST` | 2 critical |
| Uncaught exceptions | No fatal traceback evidenced. The 8 exits are unexplained |
| Memory / resource instability | Not reported; resource samples present |
| Broker-connection instability | None reported. Coinbase failed closed; OANDA practice / read-only |
| Stale-data incidents | Not reported |
| Watchdog intervention | Yes: the supervisor auto-restarted 8 times |
| Trade-gate violations | None reported |
| Execution-permission transitions | None: `execution_allowed=false` and `can_live_execute=false` across snapshots; live authority BLOCKED |

**Gaps that keep soak blocked for this RC:**

1. The OV-002 R1 remediation (atomic persistence, monotonic critical ledger, v2 process identity, legacy PASS rejection) is on `css-rclive-w1-autonomous-supervisor` and `css-tai-002-runtime-validation-r2`, **not** on the PR #100/#101 line. This branch has no `backend/certification/` or `scripts/css_ov002_72h_endurance.py`. That review ended **CHANGES REQUIRED** (OV002-R5-IR).
2. Attempt 3 is **prohibited until the owner explicitly approves it**, with a fresh zero-time start (`PHASE_182_RUNTIME_INTEGRITY_AND_CERTIFICATION_FOUNDATION.md`).
3. The root cause of Attempt 2's eight exits and two heartbeat losses has not been established in any committed document.

Nothing in this pass started, extended or credited a soak run.

## Live-trading certification

Status is unchanged and remains **BLOCKED**. Per `docs/CSS_PRODUCTION_AUTHORIZATION_EVIDENCE_2026-09-30.md`: `PRODUCTION_RELEASE_AUTHORIZED=NO`, `LIVE_FUNDED_TRADING_AUTHORIZED=NO`, `BROKER_EXECUTION_AUTHORIZED=NO`. Live-trading certification additionally needs the following, none of which this repository can produce honestly:

- **Endurance (above):** a valid OV-002 run on the RC line.
- **External production evidence:** security/operations, backup/restore drill, signed incident tabletop, production-like UAT, legal/jurisdiction review, a deployed environment, and owner sign-off after review.
- **Broker certification:** live credentials for Coinbase/OANDA and a `REAL_BROKER`, CURRENT, armed provenance. Mission Control computes `execution_allowed` only from those, and `live_trading_blocked` is hard-coded `True`.

## Release-candidate path (engineering view)

1. Run CI on this head and merge COM-016 into PR #101 (owner decision).
2. Owner decision on soak: either port the OV-002 R1 harness and remediation onto the RC line (an engineering task, after OV002-R5-IR's changes-required items are closed) or certify from the remediated line. Diagnose Attempt 2's exits and heartbeat losses before any Attempt 3.
3. Owner approval of Attempt 3; fresh 72 h run on a frozen RC SHA.
4. The external production evidence listed above.
5. Live-trading certification only after 1–4, through the approved certification gates. Not before.

## Open items recorded, not fixed

- Engine `/health` echoes import-error text (LOW).
- Mobile `/api/status` and web `/health` are anonymous by design (ACCEPTED; narrowing them is a product decision).
- Earlier OPEN items #7, #11, #15, #22 and #23 in `docs/CSS_COMMERCIAL_CLOSURE_EVIDENCE.md` are unchanged.
