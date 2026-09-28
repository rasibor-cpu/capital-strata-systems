# CSS Commercial Collections — Closure Evidence Package

_Maintained by the Claude engineering lane. Repository `rasibor-cpu/capital-strata-systems`, branch `css-commercial-collections-2026-09-19`, PR #100 (draft) → `css-v1-completion-2026-09-13`._

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

## Known limitations and findings

1. **Unauthenticated existing web routers.** The existing commercialization routers in `dashboard/web/web_app.py` have no request authentication. These include `POST /api/v1/commercial-trial/enroll` and `/cancel`, which act on any `customer_id`, and the readiness queries. This predates PR #100. Fixing it requires a web sign-in for operators and customers, which does not exist today.
2. **No operator web identities.** The only web session is the superuser's (role `superuser`), which maps to no commercial permission. The governance API is therefore unusable until FINCON, HEAD_FINCON, AUDIT and compliance operator identities are provisioned. This is correct fail-closed behaviour.
3. **Statement scope.** Statement access is operator-scoped (any commercial viewer can read any customer). Customer self-service would additionally need an ownership check.
4. **Legacy direct resolution path.** `ReconciliationService.resolve_exception` is still callable directly by internal code; only the API path is forced through maker-checker.
5. **Audit anchoring.** Checkpoint export and verification exist (`write_anchor`, `verify_against_anchors`). They only protect against a database-file writer if the anchor file lives on separate, write-once storage, which is a deployment responsibility, not yet in place.
6. **Mission Control UI.** It does not yet render the commercial views; the API is ready for it.
7. **External and owner gates.** UAT with real operators, an external audit, provider integration and any production activation remain outstanding. None is claimed.

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
- Authorization to provision operator identities and to choose the web authentication model (item 1–2 above).
- UAT sign-off and any external certification.
- Disposition of the superseded PRs (#81, #71).
