# CSS OV-002 Attempt 2 — Formal Invalidation Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Attempt:** `OV-002 ATTEMPT 2`
**Run ID:** `OV002-20260723T062225Z`
**Evidence package:** `runtime_reports/operational_validation/ov002_attempt2_20260723T062224Z/`
**Freeze SHA:** `0ff97cba114c051b640eeabe2edacdecc5c02053`
**Branch:** `css-unified-consolidation-2026-07-13`
**Closure class:** Documentation-only incident closure (runtime not modified by this report)

---

## Formal disposition

# ENDURANCE INVALIDATED

OV-002 Attempt 2 is formally invalidated. It does **not** satisfy AR-014.
Phase 181 remains **`NOT_CERTIFIED`**.
No production, live-execution, broker, or certification claim is authorized.

The monitor’s provisional recommendation `ENDURANCE PASS WITH RESIDUALS` is **rejected as incomplete**.

---

## What the wall-clock evidence shows

| Observation | Evidenced value |
| --- | --- |
| Start (UTC) | `2026-07-23T06:22:25.166408+00:00` |
| Finish (UTC) | `2026-07-26T06:24:26.856207+00:00` |
| Elapsed wall-clock hours | **~72.03** (`72.03289`) |
| Monitoring snapshots | **863** |
| Timing mode | `wall_clock` · `synthetic_timing=false` |
| Commit drift in snapshots | None observed (`commit_drift` false across package) |
| Safety `safety_ok` in snapshots | True across sampled package (execution remained disabled) |

### Safety posture (preserved)

Across the Attempt 2 snapshot package and start assertions:

- Advisory-only / fail-closed posture remained intact.
- Execution remained disabled (`execution_allowed=false`).
- Live trading remained blocked (`can_live_execute=false`).
- Phase 181 was never claimed certified.

### Process / port continuity (HTTP-adjacent, not sufficient alone)

| Observation | Evidenced value |
| --- | --- |
| Main mobile-server PID at start | `26152` (`launcher.css_mobile_launcher` on port `8765`) |
| PID `26152` in resource samples | Present in **all 863** health snapshots |
| Port `8765` | Remained the listening mobile endpoint for that PID through the package |

HTTP health continuity and PID `26152` availability are acknowledged. They do **not** override declared invalidating conditions.

---

## Why Attempt 2 is invalidated

Declared Attempt 2 invalidating conditions (pre-run readiness) included, among others:

- Unexpected CSS restart
- Runtime unavailable without an evidenced and permitted recovery
- Continuous endurance integrity beyond HTTP reachability

### 1) Eight unexpected runtime exit / restart events

Supervisor alerts under `runtime/alerts/` during the Attempt 2 window record **eight** unexpected `CSS Runtime` exits, each followed by auto-restart activity. The durable supervisor state file records:

| Field | Value |
| --- | --- |
| `restart_count` | **8** |
| `max_restart_limit` | **3** |
| `failure_count` | `0` (not a trustworthy continuity ledger; see remediation plan) |
| `status` | `RUNNING` at review time |

Representative alert messages (timestamps UTC):

| Time (UTC) | Event |
| --- | --- |
| `2026-07-23T06:24:04Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:34:59Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:37:24Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:37:39Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:42:34Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:42:49Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:43:04Z` | Unexpected exit + restart attempt |
| `2026-07-23T06:43:19Z` | Unexpected exit + restart attempt |

These are **unexpected runtime exit/restart events**. They breach the declared invalidating condition for unexpected CSS restart / unpermitted recovery, regardless of later HTTP recovery.

Note: `max_restart_limit=3` was exceeded in cumulative `restart_count` while attempts were repeatedly labeled `1/3`, evidencing weak limit enforcement and non-durable failure accounting.

### 2) Two CRITICAL engine-heartbeat-loss alerts

| Alert ID | Timestamp (UTC) | Event |
| --- | --- | --- |
| `07b9ef69-badc-4fb5-8c18-966abec61848` | `2026-07-23T06:34:09.746812+00:00` | `ENGINE_HEARTBEAT_LOST` — “Engine heartbeat lost! Last seen 600 seconds ago.” |
| `ecab107f-d0ee-4e87-8d33-49a50fea4b1c` | `2026-07-23T06:53:25.650235+00:00` | `ENGINE_HEARTBEAT_LOST` — “Engine heartbeat lost! Last seen 600 seconds ago.” |

Critical heartbeat-loss events breach declared continuity / runtime-integrity expectations for OV-002 endurance.

### 3) Supervisor identity discontinuity

At Attempt 2 start authorization, supervisor `started_at` was recorded as `2026-07-23T06:18:14Z`.
At invalidation review, `runtime/supervisor/css_runtime_supervisor_state.json` shows `started_at` of `2026-07-23T06:43:24.702789+00:00` with the same `supervisor_id` and `restart_count=8`.

A later stable observation window does **not** retroactively replace the declared start or erase early discontinuity.

---

## Rejection of the monitor’s provisional PASS

`RUN_STATUS.json` ended as:

- `status`: `COMPLETE`
- `elapsed_hours_wall_clock`: `72.03289`
- `recommendation_pending`: **`ENDURANCE PASS WITH RESIDUALS`**

That provisional result is **rejected** because the monitor path, as executed, did **not** reconcile:

1. Supervisor alert stream (WARNING unexpected exits; CRITICAL heartbeat loss)
2. Restart history (`restart_count=8` vs `max_restart_limit=3`)
3. Heartbeat continuity (engine heartbeat-loss alerts)
4. Full process-tree identity beyond mobile HTTP PID / port checks

HTTP availability, snapshot count, and elapsed wall-clock hours are insufficient alone for OV-002 certification credit.

---

## Certification effect

| Item | Effect |
| --- | --- |
| OV-002 Attempt 2 | **`ENDURANCE INVALIDATED`** |
| AR-014 | Remains open / partially closed — **no 72h credit** |
| RB-012 | Remains partially closed |
| Phase 181 | Remains **`NOT_CERTIFIED`** |
| Elapsed time carry-forward | **Forbidden** |
| Attempt 3 | May begin from **zero** only after owner approval and remediation |

---

## Explicit non-claims

- No production readiness claim
- No live-execution authorization
- No broker certification
- No Phase 181 certification
- No assertion that CSS “failed safely into a PASS”
- No assertion that later stability cures early invalidating events

---

## Evidence custody

Attempt 2 evidence remains authoritative custody under:

`runtime_reports/operational_validation/ov002_attempt2_20260723T062224Z/`

This invalidation report does not modify that package. Existing untracked operational files remain protected.

Companion remediation: `docs/release/CSS_OV002_SUPERVISOR_AND_MONITOR_REMEDIATION_PLAN.md`

---

*End of CSS_OV002_ATTEMPT2_INVALIDATION_REPORT.md*
