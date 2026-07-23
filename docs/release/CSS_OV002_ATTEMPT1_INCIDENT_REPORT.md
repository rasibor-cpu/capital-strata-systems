# CSS OV-002 Attempt 1 — Incident Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Attempt:** **1**
**Formal disposition:** `ENDURANCE INVALIDATED — CONTINUITY NOT ESTABLISHED`
**Close-out date (local):** 2026-07-23
**Branch:** `css-unified-consolidation-2026-07-13`
**Close-out baseline HEAD (pre-commit):** `0457c24e17698a8113a9a6ffe26918f0818a9404`

---

## Disposition

# ENDURANCE INVALIDATED — CONTINUITY NOT ESTABLISHED

Attempt 1 **cannot** satisfy AR-014.
Elapsed time **must not** be resumed or carried forward.
Phase 181 remains **`NOT_CERTIFIED`**.

This is **not** described as an application endurance failure caused by CSS unless proven. Repository evidence shows the monitor invalidated the run for **commit drift**, then stopped. Exact operator/process stop causality beyond that is not fully established.

---

## Baselines and start

| Field | Value |
| --- | --- |
| Freeze / Attempt 1 baseline | `34503b155d6e1274863d0b137e23b145d2901e1e` (OV-002 harness) |
| RC-001 (immutable) | `6513e6a1e45ffc42aff192e1c784171ad6fc182b` |
| RC-002 candidate | `fbcc31f9a877f8fbc2b67291b4b7ee8ba2fe4ff5` |
| Run ID | `OV002-20260722T043023Z` |
| Start UTC (evidenced) | `2026-07-22T04:30:23.215600+00:00` |
| Start local (evidenced) | `2026-07-22T00:30:23.894242-04:00` |
| Evidence directory | `runtime_reports/operational_validation/ov002_72h_20260722T043023Z/` (local custody; not git-committed) |

---

## Last evidenced runtime / continuity

| Field | Value |
| --- | --- |
| Last snapshot | `snapshots/health_20260723T054132Z.json` |
| Last observed UTC | `2026-07-23T05:41:32.034677+00:00` |
| Elapsed wall-clock (monitor) | **~25.185 hours** (`elapsed_hours_wall_clock`) |
| Snapshot count | **304** |
| Timing mode | `wall_clock` · `synthetic_timing=false` |
| Continuous 72h proof | **Insufficient / not established** |

### Invalidation record (monitor)

`INVALIDATION.json`:

- `reasons`: [`active_commit_changed`]
- `observed_at_utc`: `2026-07-23T05:41:32.037050+00:00`
- `elapsed_hours_wall_clock`: `25.185333`

`RUN_STATUS.json` final: `INVALIDATED` with the same reason.

Interpretation: the endurance freeze SHA was `34503b15…`. Repository HEAD later moved to `0457c24e…` (Commercial Readiness CEP-001). The monitor correctly fail-closed on commit drift. That event **invalidates** continuous 72-hour certification eligibility for Attempt 1.

---

## Last known safety posture (final snapshot)

From `health_20260723T054132Z.json`:

| Control | Observed |
| --- | --- |
| runtime_mode | `DISABLED` |
| advisory_only | true |
| fail_closed | true |
| execution_enabled | false |
| execution_allowed | false |
| can_live_execute | false |
| live_authority_state | `BLOCKED` |
| Coinbase account auth claimed | false |
| OANDA LIVE certified claimed | false |
| Coinbase / OANDA execution_blocked | true |
| Health HTTP | 200 (`css_mobile_launcher` healthy at snapshot) |

---

## Incident classification

| Item | Assessment |
| --- | --- |
| Host reboot | **Not observed / not reported** in Attempt 1 evidence |
| Fatal application traceback | **Not evidenced** in Attempt 1 close-out review |
| Regular cycles / health snapshots | **Evidenced** (304 wall-clock snapshots over ~25.2h) |
| Live execution | **Remained blocked** in evidenced snapshots |
| Coinbase | Remained fail-closed / non-certified (OV-001 residuals carried) |
| Process / monitor stop | **Confirmed** — `css_ov002_72h_endurance.py` not running at close-out; monitor exited after INVALIDATED |
| Exact stop cause (beyond invalidation reason) | **Unknown** (no separate crash dump attributed) |
| CSS launcher at close-out | `launch_css.bat` still observed running (PID noted at review) — **not** treated as continuous 72h proof |

---

## Certification effect

| Item | Effect |
| --- | --- |
| AR-014 | Remains **PARTIALLY CLOSED** — Attempt 1 grants **no** 72h credit |
| RB-012 | Remains **PARTIALLY CLOSED** |
| Phase 181 | Remains **`NOT_CERTIFIED`** |
| Attempt 1 resume | **Forbidden** — begin Attempt 2 from **zero** elapsed time |

---

## Safety assessment

- Live trading remained **blocked** in evidenced snapshots.
- No live order execution evidenced.
- Fail-closed / advisory posture remained active in evidenced snapshots.
- Attempt 1 is useful for **stability and safety observations only**, not for endurance certification.

---

## Required disposition

1. Preserve local evidence directory (do not delete).
2. Do **not** resume elapsed-time counting.
3. Commit governed documentation of Attempt 1 invalidation.
4. Begin a **new** 72-hour run (Attempt 2) from zero on a fresh freeze SHA.

---

## Untracked local artifact classification (Part E)

| Path | Classification | Commit? |
| --- | --- | --- |
| `CSS_Overnight_Runtime_Review.txt` | Temporary / ad-hoc review note | **No** |
| `broker_environment_bootstrap_verification.txt` | Temporary local diagnostic output | **No** |
| `broker_environment_diagnostic.txt` | Temporary local diagnostic output | **No** |
| `pytest_*.txt` (8 files) | Temporary local pytest capture | **No** |
| `tools/diagnostics/broker_environment_diagnostic.ps1` | Reusable governed diagnostic (read-only; no secrets written by design) | **Deferred** — not required for Attempt 1 close-out; leave untracked for separate review |
| `runtime_reports/operational_validation/ov002_72h_*` | Certification evidence custody (local) | **No** (gitignored; preserve on disk) |

---

*End of CSS_OV002_ATTEMPT1_INCIDENT_REPORT.md*
