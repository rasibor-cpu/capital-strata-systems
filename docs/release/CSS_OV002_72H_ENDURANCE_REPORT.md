# CSS OV-002 Attempt 1 — 72-Hour Endurance Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Attempt:** **1**
**Final result:** `ENDURANCE INVALIDATED`
**Reason:** `CONTINUITY NOT ESTABLISHED / PROCESS TERMINATION CAUSE UNKNOWN`
**Formal companion:** `docs/release/CSS_OV002_ATTEMPT1_INCIDENT_REPORT.md`

---

## Final result

# ENDURANCE INVALIDATED

**Reason:** `CONTINUITY NOT ESTABLISHED / PROCESS TERMINATION CAUSE UNKNOWN`

- The run **cannot** be resumed.
- Elapsed time **cannot** be carried forward.
- **No certification credit** is granted toward AR-014 / Phase 181.
- Evidence remains useful for **stability and safety observations only**.

Monitor-recorded invalidation reason (primary, evidenced): **`active_commit_changed`** at ~**25.185** wall-clock hours (freeze `34503b15…` vs later HEAD including `0457c24e…`). Exact broader stop causality beyond monitor exit after invalidation is **unknown**.

Phase 181 remains **`NOT_CERTIFIED`**.

---

## Attempt identity

| Field | Value |
| --- | --- |
| Run ID | `OV002-20260722T043023Z` |
| Branch | `css-unified-consolidation-2026-07-13` |
| Freeze SHA | `34503b155d6e1274863d0b137e23b145d2901e1e` |
| RC-001 (immutable) | `6513e6a1e45ffc42aff192e1c784171ad6fc182b` |
| Start UTC | `2026-07-22T04:30:23.215600+00:00` |
| Last evidenced snapshot UTC | `2026-07-23T05:41:32.034677+00:00` |
| Evidenced elapsed | ~**25.185 h** (of 72.0 target) |
| Snapshots | **304** |
| Evidence directory | `runtime_reports/operational_validation/ov002_72h_20260722T043023Z/` |
| Timing | `wall_clock` · not simulated |

---

## What was observed (non-certifying)

| Observation | Status |
| --- | --- |
| Regular health snapshots | Yes (through last snapshot) |
| Fatal traceback | Not evidenced |
| Live execution | Blocked in evidenced snapshots |
| Coinbase | Fail-closed / account auth not claimed |
| OANDA | Practice/read-only identity; not LIVE-certified |
| Host reboot | Not observed/reported |
| Continuous 72h | **Not proven** |

---

## Safety posture (last evidenced snapshot)

| Control | Value |
| --- | --- |
| runtime_mode | DISABLED |
| advisory_only | true |
| fail_closed | true |
| execution_allowed | false |
| can_live_execute | false |
| live trading | BLOCKED |

---

## Next action

**OV-002 Attempt 2** — fresh 72-hour wall-clock run from **zero** elapsed time on a new freeze SHA after Attempt 1 close-out commit.
See Attempt 2 readiness record (must state `READY FOR ENDURANCE` before start).

---

*End of CSS_OV002_72H_ENDURANCE_REPORT.md (Attempt 1 final).*
