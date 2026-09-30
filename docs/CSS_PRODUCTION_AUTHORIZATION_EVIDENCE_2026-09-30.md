# CSS Production Authorization — Evidence and Decision (2026-09-30)

_Record of the governed production-authorization review that the owner requested on 2026-09-30. It keeps production authorization separate from any trading, broker, money-movement or charging authority. It contains no credential, password, key or session token._

## Owner authorization

The owner (Robert Asibor) authorized CSS to proceed through the governed **production authorization process** on 2026-09-30. That authorization explicitly excluded live funded trading, broker execution, real-money movement, customer charging and refunds.

## Identity

| Item | Value |
|---|---|
| Repository | `C:\rasib\source\capital-strata-systems` (worktree `.claude/worktrees/css-continuation-message-451a81`) |
| Branch | local `css-com015-work` → remote `css-operator-auth-2026-09-28` (PR head) |
| QUALIFIED_CODE_HEAD | `720d9b39df2a16d303d24e2abd4f9ea1a5cec50d` (last application-code change) |
| Prior evidence head | `fd6df7cfd18927fab6e1efc3619803ee56f5b2ef`: docs-only (`docs/CSS_OWNER_UAT_EVIDENCE_2026-09-29.md`, `docs/CSS_COMMERCIAL_CLOSURE_EVIDENCE.md`); equal to `origin/css-operator-auth-2026-09-28` at review start |
| FINAL_PRODUCTION_EVIDENCE_HEAD | the commit that adds this document (docs-only; it does not re-qualify application code) |
| PR #101 | OPEN, DRAFT, MERGEABLE, base `css-commercial-collections-2026-09-19`. Not merged, and its state was not changed |
| RC tag | `css-engineering-rc-2026-09-29` → `9335e866585d1b02319a5a56b1dfc7d8ebb35150`. Local only, not on the remote, and not moved |
| Post-UAT work | none: no commit on any ref after `fd6df7cf` (2026-09-29 22:47 -0400) |

## Test / CI evidence (reused, not re-run)

Application code has not changed since `720d9b39`. `fd6df7cf` and this commit change documentation only, so the existing exact-head CI still applies:

- `fd6df7cf`: CSS Full Regression Remote `36661458540` SUCCESS, **2567 passed**, 0 failed (14 warnings); `css_governance` `36661462503` SUCCESS.
- `720d9b39`: Full Regression `36660608527` (2567 passed), Full Test Release Candidate `36660610748` (2567 passed, readiness authority flags false), `css_governance` `36660612738`, all SUCCESS.

No local test run was performed for this review.

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| Authentication | PASS (application level) | Server-issued sessions, CSRF on every cookie mutation (COM-014/015), no default bootstrap password with a one-time local first-claim (`0cfcf6f2`), and no unauthenticated enrollment or cancellation. Owner UAT items 1–3 and 17–18 |
| RBAC | PASS (application level) | FINCON / HEAD_FINCON / AUDIT / HEAD_COMPLIANCE are enforced server-side. AUDIT cannot enroll (UAT item 5) |
| Maker/checker | PASS | Maker 10001 cannot self-approve; checker 10002 approved; state became EXECUTED only after approval; audit REQUEST → APPROVE → EXECUTE chain verifies (UAT items 9–11, 15) |
| Commercial governance | PASS (non-charging scope) | Trial/agreement governance holds. Payments, allocations, collection authorities, provider configurations and charge policies: 0 rows. `CUSTOMER_CHARGING_ENABLED=false`, `MONEY_MOVEMENT_ALLOWED=false` |
| Audit / data | PASS (application level) | Commercial and auth audit hash chains verify, with no credential in either log |
| Security / operations certification | **BLOCKED** | `docs/CSS_PRODUCTION_SECURITY_CERTIFICATION_CHECKLIST.md` status is "NOT YET CERTIFIED". It has no production evidence for secrets storage, TLS, monitoring/alerting, dependency review or independent reviewer approval. `docs/production/requests/CSS_SECURITY_OPERATIONS_EVIDENCE_REQUEST.md` has not been answered |
| Rollback / recovery | **BLOCKED** | `docs/CSS_COMMERCIAL_ROLLBACK_PLAN.md` is documented, but its status is "REQUIRES PRODUCTION-LIKE TEST EVIDENCE". The real-environment encrypted off-site backup and restore/rollback drill (BACKUP_RESTORE) has not been performed |
| Production closure register | **BLOCKED** | `docs/production/CSS_SUNDAY_PRODUCTION_CLOSURE_REGISTER_2026-09-20.md` lists all 13 workstreams as EXTERNAL BLOCKED. `assess_production_closure()` returns `production_authorized=False` when no validated production evidence package exists, and none exists |

## Trading safety posture (unchanged)

```
EXECUTION_ALLOWED=false
LIVE_TRADING_BLOCKED=true
BROKER_UNARMED=true          (BROKER_EXECUTION_ARMED=false)
ADVISORY_ONLY=true
```

The source defaults are in `dashboard/runtime/mission_control_state.py` and `dashboard/runtime/runtime_operational_state.py`. The last observed state was recorded at owner-UAT close.

## Blockers

These are all external and non-trading. Each needs a real environment, an outside reviewer or a signed artifact, and none can be produced honestly from this repository:

1. SECURITY_OPERATIONS: independently verified production controls (secrets storage, TLS with fail-closed transport, monitoring/alerting, dependency/vulnerability review).
2. BACKUP_RESTORE: real-environment encrypted off-site backup plus a restore/rollback drill.
3. INCIDENT_TABLETOP: signed operator tabletop.
4. PRODUCTION_UAT: production-like UAT in a deployed environment, beyond the owner's local `127.0.0.1` / `CSS_ENV=development` session.
5. JURISDICTION_LEGAL_REVIEW / SERVICE_MODE_APPROVALS: counsel approval of the exact agreement/version/jurisdiction.
6. No deployed production environment exists; the only runtime evidence is local development.
7. OWNER_SIGNOFF: the register requires the APPROVE decision **after** all the evidence above has been reviewed. The owner's instruction to proceed is recorded, but it cannot stand in for missing evidence (checklist certification rule: "a verbal assertion cannot substitute for this record").

The payment-provider, payment-authority, notification-provider/policy and reconciliation workstreams gate customer charging, which remains unauthorized. They are not required for a non-charging release, but they stay open.

## Known limitations

- Populated advice-profitability / client-earnings screens have not been tested with an owner-approved dataset (owner UAT item 7b).
- Owner UAT ran locally on port 8001 in development mode.
- The RC tag exists only locally.

## Decision

```
OWNER_PRODUCTION_AUTHORIZATION=YES
PRODUCTION_RELEASE_AUTHORIZED=NO
CSS_PRODUCTION_STATUS=BLOCKED

LIVE_FUNDED_TRADING_AUTHORIZED=NO
BROKER_EXECUTION_AUTHORIZED=NO
REAL_MONEY_MOVEMENT_AUTHORIZED=NO
REAL_CUSTOMER_CHARGING_AUTHORIZED=NO
```

The application code at `720d9b39` is engineering-qualified and owner-UAT accepted. Production release stays blocked only on the external, environment-level evidence listed above. Once that evidence is supplied through `docs/production/CSS_PRODUCTION_EVIDENCE_HANDOFF_GUIDE.md` and validates, this decision can be re-assessed without further application development.
