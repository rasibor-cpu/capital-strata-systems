# CSS Remediation Priority Queue

**Programme:** Release Gate 2 — Audit Remediation  
**Document type:** Strict execution order for all register items  
**Authority sources:** `CSS_AUDIT_REMEDIATION_REGISTER.md`, `CSS_RELEASE_BLOCKER_MATRIX.md`, `CSS_RELEASE_GATE_2_PLAN.md`  
**Baseline HEAD:** `4ea738d86c167373deccbe4edf217e929de4414d`

Rules:

1. Lower priority number executes first.
2. An item may start only when listed dependencies are CLOSED or WAIVED.
3. Parallelism is allowed only where dependencies and ownership do not conflict.
4. Every item maps to a confirmed Master Audit finding.

---

## Strict execution queue

| Priority | Remediation ID | Why it is next | What it unlocks | Dependencies |
| ---: | --- | --- | --- | --- |
| 1 | AR-001 | Release truth must be frozen before any remediation is claimed complete | Honest status page; prevents false GO reuse | None |
| 2 | AR-003 | Critical work needs named owners before parallel waves | Accountable execution of all later ARs | None |
| 3 | AR-004 | Operators need a single entry document aligned to AR-001 | Clear Gate 2 communication; README honesty | AR-001 |
| 4 | AR-002 | Evidence custody must exist before generating new proof | SHA-bound artifacts; clean baseline discipline | AR-001 |
| 5 | AR-027 | Fast misrepresentation fix; no dependency on heavy engineering | Removes false IBKR-ready signal immediately | None |
| 6 | AR-005 | Known red test blocks current-SHA certification narrative | Green/waived suite baseline for AR-012 | None — **CLOSED (Batch B)** |
| 7 | AR-009 | Fail-open health invalidates every readiness certificate | Trustworthy ops health; prerequisite for OAT | None — **CLOSED (Batch B)** |
| 8 | AR-010 | Certification health PASS-on-absence equally invalidates Phase 181 | Honest certification health dimension | None — **CLOSED (Batch B)** |
| 9 | AR-008 | Lifecycle divergence corrupts paper trading records and analytics | Safe paper close path; integrity package | None — **CLOSED (Batch B)** |
| 10 | AR-006 | Must decide singular paper trading authority before execution redesign | Clear engine ownership for AR-007 | AR-001 — **CLOSED (Batch B)** |
| 11 | AR-007 | Synthetic accept is the strongest engineering misrepresentation risk | Honest execution semantics for Gate 2 | AR-006, AR-008 — **CLOSED (Batch B)** |
| 12 | AR-034 | Risk lean-path can approve oversized notionals even in paper | Safer risk gating before broader tests | None |
| 13 | AR-023 | Default credentials are immediate production-exposure blockers | Secure mobile/auth foundation | None — **CLOSED (Wave 2)** |
| 14 | AR-024 | Mutations without auth make LAN/production hosts unsafe | Secure API boundary for OAT/deploy | AR-023 — **CLOSED (Wave 2)** |
| 15 | AR-026 | Legacy OANDA writes coexist with read-only claims | Broker safety boundary for fresh read proofs | None — **CLOSED (Wave 2)** |
| 16 | AR-032 | Config bootstrap/aliases affect all broker/security evidence | Stable environment for AR-033/040 | AR-002, AR-005 — **CLOSED (Wave 2)** |
| 17 | AR-033 | Secret authority migration needed before real broker/notify proofs | Lease-only credential use | AR-032 — **PARTIALLY CLOSED (Wave 2 demotion)** |
| 18 | AR-012 | Current-SHA compile/regression is the evidence backbone | Unlocks OAT/endurance/recert | AR-002, AR-005 — **CLOSED (Wave 3)** |
| 19 | AR-028 | Operations service must run with required checkers after AR-009 | Real ops health for OAT | AR-009 — **CLOSED (Wave 3 wiring)** |
| 20 | AR-040 | Fresh Coinbase/OANDA read-only evidence after boundary fixes | Broker dimension for Phase 181 | AR-026, AR-032, AR-033 — **PARTIALLY CLOSED (Batch 2 update; live residual)** |
| 21 | AR-013 | OAT is a Phase 181 hard dimension | Operational acceptance evidence | AR-009, AR-012, AR-028 — **PARTIALLY CLOSED (Batch 2: 88.89%; SHUTDOWN residual)** |
| 22 | AR-029 | Metrics persistence needed before credible endurance samples | Telemetry for AR-014/044 | AR-028 — **CLOSED (Wave 2 honesty)** |
| 23 | AR-014 | Wall-clock endurance replaces simulated certificates | Endurance dimension for Phase 181 | AR-012, AR-029 — **PARTIALLY CLOSED (Batch 2; 72h residual)** |
| 24 | AR-015 | Restore drill required for DR readiness | Continuity dimension for Phase 181 | AR-002, AR-016*(start)* — **CLOSED (Wave 3 drill)** |
| 25 | AR-044 | Prevents modeled performance from re-entering certificates | Clean performance claims | AR-014, AR-029 — **CLOSED (Wave 3)** |
| 26 | AR-045 | Blocks fixture URIs from minting production certificates | Honest Phase 181 re-entry | AR-011*(prep)*, AR-041*(parallel)* — **CLOSED (Wave 3)** |
| 27 | AR-017 | Product MVP stops catalogue false completeness | Institutional honesty; scopes AR-047/042 | AR-001 — **PARTIALLY CLOSED (Wave 4)** |
| 28 | AR-047 | Board/investor/regulatory must be in or explicitly out | Prevents commercial overclaim | AR-017 — **CLOSED (Wave 4 OUT OF SCOPE)** |
| 29 | AR-018 | 182A/EIS must be committed or deferred | Dashboard honesty | AR-002, AR-017 — **CLOSED (Wave 4 DEFER)** |
| 30 | AR-042 | Executive report provenance after MVP decision | Management vs audited clarity | AR-017, AR-018 — **PARTIALLY CLOSED (Wave 4)** |
| 31 | AR-022 | Alerting must be real or labelled non-operational | Ops readiness / no false pager claims | AR-033, AR-028 — **PARTIALLY CLOSED (Wave 4)** |
| 32 | AR-025 | HTTPS/PWA installability for production mobile exposure | Secure install path | AR-016*(partial)* — **PARTIALLY CLOSED (Wave 2/4)** |
| 33 | AR-031 | Options advisory data activation after broker/secrets ready | Removes DATA_DEPENDENCY_BLOCKED where approved | AR-040, AR-033 — **CLOSED (Wave 2 honesty)** |
| 34 | AR-019 | Canonical audit ledger supports governance/ISO evidence | Correlated audit trail | AR-033 |
| 35 | AR-041 | Real governance evidence intake after custody exists | Non-fixture governance scores | AR-002, AR-019 |
| 36 | AR-011 | Phase 181 recert only after evidence-producing ARs land | Production certification decision | AR-012, AR-013, AR-014, AR-015, AR-009, AR-010, AR-045 — **CLOSED (Batch 2 NOT_CERTIFIED disposition)** |
| 37 | AR-016 | CI/CD path required for controlled deployment claim | Deployment readiness dimension | AR-012, AR-001 — **CLOSED (Final Close-Out Batch 1)** |
| 38 | AR-043 | Quality gates harden CI beyond compile/tests | Sustainable release engineering | AR-016, AR-012 |
| 39 | AR-020 | ISO 27001 evidence after governance intake | Compliance track (may be post-exit if deferred) | AR-041, AR-019 |
| 40 | AR-021 | ISO 9001 evidence after governance intake | Compliance track (may be post-exit if deferred) | AR-041 |
| 41 | AR-035 | Small advisory committee honesty fix | Cleaner committee semantics | None |
| 42 | AR-036 | Portfolio history corruption fail-closed | Stronger advisory persistence | None |
| 43 | AR-038 | Runtime heartbeat hard transition | Stronger runtime authority | AR-037*(preferred)* |
| 44 | AR-037 | Authority consolidation reduces operator contradictions | Stable snapshots/readiness displays | AR-038*(iterative)* |
| 45 | AR-039 | MC session enforcement after API auth exists | Hardened read-only plane | AR-024 |
| 46 | AR-046 | Production IdP/MFA if commercial exposure required | Commercial auth readiness | AR-023, AR-024 |
| 47 | AR-030 | Monitoring retention/consolidation after alerts exist | Durable ops monitoring | AR-022, AR-029 — **CLOSED (Wave 2 pager honesty)** |

\*AR-015 may begin restore planning in parallel with AR-016 design, but measured restore evidence should use the intended backup targets from the deployment profile.

---

## Wave view (same order, grouped)

### Wave 0 — Freeze and ownership
1–6: AR-001, AR-003, AR-004, AR-002, AR-027, AR-005 — **COMPLETE** (AR-005 closed in Batch B)

### Wave 1 — Integrity fail-closed
7–12: AR-009, AR-010, AR-008, AR-006, AR-007 — **COMPLETE (Batch B)**; AR-034 remains OPEN

### Next executable Critical items
**Gate 3 OV-001 COMPLETE** — OAT 100%; AR-013 CLOSED; AR-040 partial (truthful broker FAIL_CLOSED)  
**CONDITIONALLY APPROVE** for 72-hour endurance (AR-014) when authorized  
Do not begin endurance until conditions in `CSS_EXECUTIVE_OPERATIONAL_VALIDATION_REPORT_OV001.md` are accepted  
Batch 3 honesty residuals (AR-017/022) remain separately authorized  
Wave model RETIRED — see `docs/release/CSS_RG2_FINAL_CLOSEOUT_PLAN.md`
### Wave 2 — Security and broker boundaries
13–17: AR-023, AR-024, AR-026, AR-032, AR-033 — **COMPLETE** (see Wave 2 executive report; AR-033 partial)

### Wave 3 — Evidence machine
18–26: AR-012, AR-028, AR-040, AR-013, AR-029, AR-014, AR-015, AR-044, AR-045 — **COMPLETE** (see Wave 3 executive report; 013/014/040 partial)

### Wave 4 — Product honesty and surfaces
27–33: AR-017, AR-047, AR-018, AR-042, AR-022, AR-025, AR-031 — **COMPLETE** (see Wave 4 executive report; 017/022/042/025 partial; 031 already CLOSED)

### Wave 5 — Recertify and harden
34–40: AR-019, AR-041, AR-043, AR-020, AR-021 — backlog; AR-011 **CLOSED (Batch 2)**; AR-016 **CLOSED (Batch 1)**

### Wave 6 — Residual hardening
41–47: AR-035, AR-036, AR-038, AR-037, AR-039, AR-046, AR-030

---

## Parallelization guide

| Can run in parallel | Condition |
| --- | --- |
| AR-027 with Wave 0 | Always |
| AR-009/010 with AR-005/012 prep | After owners assigned |
| AR-023/024 with AR-008/006 | Different owners |
| AR-017/047 product decisions with Wave 1 | No code dependency |
| AR-035/036 residual with Wave 5 | After Critical blockers closed |

| Must not parallelize | Reason |
| --- | --- |
| AR-011 before AR-012/013/014/015/009/010/045 | Recert would reuse invalid evidence |
| AR-007 before AR-006 | Execution redesign needs chosen authority |
| AR-040 before AR-026/032/033 | Boundary/config/secrets prerequisites |
| AR-014 before AR-029 | Need durable metrics/samples |

---

## Gate 2 minimum path (Critical-only subsequence)

If product authority authorizes a **minimum** Gate 2 exit focused only on Production Certification integrity:

```text
AR-001 → AR-003 → AR-002 → AR-005 → AR-009 → AR-010 → AR-008 → AR-006 → AR-007
 → AR-023 → AR-024 → AR-026 → AR-027 → AR-012 → AR-028 → AR-013 → AR-014 → AR-015
 → AR-017 → AR-022 → AR-045 → AR-011 → AR-016
```

All other ARs remain on the full queue for hardening/compliance/commercial readiness.

---

## Queue control

- Queue amendments require an update to `CSS_AUDIT_REMEDIATION_REGISTER.md` first.
- Completed items move to CLOSED in the register; priority numbers are stable historical indices and are not reused.
- New findings receive the next AR ID and are inserted by dependency, not by appending blindly to the end.

---

*End of CSS Remediation Priority Queue. This document does not authorize code changes, deployment, restart, broker authentication, or live trading.*
