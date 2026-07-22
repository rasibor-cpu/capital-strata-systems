# CSS Release Gate 2 Plan

**Programme:** Release Gate 2 — Audit Remediation  
**Phase:** AR-001 planning complete; execution not started  
**Document type:** Project governance only  
**Baseline HEAD:** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Authority sources:**
- `CSS_V1_MASTER_COMPLETION_AUDIT.md`
- `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`
- CSS Executive PMO Pack — **not found in repository**; objectives below are inferred from the Master Audit production/commercial assessments
- CSS Executive Audit Remediation Register — **not found**; superseded by the canonical register above

---

## 1. Executive summary

Release Gate 2 converts the CSS V1 Master Completion Audit into an executable remediation programme whose sole purpose is to make **Production Certification** an honest, evidence-backed outcome.

Gate 1 / RC1.1 established a controlled-paper, advisory, read-only baseline at HEAD `4ea738d`. Gate 2 does **not** authorize live trading. It closes the gap between:

- what the platform can already do under fail-closed paper/advisory controls, and
- what must be true before CSS may claim Production Certification.

Current authoritative posture remains:

| Surface | Result |
| --- | --- |
| Controlled paper | `CERTIFIED_CONTROLLED_PAPER_OPERATION` |
| Production certification | `NOT CERTIFIED` |
| Live trading | `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY` |

Gate 2 succeeds only when every Critical remediation is **CLOSED** or **WAIVED** with written residual-risk acceptance, and Phase 181 can be re-run using verified observations rather than fixtures.

---

## 2. Objectives

1. Establish a single remediation backlog with unique IDs (AR-001…AR-047).
2. Eliminate false production-complete claims and release-authority contradictions.
3. Close engineering integrity blockers that make V1 production claims unsafe:
   - synthetic execution acceptance
   - non-singular trading authority
   - asset lifecycle divergence
   - health fail-open scoring
4. Capture current-SHA compile, regression, OAT, endurance, and DR evidence.
5. Create a real CI/CD and evidence-custody path sufficient for controlled deployment certification.
6. Define honest institutional reporting and executive-dashboard scope for V1/Gate 2.
7. Harden security boundaries required for production exposure (credentials, sessions, broker write isolation).
8. Preserve live-execution blocks throughout; live micro-pilot remains a separate future programme.

---

## 3. Success criteria

Gate 2 is successful when all of the following are true:

1. Canonical remediation register is complete and traceable to Master Audit findings.
2. No active release document claims production certification without matching Phase 181 verified evidence.
3. Worktree/evidence custody rules prevent untracked packages from being treated as release proof.
4. All Critical AR items are CLOSED or WAIVED with sign-off.
5. Current release-candidate SHA has archived:
   - compile evidence
   - bounded regression evidence
   - OAT evidence
   - endurance evidence (wall-clock)
   - backup/restore evidence
6. Health and certification scoring fail closed on missing checks/telemetry.
7. Synthetic “accepted” execution cannot be presented as an executed order.
8. IBKR placeholder and OANDA legacy write paths cannot present as production-ready/executable.
9. Notification and monitoring either operate for real or are explicitly labelled non-operational.
10. Institutional catalogue claims match generatable MVP scope.
11. Safety posture unchanged: no live execution enablement as a side effect of Gate 2.

---

## 4. Exit criteria

### Must-pass (Release Gate 2 exit)

| ID | Exit criterion | Linked ARs |
| --- | --- | --- |
| X1 | Canonical status doc supersedes contradictory GO/100% production claims | AR-001, AR-004 |
| X2 | Release-candidate SHA evidence pack complete and SHA-bound | AR-002, AR-011, AR-012 |
| X3 | Phase 153i resolved or formally waived | AR-005 |
| X4 | Trading/execution language matches actual paper behaviour | AR-006, AR-007 |
| X5 | Asset lifecycle strict and taxonomy-aligned | AR-008 |
| X6 | Health/certification fail-closed on absence | AR-009, AR-010 |
| X7 | OAT + endurance + DR evidence verified | AR-013, AR-014, AR-015 |
| X8 | CI gates exist; CD path documented; false automation claims removed | AR-016 |
| X9 | Institutional MVP defined; catalogue honesty restored | AR-017, AR-047 |
| X10 | Default credentials removed; mutation auth boundaries enforced | AR-023, AR-024 |
| X11 | OANDA legacy writes isolated; IBKR ready=false | AR-026, AR-027 |
| X12 | Phase 181 re-evaluated on verified evidence | AR-011, AR-045 |
| X13 | Named owners assigned for Critical domains | AR-003 |

### Explicitly out of Gate 2 exit (deferred unless product authority expands scope)

- Live trading enablement / micro-pilot execution
- Full 191-report institutional catalogue completion
- Accredited ISO 27001/9001 certification
- Full IdP/MFA commercial identity (may be required for commercial Gate; optional for controlled-deploy cert if scoped)
- IBKR production implementation
- Autonomous AI/learning auto-application

---

## 5. Critical path

```text
AR-001 Release truth
   └─ AR-004 README/status
   └─ AR-002 Evidence custody
         └─ AR-012 Current-SHA tests
               └─ AR-005 Phase 153i
               └─ AR-009/010 Health fail-closed
                     └─ AR-013 OAT
                     └─ AR-014 Endurance
                     └─ AR-015 DR
                           └─ AR-011 Phase 181 recert
                                 └─ AR-016 CI/CD
                                       └─ GATE 2 EXIT (controlled deployment certification eligible)

Parallel integrity track (must join before AR-011):
AR-006 Trading authority ──┐
AR-007 Execution honesty ──┼──► integrity package
AR-008 Lifecycle strict ───┘

Parallel security/broker track (must join before AR-011 if production exposure claimed):
AR-023 Credentials ─► AR-024 API auth
AR-026 OANDA boundary ─► AR-040 fresh read-only evidence
AR-027 IBKR quarantine
AR-032/033 Config + secrets

Parallel product-honesty track:
AR-017 Report MVP ─► AR-042/018 Executive scope
AR-022 Notifications honesty or real delivery
```

---

## 6. Dependencies

| Dependency | Why required |
| --- | --- |
| Master Completion Audit freeze | Findings must not churn mid-gate without register amendment |
| Product authority for MVP scope | AR-017/AR-018/AR-047 need explicit in/out decisions |
| Operator authorization for OAT/endurance/DR | Evidence cannot be fabricated in CI alone |
| Secret/store access for real notification/broker read proofs | Only under existing fail-closed controls |
| No live-trading authorization | Gate 2 must not expand execution authority |
| Clean evidence store location | Outside dirty worktree or governed archive |

---

## 7. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep into live trading | Safety regression | Hard exclusion in exit criteria |
| Treating fixture tests as production evidence | False certification | AR-045 rejects synthetic URIs in production profile |
| Committing Phase 181A/182A without review | Unstable baseline | AR-002/AR-018/AR-032 controlled review |
| Fixing labels without fixing execution honesty | Misrepresentation | AR-006/AR-007 required before recert |
| Endurance simulated again | Invalid Gate exit | AR-014 wall-clock requirement |
| Expanding institutional catalogue instead of MVP | Delay without honesty | AR-017 product decision first |
| Ownerless Critical ARs | Non-execution | AR-003 before mid-gate |

---

## 8. Recommended execution order

See also `CSS_REMEDIATION_PRIORITY_QUEUE.md` for the strict ranked queue.

### Wave 0 — Governance freeze (days 1–3)

AR-001 → AR-003 → AR-004 → AR-002 → AR-027 → AR-005

### Wave 1 — Integrity blockers (days 3–15)

AR-009 → AR-010 → AR-008 → AR-006 → AR-007 → AR-034

### Wave 2 — Security and broker boundaries (parallel with Wave 1 where possible)

AR-023 → AR-024 → AR-026 → AR-032 → AR-033 → AR-040

### Wave 3 — Evidence generation (days 10–25)

AR-012 → AR-028 → AR-013 → AR-029 → AR-014 → AR-015 → AR-044 → AR-045

### Wave 4 — Product honesty and ops surfaces (parallel)

AR-017 → AR-047 → AR-018 → AR-042 → AR-022 → AR-025 → AR-031

### Wave 5 — Recertification and Gate exit (days 20–30)

AR-011 → AR-016 → AR-043 → AR-041 → AR-019/020/021 (as scoped) → Gate 2 sign-off

---

## 9. Governance rules for Gate 2 execution

1. No application code changes in AR-001 planning documents (this phase).
2. Future code remediations must reference an AR ID in commit/PR body.
3. Waivers require severity, residual risk, expiry, and approver.
4. Live execution flags must remain fail-closed unless a separate programme authorizes otherwise.
5. Register amendments require Master Audit delta or new evidence note.

---

## 10. Deliverables checklist for AR-001 (this phase)

| Deliverable | Path | Status |
| --- | --- | --- |
| Audit Remediation Register | `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md` | Created |
| Release Gate 2 Plan | `docs/release/CSS_RELEASE_GATE_2_PLAN.md` | Created |
| Release Blocker Matrix | `docs/release/CSS_RELEASE_BLOCKER_MATRIX.md` | Created |
| Remediation Priority Queue | `docs/release/CSS_REMEDIATION_PRIORITY_QUEUE.md` | Created |

---

*End of CSS Release Gate 2 Plan. This document does not authorize code changes, deployment, restart, broker authentication, or live trading.*
