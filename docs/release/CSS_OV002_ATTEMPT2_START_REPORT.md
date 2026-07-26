# CSS OV-002 Attempt 2 — First-Start Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Attempt:** `OV-002 ATTEMPT 2`
**Recorded (UTC):** 2026-07-23T06:23:00Z
**Active commit (freeze):** `0ff97cba114c051b640eeabe2edacdecc5c02053`
**Branch:** `css-unified-consolidation-2026-07-13`

---

## Readiness result

# READY FOR ENDURANCE

Source: `docs/release/CSS_OV002_ATTEMPT2_PRE_RUN_READINESS.md`

---

## Monitor started

**Yes**

| Field | Value |
| --- | --- |
| Run ID | `OV002-20260723T062225Z` |
| Evidence directory | `runtime_reports/operational_validation/ov002_attempt2_20260723T062224Z/` |
| UTC start | `2026-07-23T06:22:25.166408+00:00` |
| Local start | `2026-07-23T02:22:25.601914-04:00` |
| Target hours | 72.0 wall-clock |
| Snapshot interval | 300 seconds |
| Timing mode | `wall_clock` · `synthetic_timing=false` |
| Elapsed carry-forward | **0** (Attempt 1 not reused) |
| Monitor PIDs | `22280` (venv wrapper), `23292` (worker) |
| RUN_STATUS | `RUNNING` |
| T+0 snapshot | `snapshots/health_20260723T062226Z.json` |

---

## Runtime processes (at start)

| PID | Role |
| --- | --- |
| 27400 | `launch_css.bat` |
| 24776 / 15744 | `css_runtime_launcher` |
| 24144 / 19312 | `css_live_dashboard` |
| 22168 / 26152 | `css_mobile_launcher` (`:8765`) |
| 22280 / 23292 | OV-002 endurance monitor |

---

## Health / broker / safety

| Check | Result |
| --- | --- |
| Health | HTTP 200 · `healthy` · `css_mobile_launcher` |
| Runtime mode | `DISABLED` · advisory · fail-closed |
| Execution allowed | **false** |
| Can live execute | **false** |
| Live authority | `BLOCKED` (`Credentials Invalid`) |
| Coinbase | fail-closed / auth not claimed |
| OANDA | fail-closed / not LIVE-certified |
| Phase 181 | `NOT_CERTIFIED` |
| Safety assertions | `ok=true` |
| Initial display/session cycle | 635 |
| Supervisor | RUNNING with heartbeat |

---

## Initial warnings

- Untracked local diagnostic/pytest text files remain in the worktree (not staged; freeze SHA unchanged).
- Authority payload shows `operator_requested_live=true` while execution remains blocked.
- Selected broker may display mode `live` while execution authority remains BLOCKED (same fail-closed posture as Attempt 1).
- Do **not** commit or push on this Desktop while Attempt 2 is RUNNING (commit drift invalidates).

---

## Recommendation

# CONTINUE

---

*Local operational evidence only — do not commit while the endurance run is active.*
