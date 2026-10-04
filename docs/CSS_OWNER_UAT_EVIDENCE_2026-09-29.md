# CSS Owner / Operator UAT — Evidence Matrix (2026-09-29)

_Human owner UAT of the engineering release candidate, run against `docs/CSS_OPERATOR_UAT_PACKAGE.md`. Records only what the owner reported observing (OWNER_OBSERVED_PASS) separately from engineering evidence (ENGINEERING_VERIFIED); nothing engineering-only is presented as owner-observed. No credential, password or session token appears here._

## Session identity

| Item | Value |
|---|---|
| Starting RC | `9335e866585d1b02319a5a56b1dfc7d8ebb35150` (local tag `css-engineering-rc-2026-09-29`, not pushed) |
| Code under test at close | `720d9b39df2a16d303d24e2abd4f9ea1a5cec50d` (owner-UAT fixes: `587812e3`, `720d9b39`) |
| Branch / PR | `css-operator-auth-2026-09-28` / PR #101 (open, draft, not merged) |
| Server | `dashboard.web.web_app:app`, `127.0.0.1`, `CSS_ENV=development`, `CSS_COMMERCIAL_DB=data\css_commercial_uat.sqlite3`, `CSS_AUTH_AUDIT_DB=data\css_auth_audit.sqlite3` — the launcher's configuration |
| Port deviation | STANDARD_UAT_PORT=8000 · ACTUAL_UAT_PORT=8001 · PORT_DEVIATION_REASON=8000 already occupied by pre-existing unrelated python/uvicorn `app.api:app` PID 10684 · EXISTING_PROCESS_MODIFIED=NO · CSS_SOURCE_MODIFIED=NO (for the port) |
| Store | Existing UAT store (not reset). Admin bootstrap and first-login password changes were completed in engineering UAT and not repeated by the owner |
| Identities | 10001 FINCON, 10002 HEAD_FINCON, 10003 AUDIT, 10004 HEAD_COMPLIANCE |

## Defects found in owner UAT (all closed)

| # | Defect (owner-observed) | Root cause | Fix | Owner retest |
|---|---|---|---|---|
| D1 | Signed-in identity/role not visible | Shared header rendered only Logout | `587812e3`: "Signed in: `<id>` · `<role>`" beside Logout on every page, from the server-side session | OWNER_OBSERVED_PASS |
| D2 | Pending request not discoverable by the checker (no web checker workflow) | Approve/reject existed only on the bearer governance API | `587812e3`: governed **Approvals** page; list/approve/reject accept the session cookie with CSRF on POST | OWNER_OBSERVED_PASS |
| D3 | Dashboard scoring tiles showed `[object Object]` | Page `get(path)` resolved only two path segments | `587812e3`: full-path resolution; objects render N/A | OWNER_OBSERVED_PASS |
| D4 | Trial & Contract **Check Status** showed nothing | Handler returned silently unless Load Agreement had been clicked in the same page load; no error handling | `720d9b39`: reads Agreement ID/Version fields; every outcome rendered visibly; API returns enrollment facts | OWNER_OBSERVED_PASS |

## Evidence matrix

Classification values: OWNER_OBSERVED_PASS · ENGINEERING_VERIFIED · FAIL · N/A · NOT_TESTED.

| # | Checklist item | Classification | Evidence |
|---|---|---|---|
| 1a | Sign in — FINCON 10001 | OWNER_OBSERVED_PASS | Owner signed in and worked as 10001 |
| 1b | Sign in — HEAD_FINCON 10002 | OWNER_OBSERVED_PASS | Owner signed in as 10002 after logging out of 10001 |
| 1c | Sign in — AUDIT 10003, HEAD_COMPLIANCE 10004 | ENGINEERING_VERIFIED | Live engineering UAT (51/51) and `tests/test_owner_uat_followups.py` |
| 1d | Signed-in identity visible (D1) | OWNER_OBSERVED_PASS | Owner observed "10002 · HEAD_FINCON" |
| — | First-login forced password change | ENGINEERING_VERIFIED | Completed in engineering UAT; owner not repeated |
| 2 | Wrong password / lockout | ENGINEERING_VERIFIED | Engineering UAT; `tests/test_operator_authentication.py`, `tests/test_change_password_hardening.py` |
| 3 | Admin bootstrap closed (no default password; local one-time) | ENGINEERING_VERIFIED | Live engineering UAT bootstrap phase 8/8; `tests/test_admin_bootstrap.py`; owner not repeated |
| 4a | Dashboard scoring tiles render values (D3) | OWNER_OBSERVED_PASS | Owner reported the `[object Object]` defect corrected |
| 4b | Mission Control shows no execution allowed/armed | ENGINEERING_VERIFIED | Engineering UAT (all four roles); safety posture below |
| 5 | Role restriction — AUDIT cannot enroll | ENGINEERING_VERIFIED | Engineering UAT; `tests/test_commercial_routes_cookie_auth.py` |
| 6 | Billing page loads while signed in | ENGINEERING_VERIFIED | Engineering UAT (cookie-authenticated data calls) |
| 7a | Advice attribution / profitability / loss-recovery economics | ENGINEERING_VERIFIED | 189 automated economics tests; economics code unchanged since COM-014 |
| 7b | Populated advice-profitability / client-earnings screens | NOT_TESTED | No owner-approved dataset seeded (documented limitation) |
| 8 | Load UAT-AGR-001 v1 terms | OWNER_OBSERVED_PASS | Owner loaded and saw the agreement as FINCON |
| 9 | FINCON maker submission → PENDING, second approver required, no payment | OWNER_OBSERVED_PASS | Request `2e99307a-d071-4be1-98d7-d197c2048de2` for UAT-CUSTOMER-001 / UAT-ACCOUNT-001 |
| 10 | Maker cannot approve own request | ENGINEERING_VERIFIED | Engineering UAT; `tests/test_owner_uat_followups.py`, `tests/test_uat_trial_enrollment.py` |
| 11a | Checker finds request on Approvals (D2) and approves | OWNER_OBSERVED_PASS | HEAD_FINCON 10002 approved; page showed "EXECUTED (ENROLLED:2026-10-30T01:55:05.283000Z)"; pending count became 0; no payment |
| 11b | Check Status shows persisted trial (D4) | OWNER_OBSERVED_PASS | Owner saw Status TRIAL_ACTIVE; UAT-CUSTOMER-001 / UAT-ACCOUNT-001; UAT-AGR-001 v1; start 2026-09-30T01:55:05.283000Z; expiry 2026-10-30T01:55:05.283000Z; cancellation NO; "trial remains active"; read-only note |
| 12 | Replay / payload-tamper refusal | ENGINEERING_VERIFIED | Engineering UAT (replay 409, tamper 422); automated tests |
| 13 | Cancellation workflow | ENGINEERING_VERIFIED | `tests/test_uat_trial_enrollment.py`, `tests/test_trial_status_check.py`; owner instructed not to cancel the UAT enrollment |
| 14 | Commercialization operations page | ENGINEERING_VERIFIED | Engineering UAT; owner opened Launch Ops (source of D1/D2 observations) but did not assess its status output |
| 15 | Audit visibility | ENGINEERING_VERIFIED | Commercial audit REQUEST → APPROVE → EXECUTE for `2e99307a…`, chain verifies; no credential in either audit log |
| 16 | Restart / recovery | ENGINEERING_VERIFIED | Engineering UAT restart phase; the UAT server was also restarted twice during owner UAT to load fixes and the request/enrollment persisted (not an owner-performed check) |
| 17a | Logout | OWNER_OBSERVED_PASS | Owner logged out of 10001 before signing in as 10002 |
| 17b | Old session unusable after logout | ENGINEERING_VERIFIED | Engineering UAT; `tests/test_logout_csrf.py` |
| 18 | Disable → session revocation | ENGINEERING_VERIFIED | `tests/test_operator_authentication.py`, `tests/test_mobile_session_revalidation.py` |

No item is FAIL. No item is N/A.

## Final state (read-only verification at close)

```
REQUEST=EXECUTED                      2e99307a-d071-4be1-98d7-d197c2048de2, maker 10001 FINCON, checker 10002 HEAD_FINCON
TRIAL_STATUS=TRIAL_ACTIVE             UAT-CUSTOMER-001 / UAT-ACCOUNT-001, UAT-AGR-001 v1, 2026-09-30T01:55:05.283000Z -> 2026-10-30T01:55:05.283000Z
CANCELLATION=NO
PAYMENT_EXECUTED=NO                   receivable payments, allocations, collection authorities, provider configurations, charge policies: 0 rows
COMMERCIAL_AUDIT=REQUEST, APPROVE, EXECUTE; hash chain verifies; auth audit chain verifies
CUSTOMER_CHARGING_ENABLED=false
MONEY_MOVEMENT_ALLOWED=false
EXECUTION_ALLOWED=false
LIVE_TRADING_BLOCKED=true
BROKER_EXECUTION_ARMED=false
ADVISORY_ONLY=true
PRODUCTION_COMMERCIAL_READY=false     (readiness runner: trading/broker execution authority false, external money movement false)
```

The runtime database also holds one earlier enrollment (`UAT-CUST-1-29292e`) created by the automated engineering-UAT harness before owner UAT; it is test data, not part of the owner evidence.

## Engineering evidence at close

`720d9b39`: full suite 2567 passed / 0 failed / 0 skipped locally; CI on the exact head — Full Regression `36660608527` (2567 passed), Full Test Release Candidate `36660610748` (2567 passed, readiness authority flags false), `css-validation` `36660612738` — all SUCCESS.

## Owner sign-off

Owner-observed items above were reported by the owner (Robert Asibor) in session on 2026-09-29. Production release is **not** authorized by this record; human operator UAT beyond the owner, production deployment, TLS, real payment provider and live-trading decisions remain separate owner-only gates.
