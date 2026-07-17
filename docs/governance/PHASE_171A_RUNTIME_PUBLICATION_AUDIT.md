# PHASE 171A — RUNTIME PUBLICATION ARCHITECTURE AUDIT

**Repository:** `/home/claude/css-work`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Baseline commit:** `a913af44e5f8ca7eaba4b3706da48115ac9caa83`  
**Audit mode:** READ-ONLY — no functional changes, no commits, no push  
**Date:** 2026-07-16  

---

## Executive Summary

CSS operates two independent supervisor classes whose instances are spawned
by two independent OS processes at startup time. Both instances default to
the same on-disk artifact path
(`runtime/supervisor/css_runtime_supervisor_state.json`) and perform
non-atomic, lock-free JSON writes. The result is a confirmed last-writer-wins
race condition on every heartbeat and state transition. Mission Control and
the freshness manager treat this file as the **sole canonical source of
runtime liveness**; a stale or corrupted write from either process is
indistinguishable from a genuine runtime failure.

The intended canonical runtime authority is the **launcher process**
(`launcher/css_runtime_launcher.py`), which owns process lifecycle,
restart logic, and heartbeat cadence. The dashboard's `CSSRuntimeSupervisor`
instance is an internal monitoring aid that has no lifecycle authority but
writes to the same artifact, overwriting launcher state with every dashboard
heartbeat cycle (approximately every ~60 cycles × cycle duration).

The minimum Phase 171B correction is a single targeted change: the
**dashboard instance must not share the launcher's canonical state file**.
This can be achieved by giving the dashboard instance a distinct `state_dir`
argument at construction time, converting it to a subordinate diagnostic
artifact rather than a rival canonical publisher.

---

## Repository Baseline

| Field | Value |
|---|---|
| Root | `/home/claude/css-work` |
| Branch | `css-unified-consolidation-2026-07-13` |
| HEAD | `a913af44e5f8ca7eaba4b3706da48115ac9caa83` |
| Remote HEAD | `a913af44e5f8ca7eaba4b3706da48115ac9caa83` |
| Working tree | Clean — `git diff --check` confirmed no changes |

---

## Producer Inventory

### 1. CSSRuntimeSupervisor Instances

#### Instance A — Launcher Process

| Field | Value |
|---|---|
| **File** | `launcher/css_runtime_launcher.py` |
| **Line** | 180 |
| **Constructor** | `CSSRuntimeSupervisor()` — all defaults |
| **state_dir** | `"runtime/supervisor"` (relative default) |
| **Resolved state_file** | `<REPO_ROOT>/runtime/supervisor/css_runtime_supervisor_state.json` |
| **Process** | `css_runtime_launcher.py` — the root supervisor process |
| **Calls start()** | Yes — line 181, immediately after construction |
| **Calls heartbeat()** | Yes — every 10 seconds (`time.sleep(10)`, line 209–210) |
| **Additional triggers** | `record_failure()`, `record_restart_attempt()`, `record_restart_success()`, `record_restart_exhausted()` on service events |
| **Artifact written** | `runtime/supervisor/css_runtime_supervisor_state.json` |

The launcher's `CSSRuntimeSupervisor` is the intended lifecycle owner. It
starts the child processes (CSS Runtime, Mobile Launcher), monitors them in
a tight 10-second loop, drives all restart logic, and owns the heartbeat
cadence. It has no constructor arguments — it accepts all defaults.

---

#### Instance B — Dashboard Process (Child of Launcher)

| Field | Value |
|---|---|
| **File** | `scripts/css_live_dashboard.py` |
| **Line** | 900 |
| **Constructor** | `CSSRuntimeSupervisor(alert_service=css_runtime_alert_service)` |
| **state_dir** | `"runtime/supervisor"` (relative default, **identical to Instance A**) |
| **Resolved state_file** | `<REPO_ROOT>/runtime/supervisor/css_runtime_supervisor_state.json` |
| **Process** | `scripts/css_live_dashboard.py` — child subprocess of the launcher |
| **Calls start()** | Yes — line 4792, after `perform_startup_reconciliation()` |
| **Calls heartbeat()** | Yes — every 60 trading cycles (line 4817); each cycle is variable-length (default `CYCLE_SLEEP = 8`s, configurable to 60s+ in continuous mode) |
| **Additional triggers** | `record_failure()` on unhandled exceptions, `stop()` on exit, `check_stale_heartbeat()` on every heartbeat call |
| **Artifact written** | `runtime/supervisor/css_runtime_supervisor_state.json` — **same path as Instance A** |

The dashboard's `CSSRuntimeSupervisor` is a monitoring aid. Its `supervisor_id`
UUID differs from the launcher's because each instance generates a fresh UUID
at construction time (`str(uuid.uuid4())`). It has no restart authority, no
child process management, and no service lifecycle knowledge. However, because
it shares the same default `state_dir`, every write it performs
**overwrites the launcher's authoritative state with a different `supervisor_id`**.

---

### 2. RuntimeSupervisor Instances (Separate Class)

| Field | Value |
|---|---|
| **Class** | `RuntimeSupervisor` in `backend/runtime/runtime_supervisor.py` |
| **File** | `scripts/css_live_dashboard.py` line 1017 |
| **Constructor** | `RuntimeSupervisor()` — all defaults |
| **Artifact** | `<REPO_ROOT>/runtime_supervisor.json` (resolved via `Path(__file__).resolve().parents[2]`) |
| **Process** | Dashboard child process |
| **Write triggers** | `__init__` (start_time), `record_cycle()` (every trading cycle), `record_error()`, `record_recovery_attempt()`, `record_broker_disconnect()`, watchdog thread (background, every 30 seconds) |
| **Write frequency** | Every trading cycle (~8–60 seconds); watchdog every 30 seconds |
| **Lock** | `threading.RLock()` — internal writes are thread-safe |

This is a distinct file (`runtime_supervisor.json` at the repository root)
and a distinct class from `CSSRuntimeSupervisor`. It is not consumed by
Mission Control directly and does not participate in the race condition on
`css_runtime_supervisor_state.json`. Included here for completeness.

---

### 3. RuntimeArtifactPublisher

| Field | Value |
|---|---|
| **Class** | `RuntimeArtifactPublisher` in `backend/runtime/runtime_artifact_publisher.py` |
| **Caller** | `scripts/css_live_dashboard.py` → `pcnrass_publish_runtime_artifacts()` line 1347 |
| **Called from** | Main trading cycle, line 5401 |
| **Frequency** | Every trading cycle (every 8–60 seconds in continuous mode) |
| **Artifacts written** | 7 files, all in `<REPO_ROOT>/artifacts/`: |
| | `css_account_state_pcnrass.json` |
| | `css_session_state_pcnrass.json` |
| | `runtime_portfolio_state.json` |
| | `runtime_advisory_snapshot.json` |
| | `portfolio_snapshot.json` |
| | `portfolio_decision.json` |
| | `validation_summary.json` |
| **Write method** | `Path.write_text(json.dumps(...))` — non-atomic, no lock |
| **Process** | Dashboard child process only |
| **Schema** | `136A.1`; all artifacts include `advisory_only: true`, `execution_allowed: false` |

---

### 4. _pcnrass_write_json (Direct dashboard writes)

| Artifact | Line | Trigger |
|---|---|---|
| `artifacts/css_session_state_pcnrass.json` | 1252 | Session initialization and every account refresh |
| `artifacts/css_account_state_pcnrass.json` | 1266, 5487 | Account state refresh and on certain PnL events |
| `artifacts/css_mobile_controls.json` | 3122 | Mobile control submission |

All three are written by `_pcnrass_write_json()` which calls
`Path.write_text(json.dumps(...))` — non-atomic.

---

## Consumer Inventory

### Mission Control — `dashboard/mission_control/`

| Consumer | File | Artifact consumed | Purpose |
|---|---|---|---|
| `RuntimeArtifactReader` | `dashboard/mission_control/runtime_artifact_reader.py:24–29` | `runtime/supervisor/css_runtime_supervisor_state.json` (via `supervisor_state_path` default) | Read supervisor health into runtime candidate |
| `RuntimeArtifactReader` | same | All 7 `artifacts/*.json` files | Build full runtime source candidate payload |
| `RuntimeSnapshotProvider` | `dashboard/mission_control/runtime_snapshot_provider.py:21,27,93–95` | `runtime/supervisor/css_runtime_supervisor_state.json` | Hydrate runtime snapshot; fallback to `Path.cwd()/path` if relative read fails |
| `RuntimeSourceResolver` | `dashboard/mission_control/runtime_source_resolver.py:29,35,81` | Via `RuntimeArtifactReader` | Select active runtime source from candidates |
| `RuntimeArtifactFreshnessManager` | `backend/runtime/runtime_artifact_freshness.py:56,66` | `runtime/supervisor/css_runtime_supervisor_state.json` (classified as CRITICAL, 120s threshold) | Classify all artifacts as GREEN/AMBER/STALE/MISSING |
| `css_mobile_launcher.py` | `launcher/css_mobile_launcher.py:1266,2095,2194` | `runtime/supervisor/css_runtime_supervisor_state.json` (via `LauncherConfig.SUPERVISOR_STATE_FILE`) | Runtime snapshot in mobile launcher routes |
| `css_mobile_launcher.py` *(conditional fallback writer)* | `launcher/css_mobile_launcher.py:2138–2150` — `_publish_supervisor_heartbeat_snapshot()` | `runtime/supervisor/css_runtime_supervisor_state.json` | **Discovered during Phase 171B implementation verification.** Writes a minimal heartbeat payload `{status, last_heartbeat, source, advisory_only, execution_allowed}` to the canonical path **only when** `supervisor_state` freshness is `MISSING` or `STALE` (>120s). Under normal operation (launcher heartbeating every 10s) this write is **always skipped**. This is intentional gap-filling behavior: if the primary publisher (launcher) has stopped, the mobile launcher provides a RUNNING signal until the canonical publisher recovers. The write format differs from `CSSRuntimeSupervisor` format; `get_supervisor_summary()` bridges both schemas by reading `last_heartbeat` or `last_heartbeat_at`. This is a **third writer**, not a competing primary publisher. |

### Freshness Classification for supervisor_state

The `RuntimeArtifactFreshnessManager` classifies `supervisor_state` as
**CRITICAL** with a threshold of **120 seconds** (`DEFAULT_THRESHOLDS["supervisor_state"] = 120.0`).
Freshness is evaluated by **filesystem mtime** (`path.stat().st_mtime`),
not by reading the `last_heartbeat_at` field inside the JSON. This means
any process write to the file resets the staleness clock, regardless of
which process wrote it or what `supervisor_id` it carried.

---

## Artifact Matrix

| Artifact | Canonical path | Writer(s) | Consumer(s) | Write frequency | Lock? |
|---|---|---|---|---|---|
| `css_runtime_supervisor_state.json` | `runtime/supervisor/` | **Instance A (Launcher)** every 10s; **Instance B (Dashboard)** every ~60 cycles; **Mobile Launcher fallback** when freshness is MISSING/STALE | RuntimeArtifactReader, RuntimeSnapshotProvider, RuntimeSourceResolver, FreshnessManager, MobileLauncher | 10s (launcher), ~60-cycle variable (dashboard), on-demand fallback (mobile) | None |
| `runtime_supervisor.json` | `<REPO_ROOT>/` | RuntimeSupervisor (dashboard process only) | None (internal stats only) | Every trading cycle + watchdog 30s | `threading.RLock()` |
| `artifacts/css_account_state_pcnrass.json` | `artifacts/` | `_pcnrass_write_json`, `RuntimeArtifactPublisher` | RuntimeArtifactReader, RuntimeSnapshotProvider | Every cycle | None |
| `artifacts/css_session_state_pcnrass.json` | `artifacts/` | `_pcnrass_write_json`, `RuntimeArtifactPublisher` | RuntimeArtifactReader, RuntimeSnapshotProvider | Every cycle | None |
| `artifacts/runtime_portfolio_state.json` | `artifacts/` | `RuntimeArtifactPublisher` | RuntimeArtifactReader | Every cycle | None |
| `artifacts/runtime_advisory_snapshot.json` | `artifacts/` | `RuntimeArtifactPublisher` | RuntimeArtifactReader | Every cycle | None |
| `artifacts/portfolio_snapshot.json` | `artifacts/` | `RuntimeArtifactPublisher` | RuntimeArtifactReader | Every cycle | None |
| `artifacts/portfolio_decision.json` | `artifacts/` | `RuntimeArtifactPublisher` | RuntimeArtifactReader | Every cycle | None |
| `artifacts/validation_summary.json` | `artifacts/` | `RuntimeArtifactPublisher` | RuntimeArtifactReader | Every cycle | None |
| `artifacts/css_mobile_controls.json` | `artifacts/` | Mobile control submit | Mobile launcher, Dashboard | On operator action | None |

---

## Publication Graph

```
┌─────────────────────────────────────────────────────────────────┐
│ LAUNCHER PROCESS (css_runtime_launcher.py)                      │
│                                                                 │
│   CSSRuntimeSupervisor [Instance A]                             │
│   state_dir = "runtime/supervisor"  (default)                   │
│   supervisor_id = UUID-A                                        │
│   heartbeat() every 10 seconds                                  │
│                              │                                  │
│               _persist_state() — non-atomic open("w")          │
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               ↓
          ┌────────────────────────────────────────┐
          │  runtime/supervisor/                   │
          │  css_runtime_supervisor_state.json     │  ← SHARED ARTIFACT
          └────────────────────────────────────────┘
                               ↑
┌──────────────────────────────┼──────────────────────────────────┐
│ DASHBOARD PROCESS (css_live_dashboard.py) — child of launcher  │
│                                                                 │
│   CSSRuntimeSupervisor [Instance B]                             │
│   state_dir = "runtime/supervisor"  (default — SAME PATH)       │
│   supervisor_id = UUID-B  (different UUID)                      │
│   heartbeat() every ~60 cycles (~8–60s each)                    │
│                              │                                  │
│               _persist_state() — non-atomic open("w")          │
└─────────────────────────────────────────────────────────────────┘

          ┌────────────────────────────────────────┐
          │  runtime/supervisor/                   │
          │  css_runtime_supervisor_state.json     │
          └───────────────────┬────────────────────┘
                              │  (read by)
              ┌───────────────┼───────────────────┐
              ↓               ↓                   ↓
  RuntimeArtifactReader   RuntimeSnapshotProvider  RuntimeArtifactFreshnessManager
  (dashboard/mission_control/) (artifact_root)     (supervisor_state: CRITICAL, 120s)
              │               │                   │
              └───────────────┼───────────────────┘
                              ↓
                    RuntimeSourceResolver
                              │
                              ↓
                    Mission Control UI

┌─────────────────────────────────────────────────────────────────┐
│ DASHBOARD PROCESS — separate artifact stream                    │
│                                                                 │
│   RuntimeSupervisor                                             │
│   ├─ Writes: runtime_supervisor.json (REPO_ROOT)                │
│   │  on every cycle, record_error(), broker_disconnect()        │
│   │  watchdog thread every 30s                                  │
│   └─ Not consumed by Mission Control                            │
│                                                                 │
│   RuntimeArtifactPublisher                                      │
│   ├─ Writes artifacts/*.json (7 files) every trading cycle      │
│   └─ Consumed by RuntimeArtifactReader, RuntimeSnapshotProvider │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ MOBILE LAUNCHER PROCESS (launcher/css_mobile_launcher.py)       │
│                                                                 │
│   Reads css_runtime_supervisor_state.json (3 routes)           │
│   via LauncherConfig.SUPERVISOR_STATE_FILE                      │
│                                                                 │
│   CONDITIONAL FALLBACK WRITE (discovered Phase 171B):           │
│   _publish_supervisor_heartbeat_snapshot() at line 2138         │
│   → Writes minimal heartbeat payload to canonical path          │
│   → Triggered ONLY when supervisor_state freshness is           │
│     MISSING or STALE (>120s without launcher heartbeat)         │
│   → Under normal operation this path is ALWAYS SKIPPED          │
│   → Gap-fill writer, NOT a competing primary publisher          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Heartbeat Trace

### Launcher heartbeat (Instance A)

```
run_launcher() main loop
  └─ while True:
       time.sleep(10)                               ← 10-second cadence
       supervisor.heartbeat()                       ← launcher/css_runtime_launcher.py:210
         └─ CSSRuntimeSupervisor.heartbeat()
              last_heartbeat_at = utcnow().isoformat()
              _persist_state()                      ← open("w") json.dump — no lock
                └─ writes runtime/supervisor/css_runtime_supervisor_state.json
```

**Cadence:** Fixed, every 10 seconds.

### Dashboard heartbeat (Instance B)

```
while True:  (main trading cycle)
  if cycle % 60 == 0:                              ← scripts/css_live_dashboard.py:4814
    if css_supervisor:
      css_supervisor.heartbeat()                   ← line 4817
        └─ CSSRuntimeSupervisor.heartbeat()
             last_heartbeat_at = utcnow().isoformat()
             _persist_state()                      ← open("w") json.dump — no lock
               └─ writes runtime/supervisor/css_runtime_supervisor_state.json
      css_supervisor.check_stale_heartbeat()       ← line 4818
        └─ reads self.last_heartbeat_at (in-memory only, not re-read from disk)
```

**Cadence:** Every 60 cycles; each cycle sleeps `CYCLE_SLEEP=8s` minimum
(continuous mode configurable to 60s+). Approximate range: 8 minutes
(8s × 60 cycles) to 60 minutes (60s × 60 cycles). **Significantly slower
than the launcher's 10-second heartbeat.**

### Key asymmetry

| Property | Launcher (Instance A) | Dashboard (Instance B) |
|---|---|---|
| Heartbeat cadence | 10 seconds | ~8–60 minutes |
| Write on start() | Yes (status=RUNNING, started_at set) | Yes (same fields, different supervisor_id) |
| supervisor_id | UUID-A (stable per launcher run) | UUID-B (different UUID, overrides UUID-A) |
| last_heartbeat_at | Set every 10s | Set every ~8–60 min |
| status field | Reflects service lifecycle | Reflects dashboard internal state |
| Owns restart logic | Yes | No |

---

## Duplicate Publisher Findings

**CONFIRMED: Two independent CSSRuntimeSupervisor instances write to the
same canonical state file with no coordination, no locking, and different
`supervisor_id` values.**

Evidence:

1. **Path resolution** (verified by direct Python evaluation):
   - Launcher: `state_dir="runtime/supervisor"` → `<REPO_ROOT>/runtime/supervisor/css_runtime_supervisor_state.json`
   - Dashboard: `state_dir="runtime/supervisor"` → `<REPO_ROOT>/runtime/supervisor/css_runtime_supervisor_state.json`
   - These resolve to the **identical absolute path**.

2. **Independent UUIDs**: `CSSRuntimeSupervisor.__init__` sets
   `self.supervisor_id = str(uuid.uuid4())`. Both instances receive
   different UUIDs. Every dashboard write overwrites the `supervisor_id`
   field, making the file's `supervisor_id` non-stable across write cycles.

3. **Independent in-memory state**: Each instance tracks its own
   `started_at`, `failure_count`, `restart_count`, `last_failure`, and
   `last_canonical_decision` in memory. When the dashboard writes its state,
   all of these reflect dashboard-process events only, erasing the launcher's
   lifecycle history from the file.

4. **No locking**: `_persist_state()` uses `open(self.state_file, "w")` +
   `json.dump()`. This is a non-atomic truncate-then-write sequence with no
   interprocess lock and no atomic rename (`os.replace`). Concurrent writes
   from two processes can produce a partially-written or truncated JSON file.

---

## Race Condition Assessment

**Severity: HIGH**

### Confirmed race scenario at startup

```
t=0       Launcher starts, creates Instance A, calls start()
          → Writes {supervisor_id: UUID-A, status: RUNNING, started_at: T0,
                    last_heartbeat_at: null, failure_count: 0}

t=ε       Dashboard subprocess starts (spawned by launcher)
          → Creates Instance B, calls start()
          → Writes {supervisor_id: UUID-B, status: RUNNING, started_at: T0+ε,
                    last_heartbeat_at: null, failure_count: 0}
          → UUID-A is now GONE from disk

t=10s     Launcher heartbeat fires
          → Writes {supervisor_id: UUID-A, last_heartbeat_at: T0+10s, ...}

t=10s+ε   Dashboard heartbeat fires only on cycle % 60
          (does NOT fire at t=10s; fires next at t~=8 minutes)
          → Launcher state is intact until the dashboard's first heartbeat
```

After ~8 minutes (or at first dashboard cycle % 60 = 0), the dashboard
overwrites the launcher's state:

```
t≈8min    Dashboard heartbeat fires (cycle 60, cycle_sleep=8s)
          → Writes {supervisor_id: UUID-B, status: RUNNING,
                    last_heartbeat_at: T0+8min, started_at: T0+ε,
                    failure_count: 0, restart_count: 0}
          → Launcher's UUID-A, failure_count, restart_count are erased
```

### Mission Control impact

Mission Control reads `css_runtime_supervisor_state.json` for:
1. **CRITICAL freshness** (threshold 120s via mtime). The file is kept fresh
   by launcher writes (every 10s) under normal operation. However, if the
   launcher exits and the dashboard continues, the dashboard's slower heartbeat
   cadence means the file goes stale within 2 minutes (120s threshold) between
   dashboard cycles in manual mode.

2. **supervisor_id**: Consumers that cache or compare `supervisor_id`
   across reads will see an inconsistent value whenever the dashboard writes.
   `RuntimeSnapshotProvider._read_json(self.supervisor_state_path)` and
   `RuntimeArtifactReader` both return the whole parsed JSON — if the
   `supervisor_id` field cycles between UUID-A and UUID-B on consecutive
   reads, any consumer comparing supervisor identity will see phantom
   "supervisor changes."

3. **started_at / failure_count / restart_count**: After a dashboard write,
   these reflect dashboard-process history only. A launcher that has
   restarted a child service 3 times will show `restart_count: 0` in the
   file for the duration of the next dashboard write cycle.

### Non-atomic write risk

`open("w") + json.dump()` truncates the file first, then writes. If two
processes interleave at this boundary:

```
Process A: open("w") → truncates file to 0 bytes
Process B: open("w") → truncates already-empty file
Process A: json.dump writes partial JSON
Process B: json.dump writes its JSON (corrupts or races A's write)
```

The result can be a truncated JSON file (0 bytes or partial JSON), which
`json.loads()` will raise on. `RuntimeArtifactReader._read_json()` and
`RuntimeSnapshotProvider._read_json()` catch exceptions and return `None`,
causing Mission Control to fall back to `SOURCE_HISTORICAL` or
`SOURCE_UNAVAILABLE` — a visible "runtime offline" state even when both
processes are running normally.

---

## Canonical Runtime Authority Recommendation

**The launcher (`launcher/css_runtime_launcher.py`, Instance A) is the
intended canonical runtime authority.**

Evidence:

1. **Lifecycle ownership**: The launcher is the root process. It spawns and
   monitors the dashboard subprocess. It calls `supervisor.start()` before
   any child process exists, and `supervisor.stop()` after all children exit.
   The launcher is the only process with a complete view of child process
   lifecycle.

2. **Restart ownership**: All restart decisions, backoff computation,
   `record_restart_attempt`, `record_restart_success`, and
   `record_restart_exhausted` calls originate from the launcher. The
   dashboard has no knowledge of whether it has been restarted.

3. **Heartbeat cadence**: The launcher heartbeats every 10 seconds — six
   times per minute, well within the 120-second freshness threshold. The
   dashboard heartbeats every ~8–60 minutes. Mission Control's freshness
   expectations align with the launcher's cadence, not the dashboard's.

4. **Mission Control expectations**: `RuntimeArtifactReader` comments
   `"publisher": "scripts.css_live_dashboard.pcnrass_publish_runtime_artifacts"` —
   this refers to the **trading-cycle artifact publisher** (the 7 `artifacts/*.json`
   files), not the supervisor state file. The supervisor state file is expected
   to be written by the supervisor process, which is the launcher.

5. **Naming convention**: The launcher's supervisor has no constructor
   arguments (pure defaults). The dashboard's supervisor accepts an
   `alert_service` argument — it was clearly added to support dashboard-side
   alerting, not to be a canonical publisher.

---

## Minimum Phase 171B Correction

**One targeted, minimal change: give the dashboard's `CSSRuntimeSupervisor`
a distinct `state_dir` that does not conflict with the launcher's canonical
path.**

No functional behavior changes. No new classes. No architectural redesign.

**Proposed change** (to be implemented in Phase 171B, not here):

In `scripts/css_live_dashboard.py` at line 900, change:

```python
# BEFORE (current — causes race condition)
css_supervisor = CSSRuntimeSupervisor(alert_service=css_runtime_alert_service)

# AFTER (Phase 171B correction)
css_supervisor = CSSRuntimeSupervisor(
    alert_service=css_runtime_alert_service,
    state_dir="runtime/supervisor/dashboard",  # subordinate path, non-conflicting
)
```

This change:
- Eliminates the duplicate write to the canonical path
- Preserves all dashboard supervisor alerting and health-check behavior
- Preserves the launcher as the sole canonical publisher of
  `runtime/supervisor/css_runtime_supervisor_state.json`
- Requires no changes to Mission Control, the freshness manager, or any consumer
- Requires no changes to the launcher
- Introduces no new dependencies

The dashboard's subordinate state at `runtime/supervisor/dashboard/css_runtime_supervisor_state.json`
can be treated as a diagnostic artifact. It may optionally be exposed via a
separate diagnostic endpoint in Mission Control in a future phase.

---

## Risks

| Risk | Severity | Notes |
|---|---|---|
| Truncated JSON during concurrent write | HIGH | Non-atomic `open("w")` can produce 0-byte or partial files. Mission Control falls back to UNAVAILABLE on parse failure. |
| supervisor_id instability | HIGH | Any consumer comparing supervisor identity across reads will see phantom identity changes when dashboard overwrites launcher state. |
| Mission Control shows "runtime offline" mid-run | MEDIUM | If the launcher exits but the dashboard continues, the file goes stale within 120s between dashboard heartbeats in manual (non-continuous) mode. |
| Dashboard `check_stale_heartbeat()` reads in-memory state only | MEDIUM | The dashboard checks `self.last_heartbeat_at` (in-memory), not the file. If the launcher's heartbeat is the most recent file write, the dashboard may incorrectly conclude its own last heartbeat was recent when checking for staleness. |
| restart_count / failure_count loss | MEDIUM | After a dashboard write, all launcher restart history is erased from the file until the launcher overwrites it again. |
| All artifact writes are non-atomic | LOW | `_pcnrass_write_json`, `RuntimeArtifactPublisher`, and `_persist_state` all use truncate-then-write. Only the single-process `RuntimeSupervisor` uses an `RLock`. Race risk is lower for single-process artifacts but still present for rapid successive writes within the dashboard. |

---

## Open Questions

1. **Is `runtime/supervisor/css_runtime_supervisor_state.json` ever read
   back from disk by either supervisor instance?**
   Neither `CSSRuntimeSupervisor` nor `RuntimeSupervisor` re-reads the state
   file on init. In-memory state is authoritative for each instance. This
   means the file is write-only from each instance's perspective — it cannot
   detect that another process is writing to the same file.

2. **Does Mission Control cache the `supervisor_id` across requests?**
   Not observed in the current codebase. However, if caching is added,
   `supervisor_id` instability will become immediately visible.

3. **Are there any test fixtures or CI processes that write to
   `runtime/supervisor/`?**
   **Resolved during Phase 171B implementation.** All existing tests that
   exercise `CSSRuntimeSupervisor` pass an explicit `state_dir=temp_dir`
   argument using `pytest`'s `tmp_path` fixture. No test writes to the
   production `runtime/supervisor/` path. CI isolation is confirmed.

4. **What is the expected behavior if `css_supervisor` is `None` in the
   dashboard?**
   All dashboard supervisor calls are guarded by `if css_supervisor:`. If the
   `CSSRuntimeSupervisor` import fails, the dashboard silently skips all
   supervisor operations. This is safe but means the canonical supervisor
   state file might not be updated — and the launcher's writes remain
   uncorrupted. Phase 171B should consider whether the fallback `None`
   guard should emit a startup warning.

5. **Does the launcher's supervisor call `record_canonical_decision()`?**
   Not observed. `record_canonical_decision()` is defined on
   `CSSRuntimeSupervisor` and persists `last_canonical_decision` to the
   state file, but no caller in the launcher invokes it. The dashboard does
   not call it either. This field is currently unused at runtime.

---

## Evidence Appendix

### File:Line References

| Finding | File | Lines |
|---|---|---|
| Instance A construction | `launcher/css_runtime_launcher.py` | 180 |
| Instance A `start()` call | `launcher/css_runtime_launcher.py` | 181 |
| Instance A heartbeat loop | `launcher/css_runtime_launcher.py` | 209–210 |
| Instance B construction | `scripts/css_live_dashboard.py` | 900 |
| Instance B conditional guard | `scripts/css_live_dashboard.py` | 894 |
| Instance B `start()` call | `scripts/css_live_dashboard.py` | 4791–4792 |
| Instance B heartbeat + stale check | `scripts/css_live_dashboard.py` | 4814–4818 |
| Instance B `record_failure()` | `scripts/css_live_dashboard.py` | 5442–5443 |
| Instance B `stop()` | `scripts/css_live_dashboard.py` | 5459–5460 |
| `state_dir` default | `backend/runtime/css_runtime_supervisor.py` | 19 |
| `state_file` construction | `backend/runtime/css_runtime_supervisor.py` | 27–29 |
| `supervisor_id = uuid.uuid4()` | `backend/runtime/css_runtime_supervisor.py` | 17 |
| `_persist_state()` non-atomic write | `backend/runtime/css_runtime_supervisor.py` | 72–78 |
| `heartbeat()` triggers `_persist_state` | `backend/runtime/css_runtime_supervisor.py` | 127–129 |
| `start()` triggers `_persist_state` | `backend/runtime/css_runtime_supervisor.py` | 102–113 |
| `RuntimeSupervisor` default state file | `backend/runtime/runtime_supervisor.py` | 14 |
| `RuntimeSupervisor` thread-safe lock | `backend/runtime/runtime_supervisor.py` | 30, 69 |
| `RuntimeArtifactPublisher` artifacts | `backend/runtime/runtime_artifact_publisher.py` | 66–75 |
| `pcnrass_publish_runtime_artifacts` caller | `scripts/css_live_dashboard.py` | 5401 |
| `ARTIFACTS_DIR` declaration | `scripts/css_live_dashboard.py` | 1188 |
| `PROJECT_ROOT` declaration | `scripts/css_live_dashboard.py` | 877 |
| `CYCLE_SLEEP` default | `scripts/css_live_dashboard.py` | 1413 |
| `RuntimeArtifactReader` supervisor path | `dashboard/mission_control/runtime_artifact_reader.py` | 24 |
| `RuntimeSnapshotProvider` supervisor path | `dashboard/mission_control/runtime_snapshot_provider.py` | 21, 93–95 |
| `RuntimeSourceResolver` supervisor path | `dashboard/mission_control/runtime_source_resolver.py` | 29, 81 |
| `FreshnessManager` CRITICAL classification | `backend/runtime/runtime_artifact_freshness.py` | 18, 40 |
| `FreshnessManager` supervisor default path | `backend/runtime/runtime_artifact_freshness.py` | 66 |
| `FreshnessManager` mtime-based freshness | `backend/runtime/runtime_artifact_freshness.py` | 145–160 |
| `LauncherConfig.SUPERVISOR_STATE_FILE` | `launcher/css_launcher_config.py` | 5–6 |
| Mobile launcher reads supervisor state | `launcher/css_mobile_launcher.py` | 1266, 2095, 2194 |
| Mobile launcher `_publish_supervisor_heartbeat_snapshot()` (conditional fallback writer) | `launcher/css_mobile_launcher.py` | 2138–2150 |
| Mobile launcher `ensure_runtime_artifacts_current()` (calls fallback writer) | `launcher/css_mobile_launcher.py` | 2100–2134 |
| Mobile launcher `get_launcher_live_readiness_blockers_feed()` (calls `ensure_runtime_artifacts_current`) | `launcher/css_mobile_launcher.py` | 1158–1159 |
| Mobile launcher `get_supervisor_summary()` (reads canonical, bridges field names) | `launcher/css_mobile_launcher.py` | 324–356 |

