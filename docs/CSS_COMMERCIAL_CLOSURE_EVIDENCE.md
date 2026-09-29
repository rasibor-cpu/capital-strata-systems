# CSS Commercial Collections — Closure Evidence Package

_Maintained by the Claude engineering lane. Repository `rasibor-cpu/capital-strata-systems`. Base work: branch `css-commercial-collections-2026-09-19`, PR #100 (draft) → `css-v1-completion-2026-09-13`. COM-011 (operator authentication) continues from PR #100's verified head (`653b45c0`) on branch `css-operator-auth-2026-09-28`, to avoid re-triggering CI on the already-green PR #100 baseline._

This document records **evidence**, not intentions. The verification levels below are distinct and must not be conflated:

| Level | Meaning |
|---|---|
| IMPLEMENTED | Code exists on the branch |
| TESTED | Automated tests exist and pass locally, and the failing-before/passing-after or mutation evidence is noted |
| CI-VERIFIED | The five required CI workflows pass **on the named commit** |
| UAT-VERIFIED | Accepted in a user-acceptance cycle with real operators |
| EXTERNALLY VERIFIED | Confirmed by a party outside engineering (auditor, provider, regulator) |
| PRODUCTION-AUTHORIZED | Explicit owner authorization to activate in production |

## Safety invariants (unchanged by this work)

`execution_allowed=false` · `live_trading_blocked=true` · `broker_execution_armed=false` · `advisory_only=true`

No commit in this package adds collection initiation, customer charging, provider credentials, money movement, broker connectivity or execution capability. `scripts/run_css_full_test_readiness.py` reports `trading_execution_authority: false` on every head listed below. Every commercial API response restates the fail-closed posture.

## Increments

| Commit | Scope | Tests | Evidence |
|---|---|---|---|
| `39f81c3` (prior head) | Collections, receipts gate, fee/terminal accounting, reconciliation + durable exception history | 2031 full suite | CI-VERIFIED (5/5) |
| `b4a126a` COM-008 | RBAC (commercial grants on the existing PermissionEngine roles, fail closed), durable maker-checker, append-only hash-chained audit | +35 | 2066 local; mutation-checked (self-approval, payload hash, approve-time validation, compare-and-set, triggers, role check, unknown action); **CI-VERIFIED 5/5** |
| `26f7a2c` COM-009 | Append-only collection lifecycle history; deterministic PAID receipts; adjustment receipts; deterministic statements | +9 | 2075 local; failing-before shown (receipt non-determinism); mutation-checked (paid classification, receipt id, history triggers, re-reconcile overwrite, customer scope, original-receipt check). CI-VERIFIED on `640f4c6d` (5/5) |
| `e499446` COM-010 | Authenticated commercial governance API (bearer session, server-side RBAC, maker-checker over HTTP), env-gated mounting | +74 | 2149 local; mutation-checked (session acceptance, role selection, bearer scheme, hash pattern). CI failed on this SHA (test harness needed `httpx2` on CI's Starlette 1.7.0); fixed in `640f4c6d`, **CI-VERIFIED 5/5** there |
| `640f4c6d` | CI fix: dependency-free ASGI test client | 0 | Failure reproduced and fix verified in a clean venv matching CI; **CI-VERIFIED 5/5** |
| (next) | External audit anchoring: `write_anchor` / `verify_against_anchors` | +3 | Detects consistent chain rebuilds, truncation and in-place rewrites with recomputed hashes; refuses to anchor an invalid chain; mutation-checked |
| COM-011 (this increment) | Operator web authentication (`css_sign_on`-backed login/logout/change-password issuing real bearer sessions), salted password hashing with legacy-hash upgrade-on-login, and closing the unauthenticated trial enroll/cancel/status/agreement routes | +30 (`tests/test_operator_authentication.py`) | 2183 full suite locally passing (up from 2153); see "Control evidence" below for what each test proves; CI pending on this commit |

## Control evidence

**RBAC.** Grants live in `backend/security/permissions.py` (`COMMERCIAL_ROLE_GRANTS`). FINCON prepares; HEAD_FINCON and HEAD_COMPLIANCE approve; FINCON, AUDIT and COMPLIANCE view; audit history is limited to AUDIT, HEAD_AUDIT, HEAD_FINCON and HEAD_COMPLIANCE. SUPER_USER, ADMIN, TECH and trading roles get no commercial rights. Tests assert that a missing actor, identity or role, an unknown role, an unknown action and role-string escalation are all denied (`tests/test_commercial_controls.py`), and that every API route returns 403 for non-commercial and superuser sessions (`tests/test_commercial_governance_api.py`).

**Maker-checker.** `engine/commercial/commercial_controls.py`. Enforced properties, each with tests:
- maker ≠ checker;
- checker holds approve permission;
- replayed and concurrent approvals are rejected (compare-and-set; one success and one 409 under a forced race);
- stale or manipulated approvals are rejected by payload-hash mismatch;
- approval after an incompatible state change is rejected;
- rejection is final;
- one open action per object;
- idempotent requests;
- exactly-once execution;
- restart persistence;
- crash resume of approved-but-unexecuted actions.

**Audit.** `engine/commercial/commercial_audit.py`. It is append-only: there is no update or delete API, and triggers abort UPDATE and DELETE. A SHA-256 hash chain lets `verify()` detect tampering, including after the triggers are dropped. **It is not cryptographically immutable**: a party with write access to the file can rebuild a consistent chain. Anchoring the head hash externally is an open item.

**History, statements and receipts.**
- **History:** `engine/commercial/collection_history.py` records each state reached once. Terminal events add history, and the original settlement is retained.
- **Receipts:** `engine/reporting/commercial_receipts.py` issues PAID receipts only with SETTLED status, a settlement reference, a ledger transaction and a reconciliation timestamp. Receipt ids and timestamps are deterministic. Adjustment receipts reference the original PAID receipt.
- **Statements:** `engine/reporting/commercial_statements.py` produces deterministic statements that count as paid only money that is both settled and reconciled, and that refuse other customers' records. No balance-due claim is made.

## Control evidence — operator web authentication (COM-011)

**Identity and credential store.** `dashboard/auth/css_sign_on.py` remains the single canonical operator user store (`data/users.json`); no second identity provider was introduced. Password hashing was upgraded from unsalted SHA-256 to salted PBKDF2-HMAC-SHA256 (600,000 iterations, 16-byte salt, `pbkdf2_sha256$<iterations>$<salt>$<hash>` format). `verify_password()` still accepts a legacy unsalted digest so pre-existing records keep working, and `authenticate_credentials()` transparently rehashes to the new format on the next successful login (`needs_password_rehash`) — verified by `test_authenticate_credentials_upgrades_legacy_hash_on_successful_login` / `..._does_not_upgrade_hash_on_failed_login`. The password-history reuse check (`validate_new_password`) was updated to verify against historical hashes rather than compare hash strings, which is required now that hashing is salted (two hashes of the same password no longer match byte-for-byte).

**Session issuance.** `backend/app/auth/operator_login_router.py` adds `POST /auth/operator/login`, `POST /auth/operator/change-password`, `POST /auth/operator/logout` and `GET /auth/operator/me`, mounted into the real operator web dashboard (`dashboard/web/web_app.py`). Login verifies the password via `css_sign_on.authenticate_credentials` (inheriting its existing lockout-after-3-attempts and password-expiry policy unchanged) and, on success, issues a bearer session token through the pre-existing `backend/app/auth/token_store.TokenStore` — the same store the commercial governance API already resolved sessions against. The caller's `user_id` and `role` in the response always come from the stored record; a client-supplied `role` field is ignored (`test_client_supplied_role_field_is_ignored`). A freshly created operator cannot sign in until they complete `change-password` (`test_newly_provisioned_operator_must_change_password_before_login_succeeds`) — this was already `css_sign_on`'s policy for all callers, not a new restriction.

**Closing the unauthenticated commercial-trial routes.** `dashboard/runtime/trial_contract_router.py` previously accepted `customer_id` in the request body with zero authentication on all four routes (`agreement`, `enroll`, `cancel`, `status`) — anyone who knew or guessed a `customer_id` could enroll or cancel their trial. Two new commercial permissions were added (`commercial_trial_enroll`, `commercial_trial_cancel`, granted to FINCON and HEAD_FINCON only) and the router now requires a valid bearer session for every route: `commercial_view_obligations` for the two read routes, the new permissions for enroll/cancel. The per-route authorization logic was extracted out of `commercial_governance_router.py` into a shared, reusable helper (`engine/commercial/commercial_authorization.actor_from_bearer`) so both routers enforce identically and there is still exactly one commercial role model (`PermissionEngine`/`COMMERCIAL_ROLE_GRANTS`) — not a second one bolted onto the trial router.

**CSRF.** These routes take a bearer token in the `Authorization` header, never a cookie; a browser does not attach that header to a cross-site request automatically, so the classic cookie-CSRF class of attack does not apply here. No CSRF middleware was added because none is needed for this authentication shape — this reasoning should be revisited if a cookie-based session is ever added to `dashboard/web/web_app.py` itself (see limitation 3 below).

**Tests (`tests/test_operator_authentication.py`, 30 cases).** Positive: correct login issues a session with the real stored role; `change-password` on a forced-first-login account issues a working session; a role actually granted a permission can reach the corresponding trial route. Negative: wrong password, unknown user, lockout after repeated failures, missing/malformed/forged/tampered `Authorization` header (all 401), logout revokes the token (subsequent use is 401), a valid session with the wrong role is rejected on enroll/cancel (403, not 401 — proving the 401/403 split is on identity-vs-permission, not conflated), wrong current password on `change-password` (401). No test asserts on a client-supplied role being honored; `test_client_supplied_role_field_is_ignored` asserts the opposite.

**DEV/UAT identities.** `scripts/provision_dev_uat_operators.py` creates FINCON, HEAD_FINCON, AUDIT and HEAD_COMPLIANCE accounts (user ids `10001`–`10004`) with randomly generated passwords (`secrets.token_urlsafe(18)`), each forced to change password on first sign-in. Generated passwords are written once to `artifacts/dev_uat_operator_credentials.json` (gitignored, never printed to a log, never committed) and the script is idempotent (skips accounts that already exist). Run and verified locally on `df566eee`'s successor state; not run against, and must never be pointed at, a production store.

## Known limitations and findings

1. ~~Unauthenticated existing web routers~~ **Partially resolved (COM-011).** The commercial-trial routes (`enroll`/`cancel`/`status`/`agreement`) and the commercial governance API now both require an authenticated operator session with the correct commercial role. Still open: the other commercialization routers mounted in `dashboard/web/web_app.py` (`client_earnings_router`, `production_charging_router`, `commercialization_release_router`, `commercialization_operations_router`, `payment_collection_preflight_router`, `notification_delivery_preflight_router`, `launch_dossier_router`, `report_export_router`) were not audited or gated in this pass, and the dashboard's own HTML pages (`/dashboard`, `/positions`, etc.) still render without any session check. `dashboard/mobile/mobile_app.py` already has its own independent cookie-based session implementation for the mobile surface — it was not touched, unified with, or replaced by this work.
2. ~~No operator web identities~~ **Resolved (COM-011).** FINCON, HEAD_FINCON, AUDIT and HEAD_COMPLIANCE DEV/UAT identities are provisioned (`scripts/provision_dev_uat_operators.py`) and can obtain a real bearer session via `POST /auth/operator/login`. Production identities are explicitly out of scope and were not created.
3. **Trial enroll/cancel are direct actions, not maker-checker.** Unlike reconciliation-exception resolution, trial enrollment and cancellation execute immediately once an authorized FINCON/HEAD_FINCON session calls them — they do not go through `CommercialControls`' maker-checker flow. Given automatic-conversion billing risk is part of the trial model, routing these through maker-checker (a second, independent approver) is a reasonable follow-up hardening step, not done here.
4. **Statement scope.** Statement access is operator-scoped (any commercial viewer can read any customer). Customer self-service would additionally need an ownership check. No customer-facing self-service surface exists anywhere in this repository today (confirmed by search) — "IDOR between customers" does not yet apply because there is no customer-authenticated surface for it to apply to; the applicable risk today is exactly the operator-authentication gap this increment addresses.
5. **Legacy direct resolution path.** `ReconciliationService.resolve_exception` is still callable directly by internal code; only the API path is forced through maker-checker.
6. **Audit anchoring.** Checkpoint export and verification exist (`write_anchor`, `verify_against_anchors`). They only protect against a database-file writer if the anchor file lives on separate, write-once storage, which is a deployment responsibility, not yet in place. This is tamper-evident, not cryptographically immutable, and the API's own audit response says so explicitly.
7. **Mission Control UI.** It does not yet render the commercial views; the API is ready for it, and now has a real operator login to authenticate against.
8. **External and owner gates.** UAT with real operators, an external audit, provider integration and any production activation remain outstanding. None is claimed.

## Branch convergence register (open PRs vs `css-v1-completion-2026-09-13`)

This register compares file content, not ancestry, because shallow history truncates merge-bases.

| PR | Branch | Finding | Recommendation |
|---|---|---|---|
| #100 | css-commercial-collections-2026-09-19 | This work; ahead of base, 0 behind at last check | Continue |
| #81 | css-session10-readiness-reconcile | 3 of 4 changed files are identical in base; `api_bridge.py` differs (base carries a later version) | Superseded; close after the owner confirms |
| #72 | css-r7-mission-control-broker-portfolio-bridge | 8 of 10 files absent from base (Binance read-only adapter, canonical broker portfolio, Mission Control contracts) | Genuinely unmerged; broker-adjacent, so port separately with safety review |
| #71 | css-r6-tier1-broker-certification | Subset of #72 (same Binance read-only adapter and tests) | Superseded by #72 |
| #65 | css-ci001-gate2-maintenance-target | Gate-2 CI and py3.11 compatibility on the v1.0.1 maintenance line; base CI already compiles on 3.11 | Maintenance-line only; review before porting |
| #63 | css-cow001-dashboard-visibility-r1 | Dashboard script hotfix on the maintenance line | Maintenance-line only |
| #64, #66, #67 | maintenance-line evidence/docs | Documentation and evidence records only | Preserve as historical records; no code impact |

## Owner-only dependencies

- Authorization for any production collection, customer charging, provider credentials or money movement.
- ~~Authorization to provision operator identities and to choose the web authentication model~~ resolved: extend `css_sign_on` (approved), DEV/UAT identities provisioned (approved). Production operator credentials remain out of scope and were not created.
- UAT sign-off and any external certification.
- Disposition of the superseded PRs (#81, #71).
- Whether trial enroll/cancel should be routed through maker-checker (limitation 3 above) is a product/risk decision, not purely an engineering one.
