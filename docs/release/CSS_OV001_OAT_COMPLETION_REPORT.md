# OV-001 OAT Completion Report

**Programme:** Release Gate 3 — Operational Validation OV-001  
**Date:** 2026-07-22  
**RC-001 baseline:** `6513e6a1e45ffc42aff192e1c784171ad6fc182b`  
**Evidence HEAD (pre-RC-002):** `b7c3d32678a42d90338d1da7f6ebe34fb200f28a`  
**Evidence package:** `runtime_reports/operational_validation/ov001_20260722T041013Z/`  
**Machine:** hostname `Finance` · platform `nt` · Python `3.12.9`

---

## Result

| Metric | Value |
| --- | --- |
| **OAT** | **100%** |
| **Status** | `EVIDENCE_COMPLETE` |
| **Blockers** | none |
| **Waived failures** | none |
| **Fabricated** | **false** |
| **Manual evidence edits** | **none** |

---

## Commands executed

```text
python -m pytest tests/test_ov001_controlled_shutdown.py -q
python scripts/css_ov001_operational_validation.py --shutdown-cycles 2
```

Timestamps (UTC): package assembled `2026-07-22T04:10:13Z` (directory stamp) / summary `2026-07-22T04:10:…` in `OV001_SUMMARY.json`.

---

## OAT scenarios (production profile)

| Requirement | Status | Evidence ID |
| --- | --- | --- |
| STARTUP | EVIDENCE_VERIFIED | BATCH2-OAT-STARTUP |
| SHUTDOWN | EVIDENCE_VERIFIED | OV001-OAT-SHUTDOWN |
| RECOVERY | EVIDENCE_VERIFIED | BATCH2-OAT-RECOVERY |
| RUNTIME_HEALTH | EVIDENCE_VERIFIED | BATCH2-OAT-RUNTIME_HEALTH |
| CONFIGURATION_VALIDATION | EVIDENCE_VERIFIED | BATCH2-OAT-CONFIGURATION_VALIDATION |
| DEPENDENCY_VALIDATION | EVIDENCE_VERIFIED | BATCH2-OAT-DEPENDENCY_VALIDATION |
| REPORT_GENERATION | EVIDENCE_VERIFIED | BATCH2-OAT-REPORT_GENERATION |
| DASHBOARD_RENDERING | EVIDENCE_VERIFIED | BATCH2-OAT-DASHBOARD_RENDERING |
| CERTIFICATION_EVIDENCE | EVIDENCE_VERIFIED | OV001-OAT-CERTIFICATION_EVIDENCE |

Artifact: `OPERATIONAL_ACCEPTANCE_COMPLETE.json`

---

## Shutdown evidence

| Field | Value |
| --- | --- |
| Observation | `shutdown/SHUTDOWN_OBSERVATION.json` |
| Status | **PASS** |
| Supervisor stop requested | true |
| Supervisor stop acknowledged | true (final `STOPPED`) |
| Process alive after stop | false |
| Port released within timeout | true |
| Repeated cycles | **2/2 PASS** (`shutdown_cycles/SHUTDOWN_CYCLE_SUMMARY.json`) |
| False-complete while alive | forbidden / not observed |

---

## Custody

- `OV001_SUMMARY.json` + `OV001_SUMMARY.custody.md`
- SHA-bound via evidence machine identity fields (`git_sha`, branch, worktree_state)

---

## Warnings / residual risks

1. Desktop `:8765` runtime was not the probe under stop — OAT SHUTDOWN used a supervised ephemeral probe (documented in RCA).  
2. Broker security contamination flags remain (see broker report) — do not confuse with OAT completeness.  
3. 72-hour endurance **not** started.

---

*End of CSS_OV001_OAT_COMPLETION_REPORT.md*
