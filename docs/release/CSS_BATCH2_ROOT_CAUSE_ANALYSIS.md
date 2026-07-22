# Batch 2 Root Cause Analysis — Production Certification Evidence

**Programme:** Release Gate 2 — Final Close-Out  
**Batch:** 2 — Production Certification Evidence  
**Date:** 2026-07-22  
**ARs:** AR-013, AR-014, AR-040, AR-011  
**Blockers:** RB-001, RB-012  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`  

## Shared corrective principle

> **Never create evidence that did not occur.**

Phase 181 certification fails closed when independently verified observations are missing. Batch 2 root cause is not a missing evaluator — it is **incomplete operational proof** relative to the Phase 181 evidence model.

## Root causes by AR

| AR | Root cause | Engineering vs operational |
| --- | --- | --- |
| **AR-013** | OAT evaluator scores supplied evidence; Wave 3 captured only `RUNTIME_HEALTH`. Full OAT PASS requires startup/shutdown/recovery/config/deps/reports/dashboard/certification observations — several are localizable; **SHUTDOWN** requires an authorized controlled stop. | Mixed — Batch 2 extends local observations; SHUTDOWN remains operational |
| **AR-014** | Wall-clock heartbeats exist, but **72h uninterrupted runtime** has not been authorized or executed. Short samples correctly set `production_evidence_eligible=false`. | Operational (duration run) |
| **AR-040** | Broker pack structure exists; live Coinbase/OANDA read-only probes default to `NOT_TESTED` without `CSS_WAVE3_BROKER_LIVE=1` and authorization. | Operational (authorized live-read) |
| **AR-011** | Phase 181 engine correctly returns `NOT_CERTIFIED` when frameworks lack verified refs. Recert cannot invent PASS dimensions. | Engineering = package + disposition; CERTIFIED requires ops residuals |

## Blocker mapping

| Blocker | Cause | Batch 2 effect |
| --- | --- | --- |
| **RB-001** | Production certification remains `NOT CERTIFIED` | Remains **PARTIALLY CLOSED** until Phase 181 can be earned; AR-011 dispositioned with explicit residuals |
| **RB-012** | Endurance proof incomplete (72h); DR local drill already CLOSED under AR-015 | Remains **PARTIALLY CLOSED** pending AR-014 operational endurance |

## Corrective approach (Batch 2)

1. Inventory existing Class B evidence (Wave 3 pack + Batch 1 CI/CD honesty).  
2. Capture only observations that can be performed locally without fabrication.  
3. Evaluate Phase 181 under **production** profile against real filesystem references.  
4. Publish Certification Readiness Assessment separating engineering vs operational gaps.  
5. Update `CERTIFICATION_SUMMARY.md` with engine status + executive decision — **no CERTIFIED claim**.

## Non-goals

- Fabricating 72h endurance results  
- Fabricating live broker PASS  
- Weakening fail-closed / advisory-only posture  
- Starting Batch 3 or Release Gate 3  
