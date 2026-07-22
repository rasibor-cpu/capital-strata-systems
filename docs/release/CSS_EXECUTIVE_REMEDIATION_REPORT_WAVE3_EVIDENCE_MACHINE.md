# Executive Remediation Report — Wave 3 (Evidence Machine)

**Programme:** Release Gate 2 — Audit Remediation  
**Batch:** Wave 3 — Evidence Machine  
**Date:** 2026-07-22  
**Midpoint:** `docs/release/RG2_MIDPOINT_REVIEW.md`  
**RCA:** `docs/release/CSS_WAVE3_ROOT_CAUSE_ANALYSIS.md`  
**Baseline HEAD (programme):** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`  
**Current Release Gate status:** **ACTIVE** — Wave 3 Evidence Machine **COMPLETE**  
**Phase 181:** remains **`NOT_CERTIFIED`** (AR-011 not in Wave 3)

## Verdict

Wave 3 operationalizes fail-closed evidence authority and SHA-bound Class B capture without inventing a production certificate. Fixture URIs are rejected in production profile; compile/ops/OAT/endurance-sample/DR-drill/broker-pack/performance packs are archived; ops host activation is wired into the headless API.

| Remediation ID | Recommendation | Release Blocker impact |
| --- | --- | --- |
| AR-012 | **CLOSE** | RB-001 → **PARTIALLY CLOSED** |
| AR-028 | **CLOSE** | RB-015 → **CLOSED** |
| AR-040 | **PARTIALLY CLOSE** | (supports RB-001 residual / AR-011) |
| AR-013 | **PARTIALLY CLOSE** | RB-001 → **PARTIALLY CLOSED** |
| AR-029 | **Already CLOSED** | No change (Wave 2) |
| AR-014 | **PARTIALLY CLOSE** | RB-012 → **PARTIALLY CLOSED** |
| AR-015 | **CLOSE** | RB-012 → **PARTIALLY CLOSED** (with AR-014 residual) |
| AR-044 | **CLOSE** | RB-012 → **PARTIALLY CLOSED** |
| AR-045 | **CLOSE** | RB-016 → **CLOSED** |

**Do not start Wave 4** until this report is executively accepted.  
**Do not claim Phase 181 CERTIFIED** — AR-011 remains OPEN.

---

## Root cause analysis (consolidated)

Full analysis: `docs/release/CSS_WAVE3_ROOT_CAUSE_ANALYSIS.md`

**Shared theme:** Evaluators existed; production-grade evidence authority and Class B capture did not.

| Cluster | ARs | Coherent fix |
| --- | --- | --- |
| Authority / fixtures | 045, 044 | Production profile rejects synthetic refs/sources; perf marks synthetic ineligible |
| Capture / custody | 012, 013 | Evidence machine + custody manifests |
| Ops observability | 028 | Startup activation + `/ops/health` |
| Continuity / endurance | 014, 015 | Wall-clock heartbeats + measured local drill |
| Broker freshness | 040 | Current-SHA pack structure; fail-closed without live probe |

---

## Per-AR executive entries

### AR-012 — Current-SHA compile and bounded regression evidence

| Field | Content |
| --- | --- |
| **Objective** | Archive SHA-bound compile (+ optional bounded pytest) with custody headers and exit codes |
| **Root Cause** | Phase 181 stubs lacked command/exit/SHA custody |
| **Files Changed** | `backend/certification/evidence_machine.py`; `scripts/css_wave3_evidence_machine.py` |
| **Tests** | `tests/test_wave3_evidence_machine.py` (assemble package) |
| **Evidence** | `runtime_reports/wave3_evidence_machine_*/COMPILE_EVIDENCE.json` + `.custody.md` |
| **Risks** | Full Gate-2 suite still operator-scheduled via `--with-regression`; dirty worktree marked INVENTORIED |
| **Dependencies** | AR-002, AR-005 (CLOSED) |
| **Recommendation** | **CLOSE** |

### AR-028 — Host-activate OperationsService (residual)

| Field | Content |
| --- | --- |
| **Objective** | Wire activation into canonical headless host so OAT can observe ops health |
| **Root Cause** | Wave 2 helper existed but was test-only |
| **Files Changed** | `backend/app/main.py` (startup + `GET /ops/health`); `backend/operations/host_activation.py` (consumed) |
| **Tests** | Wave3 ops activation; `tests/test_backend_app_main_recovery.py`; ops control centre |
| **Evidence** | `OPS_ACTIVATION_OBSERVATION.json` in Wave 3 package |
| **Risks** | Soft-activate on startup — hard fail only when ops route cannot activate |
| **Dependencies** | AR-009 (CLOSED) |
| **Recommendation** | **CLOSE** |

### AR-040 — Fresh Coinbase/OANDA read-only evidence

| Field | Content |
| --- | --- |
| **Objective** | Current-SHA read-only evidence pack without execution authority |
| **Root Cause** | Historical broker packages stale; no fresh Gate-2 pack |
| **Files Changed** | `backend/certification/evidence_machine.py` (`capture_broker_read_only_evidence_pack`) |
| **Tests** | Wave3 assemble asserts pack present / incomplete without live probe |
| **Evidence** | `BROKER_READ_ONLY_EVIDENCE.json` — `NOT_TESTED` unless `CSS_WAVE3_BROKER_LIVE=1` |
| **Risks** | Live PASS still requires authorized operator probe (not claimed here) |
| **Dependencies** | AR-026, AR-032, AR-033 |
| **Recommendation** | **PARTIALLY CLOSE** |

### AR-013 — Operational Acceptance Testing

| Field | Content |
| --- | --- |
| **Objective** | Archive OAT observations with remediation IDs; no fabricated full PASS |
| **Root Cause** | Evaluator scored supplied evidence; no current-SHA observation pack |
| **Files Changed** | `evidence_machine.capture_oat_observation_pack`; profile passthrough in `operational_acceptance.py` |
| **Tests** | Wave3 OAT incomplete under production profile |
| **Evidence** | `OPERATIONAL_ACCEPTANCE_OBSERVATION.json` — EVIDENCE_INCOMPLETE with blockers |
| **Risks** | Full authorized OAT PASS (startup/shutdown/recovery suite) still residual |
| **Dependencies** | AR-009, AR-012, AR-028 |
| **Recommendation** | **PARTIALLY CLOSE** |

### AR-029 — Metrics persistence / export

| Field | Content |
| --- | --- |
| **Objective** | (Already CLOSED in Wave 2) |
| **Root Cause** | N/A — no rework |
| **Files Changed** | None in Wave 3 |
| **Tests** | None required |
| **Evidence** | Wave 2 host observability tick |
| **Risks** | External export still future |
| **Dependencies** | — |
| **Recommendation** | **Already CLOSED** |

### AR-014 — Wall-clock endurance evidence

| Field | Content |
| --- | --- |
| **Objective** | Ban +1s injection as production timing; capture wall-clock sample; refuse 72h eligibility until duration met |
| **Root Cause** | Simulated elapsed time treated as endurance proof |
| **Files Changed** | `backend/validation/endurance_evidence.py`; evidence machine sample capture |
| **Tests** | Wave3 wall-clock delta test; phase163 endurance suite |
| **Evidence** | `ENDURANCE_WALL_CLOCK_SAMPLE.json` — `production_evidence_eligible=false` |
| **Risks** | Authorized multi-hour/72h run not executed in this batch |
| **Dependencies** | AR-012, AR-029 |
| **Recommendation** | **PARTIALLY CLOSE** |

### AR-015 — Backup / restore drill

| Field | Content |
| --- | --- |
| **Objective** | Measured local backup/restore with RTO/RPO timings and hash verification |
| **Root Cause** | DR evaluators scored assertions without drills |
| **Files Changed** | `backend/certification/backup_restore_drill.py`; DR evaluator drill observation hook |
| **Tests** | Wave3 backup restore drill |
| **Evidence** | `dr_drill/BACKUP_RESTORE_DRILL.json` with measured seconds |
| **Risks** | Local artifact drill ≠ production cluster failover (explicitly not claimed) |
| **Dependencies** | AR-002; AR-016 for deployment-profile targets |
| **Recommendation** | **CLOSE** for Gate 2 measured drill capability |

### AR-044 — Replace simulated performance claims

| Field | Content |
| --- | --- |
| **Objective** | Mark synthetic telemetry ineligible for production evidence |
| **Root Cause** | Summarizer could be read as observed performance without sample honesty flags |
| **Files Changed** | `backend/monitoring/runtime_performance_monitor.py` |
| **Tests** | Wave3 performance synthetic rejection; runtime performance monitor suite |
| **Evidence** | `PERFORMANCE_SAMPLE.json` |
| **Risks** | Callers must pass `synthetic=True` when feeding non-observed data |
| **Dependencies** | AR-014, AR-029 |
| **Recommendation** | **CLOSE** |

### AR-045 — Evidence signatures, expiry, provenance

| Field | Content |
| --- | --- |
| **Objective** | Production profile rejects synthetic `evidence://` fixtures and fixture sources; support expiry |
| **Root Cause** | Phase 181 tests could mint CERTIFIED from Class D URIs |
| **Files Changed** | `backend/certification/evidence_authority.py`; `production_readiness_models.py`; engine + dimension evaluators |
| **Tests** | Wave3 AR-045; `test_production_profile_rejects_fixture_uris`; fixture_lab preserves lab suites |
| **Evidence** | Authority diagnostics in certification engine output |
| **Risks** | Operators must set `CSS_CERTIFICATION_PROFILE=production` for production evaluation hosts |
| **Dependencies** | AR-012 (capture paths) |
| **Recommendation** | **CLOSE** |

---

## Release blockers affected

| Blocker | Pre–Wave 3 | Post–Wave 3 | Rationale |
| --- | --- | --- | --- |
| RB-001 | OPEN | **PARTIALLY CLOSED** | Class B machine lands; Phase 181 still NOT CERTIFIED (AR-011) |
| RB-012 | OPEN | **PARTIALLY CLOSED** | Wall-clock + measured drill; 72h endurance residual |
| RB-015 | PARTIALLY CLOSED | **CLOSED** | Ops activation wired + observable |
| RB-016 | OPEN | **CLOSED** | Production profile rejects fixture URIs |

Unaffected Critical open: RB-009, RB-010, RB-011.

---

## Validation evidence

| Suite / run | Result |
| --- | --- |
| Wave 3 + Phase 181 + endurance + perf + cert + main + ops + Wave2 | **50 passed**, exit 0 (`artifacts/_wave3_validate.txt`) |
| Evidence machine package | `runtime_reports/wave3_evidence_machine_20260722T023605Z/` |
| Phase 181 certification claim | **NOT_CERTIFIED** (explicit non-claim) |

---

## Programme impact (evidence-bound)

| Metric | Midpoint (post Wave 2) | Post Wave 3 |
| --- | ---: | ---: |
| Fully CLOSED ARs | 21 | **26** (+012, 028, 015, 044, 045) |
| PARTIALLY CLOSED ARs | 3 | **5** (025, 033, +013, 014, 040; 028 closed) |
| Critical blockers fully open | 5 | **3** (RB-009, 010, 011) + RB-001/012 partial |
| Production readiness | NO-GO | **NO-GO** |
| Live trading | BLOCKED | **BLOCKED** |

---

## Next critical path

1. Executive acceptance of this Wave 3 report  
2. **Do not start Wave 4**  
3. Residuals: AR-013 full OAT PASS; AR-014 72h wall-clock; AR-040 live read-only probe; then AR-011 recert when authorized  
4. Parallel High residual outside Wave 3: AR-034  

---

## Non-claims

- No Production Certification  
- No commercial readiness  
- No live trading enablement  
- No Wave 4 product work  
- No fabricated 72h endurance or live broker PASS  
