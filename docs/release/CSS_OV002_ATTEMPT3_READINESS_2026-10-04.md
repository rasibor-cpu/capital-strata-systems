# OV-002 Attempt 3: Readiness Record (2026-10-04)

**Approval:** the owner approved a fresh Attempt 3 on 2026-10-04, conditional on: auth fixes integrated; endurance tooling on the release candidate; supervisor restart limit corrected; heartbeat instrumentation improved; the release candidate passing its available validation suite. All five conditions are met on the PR #101 head that carries this file (see the validation section).

**Label:** `OV-002 ATTEMPT 3`. Zero carry-forward: no time from Attempt 1 or 2 is credited (`elapsed_carry_forward_hours: 0` is written to `RUN_META.json`).

## What Attempt 3 measures

| Item | Value |
|---|---|
| Supervised service | `dashboard.web.web_app:app` on `127.0.0.1:8765`, supervised by `dashboard.runtime.runtime_supervisor` (the release line's own supervisor) |
| Not covered | The interactive paper-engine loop (`scripts/css_live_dashboard.py`): it cannot run unattended (Phase 181 ENG-07) |
| Governed target | **72 h** wall-clock, measured monotonically |
| Interim checkpoint | 23 h, recorded as a non-certifying `INTERIM_CHECKPOINT` plus `MANIFEST_INTERIM.json` |
| Snapshot cadence | 60 s |
| Heartbeat | Runtime publishes every 5 s; STALE > 60 s, LOST > 180 s (governed values, unchanged); startup grace 120 s |
| Restart limit | 3 for the run, but **any** unexpected restart invalidates the attempt |
| Result vocabulary | `RUNNING` → `INVALIDATED` \| `STOPPED_BEFORE_TARGET` \| `COMPLETE_PENDING_GOVERNANCE_REVIEW`. Never "PASS" or "CERTIFIED". |

## Automatic invalidation (terminal; credits 0 h)

`RELEASE_SHA_CHANGED`, `RELEASE_TREE_MODIFIED`, `CONFIGURATION_SUBSTITUTED`, `UNEXPECTED_ENGINE_RESTART`, `SUPERVISOR_RUN_FAILED:*` (including restart limit exceeded), `SUPERVISOR_PROCESS_EXITED`, `UNEXPLAINED_SUPERVISOR_STOP`, `CRITICAL_HEARTBEAT_LOSS:{ENGINE_TERMINATED|PROCESS_HUNG|EVENT_LOOP_BLOCKED|NO_HEARTBEAT_SOURCE}`, `EVIDENCE_RECORDER_GAP` (monitor stall, or a monitor restart with a gap > 180 s), `CLOCK_DISCONTINUITY` (> 300 s), `UNAUTHORIZED_EXECUTION_TRANSITION:{execution_allowed|live_trading_blocked|advisory_only|broker_execution_armed}`, `R7_TRADE_GATE_INACTIVE`, `SAFETY_POSTURE_UNVERIFIABLE`.

The start itself is refused when:
- the tracked tree is dirty;
- the evidence directory already exists;
- `CSS_TEST_MODE`, `CSS_AUTOMATED_INPUT` or `PYTEST_CURRENT_TEST` is set;
- `CSS_ENV` is a development value.

## Evidence recorded

`runtime/endurance/<run-id>/` (git-ignored, so it cannot dirty the release tree):

| File | Contents |
|---|---|
| `RUN_META.json` | Label, run id, release HEAD SHA, branch, configuration fingerprint (env values SHA-256 hashed, never stored), host, start UTC, thresholds |
| `RUN_STATUS.json` | Current status and reasons (atomic writes; terminal states monotonic) |
| `snapshots.jsonl` | Hash-chained, every 60 s: wall and monotonic elapsed, drift and clock step, release SHA and tree state, config fingerprint; supervisor PID, uptime, restart count and timestamps, last exit (code / signal), generation; runtime PID, alive state, process state, heartbeat sequences and gaps, heartbeat classification; memory (RSS / working set), threads, fds or handles for runtime and supervisor; HTTP `/health` status and latency; safety posture (`execution_allowed`, `live_trading_blocked`, `advisory_only`, `broker_execution_armed`, R7 active, broker name / connection / account mode, data freshness, kill switch, resolved mode, engine mode); child-log traceback and error counts |
| `monitor_events.jsonl` | Hash-chained: `RUN_PREPARED`, `SUPERVISOR_LAUNCHED`, `PID_TRANSITION`, `ENGINE_HEARTBEAT_LOST` (classification, gap, expected interval, last sequences, PID state, stack-dump bytes, restart action, resulting state), `UNCAUGHT_EXCEPTION_OBSERVED`, `STALE_DATA`, `CLOCK_ANOMALY`, `INTERIM_CHECKPOINT`, `RUN_INVALIDATED`, `TARGET_REACHED`, `OPERATOR_STOP`, `MONITOR_RESUMED`, `MONITOR_FINISHED` |
| `supervisor_events.jsonl` | Hash-chained: `SUPERVISOR_STARTED`, `CHILD_LAUNCHED`, `CHILD_EXITED_UNEXPECTEDLY` (exit code, signal or NTSTATUS, PID, generation, child-log SHA-256), `CHILD_RESTART_SCHEDULED`, `RUN_FAILED`, `SUPERVISOR_STOPPED` (signal) |
| `supervisor_state.json`, `runtime_heartbeat.json` | Live state (the ledgers are authoritative) |
| `child_logs/generation_NNN.log` | Full runtime stdout and stderr, append-only |
| `runtime_stack_dumps.log` | `faulthandler` all-thread dumps requested on heartbeat loss (POSIX only) |
| `INVALIDATION.json`, `MANIFEST.json`, `MANIFEST_INTERIM.json` | Reasons and snapshot; SHA-256 of every artifact |

`python scripts/css_ov002_endurance.py verify --run-id <id>` re-checks every hash chain and the manifest.

## Why Attempt 3 was not started in the engineering sandbox

The engineering session runs in an ephemeral cloud container that is reclaimed when the session goes idle and can be restarted. It is not the governed host (Attempts 1 and 2 ran on the owner's workstation, with its broker configuration and local evidence custody). A 23–72 h run there would almost certainly end in `EVIDENCE_RECORDER_GAP` or `SUPERVISOR_PROCESS_EXITED`, which would burn the Attempt 3 label on an environment failure. A harness **rehearsal** (non-certifying, separate run id) was run there instead; see the PR #101 checkpoint.

## Harness rehearsals in the engineering sandbox (non-certifying)

None of these is Attempt 3; none credits any time. Evidence stayed in the sandbox; the summaries below come from `verify` and the ledgers.

| Run id | Head | Purpose | Result | What it proved |
|---|---|---|---|---|
| `OV002-HARNESS-REHEARSAL-1` | `638d563` | 10 min clean run | **INVALIDATED** 18 ms after start: `CRITICAL_HEARTBEAT_LOSS:ENGINE_TERMINATED` | **Real defect found:** the first tick ran before the supervisor had reported a PID. Fixed in `8338e22` (missing PID inside the bounded startup grace is `STARTUP_GRACE`), with regression tests |
| `OV002-HARNESS-FAULT-INJECTION-1` | `8338e22` | (interrupted) | `STOPPED_BEFORE_TARGET` (`OPERATOR_STOP:SIGTERM`) at 0.086 h; ledgers verified | Controlled-stop path: terminal, never "complete", supervisor and runtime stopped. Exposed a minor evidence gap (child exit `unknown`), fixed in `b285aec` |
| `OV002-HARNESS-REHEARSAL-2` | `8338e22` | 10 min clean run | **INVALIDATED** at 0.121 h: `RELEASE_TREE_MODIFIED` | Engineering edited a tracked file mid-run (the `b285aec` fix). Detected within one 15 s snapshot. The rule works; the run was spent by operator error |
| `OV002-HARNESS-FAULT-INJECTION-2` | `b285aec` | SIGKILL the runtime after 4 snapshots | **INVALIDATED** 9 s after the kill: `UNEXPECTED_ENGINE_RESTART`; 0 h credited | Exit `-9`/`SIGKILL`, generation, PID transition 17660 → 17787 and restart recorded; supervisor stopped cleanly |
| `OV002-HARNESS-REHEARSAL-3` | `b285aec` | 10 min clean run, 15 s snapshots | **`COMPLETE_PENDING_GOVERNANCE_REVIEW`** at 0.171 h | 42 snapshots (1 `STARTUP_GRACE`, 41 `HEALTHY`); 41/41 HTTP 200 after startup, max 4.8 ms; runtime RSS 54.2 → 54.9 MB; 0 restarts; 0 tracebacks; posture safe throughout (`execution_allowed=false`, `live_trading_blocked=true`, `advisory_only=true`, unarmed, R7 active); `INTERIM_CHECKPOINT` fired; all three hash chains and the manifest verify; no processes left behind |

Detection latency, by construction: a stalled beat is classified LOST once 180 s have passed since the monitor last saw its sequence advance, observed at the next snapshot. That is at most 180 s + one snapshot interval (60 s in Attempt 3).

## Starting Attempt 3 on the governed host

From a fresh console on the host, at the PR #101 head:

```bat
cd C:\rasib\source\capital-strata-systems
git fetch origin css-operator-auth-2026-09-28
git checkout css-operator-auth-2026-09-28
git merge --ff-only origin/css-operator-auth-2026-09-28
git status --short --untracked-files=no
set CSS_ENV=
set CSS_TEST_MODE=
set CSS_AUTOMATED_INPUT=
.venv\Scripts\python.exe -m pytest -q tests\test_endurance_monitor.py tests\test_endurance_supervision.py tests\test_route_auth_inventory.py
.venv\Scripts\python.exe scripts\css_ov002_endurance.py start --run-id OV002-A3-REHEARSAL-HOST --label "OV-002 HARNESS REHEARSAL (non-certifying)" --target-hours 0.25 --interim-hours 0.1 --snapshot-seconds 15
.venv\Scripts\python.exe scripts\css_ov002_endurance.py verify --run-id OV002-A3-REHEARSAL-HOST
.venv\Scripts\python.exe scripts\css_ov002_endurance.py start --run-id OV002-ATTEMPT-3 --label "OV-002 ATTEMPT 3" --target-hours 72 --interim-hours 23
```

Notes for the host:
- `git status` must print nothing. The 15-minute host rehearsal exercises the Windows-only paths (process liveness, working set and handle count, CTRL_BREAK) that Linux CI cannot. Run it first and delete its directory only after it has been reviewed.
- Leave the Attempt 3 console window open. Stop only with **Ctrl+C in that window**: the result is `STOPPED_BEFORE_TARGET`, never complete. Do not pull, commit, check out, edit config files or change environment in that checkout during the run: each invalidates it, by design.
- If the monitor console is closed by accident, resume within 3 minutes with `css_ov002_endurance.py resume --run-id <id>`. A longer gap invalidates.
- Port 8765 must be free, so do not run the mobile launcher on the same port at the same time.
- Report the `RUN_META.json` values (SHA, start UTC, fingerprint) and the evidence path when the run starts.
