# Wave 3 — Consolidated Root Cause Analysis

**Programme:** Release Gate 2  
**Batch:** Wave 3 — Evidence Machine  
**Scope:** AR-012, AR-028 (residual), AR-040, AR-013, AR-029 (already CLOSED — no rework), AR-014, AR-015, AR-044, AR-045  
**Date:** 2026-07-21  
**Midpoint:** `docs/release/RG2_MIDPOINT_REVIEW.md`

## Shared theme

Certification and readiness **evaluators exist**, but Production Certification still treats missing, synthetic, clock-injected, or uncustodied artefacts as if an evidence machine were complete. Shared corrective principle: **fail-closed evidence authority** — reject Class D fixtures in production profile, capture SHA-bound Class B observations, measure drills honestly, and refuse to claim CERTIFIED when residual dimensions are incomplete.

## Shared architectural causes

| Cluster | ARs | Cause |
| --- | --- | --- |
| Duplicated certification logic | 012, 013, 045 | Multiple evaluators share `evaluate_required_evidence` but apply no profile/provenance gate |
| Evidence gaps | 012, 013, 014, 015, 040 | Phase 181 stubs lack SHA/command/exit codes; no current-SHA packs |
| Traceability gaps | 012, 045 | Custody standard documented; not operationalized in capture harness |
| Documentation deficiencies | 013, 040, 044 | Reports say EVIDENCE INCOMPLETE / UNKNOWN without remediation mapping to ARs |
| Certification weaknesses | 014, 044, 045, RB-016 | Fixture URIs + clock-injected duration can mint controlled-deployment CERTIFIED in tests |

## Duplicated certification logic

1. Platform / OAT / endurance / DR / deployment all funnel through one acceptance helper without production-profile rules.
2. Legacy `backend/validation/operational_acceptance.py` vs Phase 181 `backend/certification/operational_acceptance.py` — Wave 3 does not merge platforms; it hardens the Phase 181 evidence gate.
3. Endurance validation engine vs Phase 181 endurance evaluator — Wave 3 fixes wall-clock at the evidence source and bans synthetic claims in production profile.

## Evidence / traceability / documentation gaps

1. `runtime_reports/phase181_certification/*` stubs without exit codes.
2. No Gate-2 capture script for compile/pytest with custody headers.
3. OAT evaluator does not perform ops; no archived observation pack mapped to AR-013.
4. DR evaluator hard-codes `backup_performed=False` / `restore_performed=False` with no measured drill path.
5. Broker readiness tooling exists; fresh Class B pack for current SHA does not.

## Smallest coherent remediation set

1. **AR-045:** Production-profile evidence authority — reject `evidence://`, FIXTURE/SYNTHETIC sources, expired evidence.
2. **AR-012:** Evidence machine capture for `compileall` + bounded regression with custody manifests.
3. **AR-028 residual:** Activate OperationsService on headless app startup; expose `/ops/health`.
4. **AR-013:** OAT observation pack from real local ops/health/config checks; archive FAIL/INCOMPLETE with AR remediations (no fabricated PASS).
5. **AR-014:** Wall-clock heartbeat deltas; short sample pack; `production_evidence_eligible=False` until duration target met.
6. **AR-015:** Measured local backup/restore drill with RTO/RPO timings.
7. **AR-040:** Fresh broker read-only evidence pack structure; fail-closed NOT_TESTED/FAIL without live auth (no execution).
8. **AR-044:** Performance monitor marks synthetic telemetry ineligible for production evidence.
9. **AR-029:** Already CLOSED — reference only.

## Expected closure posture

| AR | Expected recommendation |
| --- | --- |
| 045, 012, 015, 044 | CLOSE (authority + capture + measured drill + sample honesty) |
| 028 | CLOSE if startup wiring lands |
| 013, 014, 040 | PARTIALLY CLOSE — harness/packs honest; full OAT PASS / 72h / live broker PASS remain residual |
| 029 | Already CLOSED — no change |

## Safety constraints

- No live trading enablement.
- No fabricated CERTIFIED Phase 181 claim (AR-011 remains OPEN).
- No Wave 4 product work.
- No new platform functionality beyond evidence custody / fail-closed gates.
