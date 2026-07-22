# CSS Release Gate 2 — Final Close-Out Plan

**Programme:** Release Gate 2 — Final Close-Out  
**Effective:** 2026-07-22  
**Authority sources:** Remediation Register, Blocker Matrix, Priority Queue, repository HEAD evidence  
**Prior approval:** Wave 4 executively approved  
**Wave model:** **RETIRED** — remaining work uses execution batches only  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`

This plan is the authoritative remaining-work baseline. Historical Waves 0–4 are complete context only.

---

## 1. Re-baseline (repository-derived)

### 1.1 Remediation status counts

| Status | Count | IDs |
| --- | ---: | --- |
| **CLOSED** | 25 | AR-001…010, 012, 015, 018, 023–024, 026–032, 044–045, 047 |
| **PARTIALLY CLOSED** | 8 | AR-013, 014, 017, 022, 025, 033, 040, 042 |
| **OPEN** | 14 | AR-011, 016, 019, 020, 021, 034, 035, 036, 037, 038, 039, 041, 043, 046 |

### 1.2 Production blockers

| Status | Count | IDs |
| --- | ---: | --- |
| Fully **OPEN** | **1** | **RB-011** (Deployment/CD / AR-016) |
| **PARTIALLY CLOSED** | 4 | RB-001, RB-009, RB-010, RB-012 |
| **CLOSED** | 11 | RB-002…008, 013–016 |

### 1.3 Certification evidence gaps (RB-001 / AR-011 path)

| Gap | Residual ARs | Notes |
| --- | --- | --- |
| Full OAT PASS | AR-013 | Observation pack incomplete |
| 72h wall-clock endurance | AR-014 | Sample only; not duration-complete |
| Fresh broker read-only PASS/FAIL | AR-040 | Pack structure; live probe residual |
| Phase 181 recert package | AR-011 | Blocked until evidence residuals land |
| Fixture rejection | AR-045 | CLOSED (production profile) |
| Compile/regression Class B | AR-012 | CLOSED |

### 1.4 Critical path judgment

Shortest safe Gate 2 exit:

```text
CLOSE RB-011 (AR-016)
  → Complete certification evidence residuals (013/014/040)
  → AR-011 Phase 181 recert
  → Close remaining Critical honesty partials (017/022 → RB-009/010)
  → Gate 2 exit (controlled deployment; live trading still blocked)
```

Medium/Low ARs and ISO/MFA (019–021, 034–039, 041, 043, 046) are **not** on the minimum Critical-blocker path unless product authority expands Gate 2 scope.

---

## 2. Remaining work packages (maximum three)

### Batch 1 — Deployment readiness (EXECUTE NOW)

| Field | Content |
| --- | --- |
| **Objective** | Eliminate the last fully OPEN production blocker (RB-011) via honest CI gates + documented manual-with-approvals CD |
| **Included ARs** | **AR-016** (primary). Light honesty contract only — do not absorb AR-043 full lint/type/security platform |
| **Included Blockers** | **RB-011** |
| **Dependencies** | AR-012, AR-001 (CLOSED) |
| **Estimated effort** | M (honesty + CI fix + playbook; no K8s) |
| **Exit criteria** | (1) Valid CI workflow(s) fail-closed on compile + bounded pytest for release/PR paths; (2) documented controlled CD path (manual-with-approvals allowed); (3) no false “automated deploy” claims in Gate-2 authority docs; (4) RB-011 CLOSED or PARTIALLY CLOSED with explicit residual named |

### Batch 2 — Certification evidence completion

| Field | Content |
| --- | --- |
| **Objective** | Close remaining evidence gaps that keep Phase 181 `NOT CERTIFIED` |
| **Included ARs** | AR-013 residual, AR-014 residual, AR-040 residual, then **AR-011** |
| **Included Blockers** | RB-001, RB-012 (partials → CLOSE if evidence meets acceptance) |
| **Dependencies** | Batch 1 preferred (deployment honesty); AR-012/015/045 CLOSED |
| **Estimated effort** | L–XL (operator-authorized OAT/endurance/broker probes) |
| **Exit criteria** | Class B evidence packages for OAT/endurance/broker meet production-profile authority; Phase 181 summary either CERTIFIED_FOR_CONTROLLED_DEPLOYMENT with real refs **or** NOT_CERTIFIED with only non-Gate-2 residuals listed; AR-011 dispositioned |

### Batch 3 — Critical honesty residuals + Gate 2 exit hygiene

| Field | Content |
| --- | --- |
| **Objective** | Finish Critical product-honesty partials still mapped to production blockers; freeze Gate 2 exit scope |
| **Included ARs** | AR-017 residual, AR-022 residual (RB-009/010); AR-025 residual if HTTPS install required for claimed mobile production; optional AR-033/042 honesty residuals |
| **Included Blockers** | RB-009, RB-010 (→ CLOSE if acceptance met); RB-011 already closed in Batch 1 |
| **Dependencies** | Batch 1; Batch 2 for certification claim |
| **Estimated effort** | M–L |
| **Exit criteria** | No Critical RB fully OPEN or PARTIAL without signed waiver; canonical release status updated; Gate 2 exit checklist signed; live trading remains BLOCKED |

**Explicitly deferred beyond Gate 2 Final Close-Out (unless scope expands):**  
AR-019, 020, 021, 034, 035, 036, 037, 038, 039, 041, 043, 046 — track in post–Gate 2 hardening backlog.

---

## 3. Optimization rationale

| Choice | Why |
| --- | --- |
| Batch 1 = AR-016 only | Sole fully OPEN Critical blocker; lowest regression if honesty+CI scoped tightly |
| Batch 2 = evidence → AR-011 | Direct path to Production Certification (RB-001) |
| Batch 3 = remaining Critical honesty | Clears RB-009/010 without reopening Wave 4 feature work |
| Defer AR-034 from Batch 1 | Different subsystem; does not unlock RB-011 or Phase 181 |
| No Wave revival | Repository state already collapsed remaining Critical work |

---

## 4. Non-claims

- Does not authorize live trading  
- Does not authorize Release Gate 3  
- Does not claim Phase 181 CERTIFIED until Batch 2 completes  
- Does not invent Kubernetes/full CD automation  

---

## 5. Batch 1 execution status

**Status:** COMPLETE (2026-07-22)  
**Report:** `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_BATCH1_DEPLOYMENT.md`  
**Outcome:** AR-016 **CLOSED**; RB-011 **CLOSED**  

## 6. Batch 2 execution status

**Status:** COMPLETE (2026-07-22)  
**Report:** `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_BATCH2_CERTIFICATION.md`  
**Assessment:** `docs/release/CSS_PRODUCTION_CERTIFICATION_READINESS_ASSESSMENT.md`  
**Outcome:** AR-011 **CLOSED** (disposition `NOT_CERTIFIED`); AR-013/014/040 remain **PARTIALLY CLOSED** (operational residuals); RB-001/RB-012 remain **PARTIALLY CLOSED**  
**Certification decision:** **CERTIFIABLE AFTER OPERATIONAL VALIDATION**  
**Next:** Batch 3 when authorized — Critical honesty residuals (do not invent CERTIFIED)

---

*End of CSS_RG2_FINAL_CLOSEOUT_PLAN.*
