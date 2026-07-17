# PHASE 171B — IMPLEMENTATION PLAN
## Runtime Publication Race Condition Remediation

**Repository:** `Capital Strata Systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Baseline:** `a913af44e5f8ca7eaba4b3706da48115ac9caa83`  
**Phase 171A audit:** `docs/governance/PHASE_171A_RUNTIME_PUBLICATION_AUDIT.md`  
**Plan status:** AWAITING APPROVAL — no production code modified  
**Date:** 2026-07-16  

---

## 1. Scope Statement

Phase 171A confirmed a single root cause: two independent
`CSSRuntimeSupervisor` instances — one in the launcher process and one in the
dashboard subprocess — write to the **same canonical artifact path** with no
coordination, no locking, and different `supervisor_id` values. The minimum
safe correction is a **single constructor argument change** that routes the
dashboard's supervisor state to a subordinate path, leaving the canonical path
exclusively owned by the launcher.

No new classes. No interface changes. No consumer changes. One line of
production code changes.

A pre-existing signature defect discovered during the evidence pass is
documented as a secondary finding and planned as a follow-up fix bundled into
the same commit.

---

## 2. Authoritative Definitions

| Term | Value |
|---|---|
| **Canonical supervisor** | `CSSRuntimeSupervisor` instance in `launcher/css_runtime_launcher.py` (Instance A) |
| **Secondary supervisor** | `CSSRuntimeSupervisor` instance in `scripts/css_live_dashboard.py` (Instance B) |
| **Canonical artifact** | `runtime/supervisor/css_runtime_supervisor_state.json` |
| **Secondary artifact** | `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` *(new, Phase 171B)* |
| **Subordinate path** | `runtime/supervisor/dashboard/` — created automatically by `_ensure_state_dir()` at first write |

No existing consumers point to the secondary artifact. The canonical artifact
path and all consumer defaults are unchanged.

---

## 3. Files That Will Change

### 3A. Primary change — production code

| File | Type | Risk |
|---|---|---|
| `scripts/css_live_dashboard.py` | Modify — 1 constructor argument added | LOW |

No other production files change.

### 3B. Secondary change — pre-existing defect fix (bundled)

| File | Type | Risk |
|---|---|---|
| `scripts/css_live_dashboard.py` | Modify — pre-existing `record_restart()` call site corrected | LOW |

This is bundled with the primary change because it is in the same file and
involves the same `css_supervisor` object.

### 3C. New test file

| File | Type | Risk |
|---|---|---|
| `tests/test_phase171b_supervisor_path_isolation.py` | New — audit-driven test | LOW |

### 3D. Files that do NOT change

| File | Why unchanged |
|---|---|
| `backend/runtime/css_runtime_supervisor.py` | No interface change; constructor already accepts `state_dir` |
| `launcher/css_runtime_launcher.py` | Canonical publisher; no changes needed |
| `dashboard/mission_control/runtime_artifact_reader.py` | Defaults to canonical path; unchanged |
| `dashboard/mission_control/runtime_snapshot_provider.py` | Defaults to canonical path; unchanged |
| `dashboard/mission_control/runtime_source_resolver.py` | Defaults to canonical path; unchanged |
| `backend/runtime/runtime_artifact_freshness.py` | Defaults to canonical path; unchanged |
| `launcher/css_launcher_config.py` | `SUPERVISOR_STATE_FILE` remains canonical path; unchanged |
| `launcher/css_mobile_launcher.py` | Reads canonical path via `LauncherConfig`; unchanged |
| All broker files | Not in scope |
| All risk/strategy files | Not in scope |

---

## 4. Exact Code Changes

### Change 1 — Primary: Dashboard supervisor `state_dir` (REQUIRED)

**File:** `scripts/css_live_dashboard.py`  
**Location:** Lines 896–901 (the `CSSRuntimeSupervisor` construction block)

```python
# ── BEFORE (current HEAD — causes race condition) ─────────────────────────
css_runtime_alert_service = None
css_supervisor = None
try:
    from backend.monitoring.css_alert_service import CSSAlertService
    from backend.monitoring.css_alert_models import AlertSeverity
    from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
    css_runtime_alert_service = CSSAlertService()
    css_supervisor = CSSRuntimeSupervisor(alert_service=css_runtime_alert_service)
except Exception as alert_init_e:
    print(f"[ALERT SERVICE INIT WARN] {alert_init_e}")

# ── AFTER (Phase 171B) ────────────────────────────────────────────────────
css_runtime_alert_service = None
css_supervisor = None
try:
    from backend.monitoring.css_alert_service import CSSAlertService
    from backend.monitoring.css_alert_models import AlertSeverity
    from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
    css_runtime_alert_service = CSSAlertService()
    css_supervisor = CSSRuntimeSupervisor(
        alert_service=css_runtime_alert_service,
        # Phase 171B: use a subordinate state_dir to avoid writing to the
        # canonical supervisor artifact owned by css_runtime_launcher.py.
        # The canonical path (runtime/supervisor/) remains exclusively written
        # by the launcher process.  This instance is a subordinate diagnostic
        # supervisor only.
        state_dir="runtime/supervisor/dashboard",
    )
except Exception as alert_init_e:
    print(f"[ALERT SERVICE INIT WARN] {alert_init_e}")
```

**What this does:**
- Dashboard instance now writes to `runtime/supervisor/dashboard/css_runtime_supervisor_state.json`
- Canonical path `runtime/supervisor/css_runtime_supervisor_state.json` is no longer touched by the dashboard
- `_ensure_state_dir()` creates the `runtime/supervisor/dashboard/` directory on first write
- No behavioral changes to any of the supervisor methods

---

### Change 2 — Secondary: Pre-existing `record_restart()` signature mismatch (REQUIRED)

**File:** `scripts/css_live_dashboard.py`  
**Location:** Line 3845

**Finding:** `record_restart()` is defined as `def record_restart(self)` (no
parameters beyond `self`). At line 3845, the dashboard calls it with a
positional argument:

```python
css_supervisor.record_restart("RESUME_PREVIOUS_SESSION")
```

This raises `TypeError: record_restart() takes 1 positional argument but 2
were given` at module-level startup code when `CSS_RESUME_SESSION=true` and a
saved session state exists. Because the call is not inside a `try/except`, this
TypeError propagates and crashes the dashboard startup sequence when session
resumption is attempted.

This defect is pre-existing (not introduced by Phase 171B). It is bundled here
because: (a) it is in the same file and same object, and (b) it would be
discovered during regression testing of the primary change.

```python
# ── BEFORE (current HEAD — pre-existing defect) ───────────────────────────
    if css_supervisor:
        css_supervisor.record_restart("RESUME_PREVIOUS_SESSION")

# ── AFTER (Phase 171B — remove spurious positional argument) ─────────────
    if css_supervisor:
        css_supervisor.record_restart()  # Phase 171B: removed invalid positional arg
```

**What this does:**
- Removes the invalid positional argument
- `record_restart()` behavior is unchanged; it already records the restart
  correctly via `self.restart_count += 1` and `self.status = "RUNNING"`
- No behavioral change when `CSS_RESUME_SESSION` is not set (the `if
  css_supervisor` guard is still present and the code path is only reached when
  `saved_state and RESUME_PREVIOUS_SESSION`)

---

## 5. Constructor Signature Analysis

### Does any constructor signature change?

**No.** `CSSRuntimeSupervisor.__init__` already accepts `state_dir: str =
"runtime/supervisor"` as a keyword argument. The Phase 171B change passes a
different value for this existing parameter. No interface modification is
required.

```python
# Current signature (unchanged):
def __init__(
    self,
    state_dir: str = "runtime/supervisor",       # ← already exists
    max_restart_limit: int = 3,
    alert_service: Optional[CSSAlertService] = None,
    canonical_alert_bridge: Optional[CanonicalAlertBridge] = None,
    event_bus: Optional[Any] = None,
):
```

The launcher continues to use all defaults:
```python
supervisor = CSSRuntimeSupervisor()   # state_dir="runtime/supervisor" — unchanged
```

---

## 6. Configuration Changes

**No configuration files change.** `LauncherConfig.SUPERVISOR_STATE_FILE`
remains:
```python
os.path.join(RUNTIME_DIR, "supervisor", "css_runtime_supervisor_state.json")
```

This points to the canonical path, which is correct and unchanged.

No `.env` changes. No `LauncherConfig` changes. No environment variables
added or modified.

---

## 7. Runtime Artifact Path Changes

| Artifact | Before | After |
|---|---|---|
| Canonical supervisor state (launcher) | `runtime/supervisor/css_runtime_supervisor_state.json` | **Unchanged** |
| Dashboard supervisor state | `runtime/supervisor/css_runtime_supervisor_state.json` (conflict!) | `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` (new, isolated) |

The secondary artifact path is new. On first dashboard startup after the
change, `_ensure_state_dir()` creates `runtime/supervisor/dashboard/`
automatically — no manual directory creation required.

---

## 8. Consumer and Reader Impact

### Mission Control readers — NO CHANGE

All Mission Control readers default to the canonical path:

| Reader | Default `supervisor_state_path` | After Phase 171B |
|---|---|---|
| `RuntimeArtifactReader` | `"runtime/supervisor/css_runtime_supervisor_state.json"` | **Unchanged** |
| `RuntimeSnapshotProvider` | `"runtime/supervisor/css_runtime_supervisor_state.json"` | **Unchanged** |
| `RuntimeSourceResolver` | `"runtime/supervisor/css_runtime_supervisor_state.json"` | **Unchanged** |
| `RuntimeArtifactFreshnessManager` | `root.parent / "runtime/supervisor/css_runtime_supervisor_state.json"` | **Unchanged** |
| Mobile launcher (3 routes) | `LauncherConfig.SUPERVISOR_STATE_FILE` | **Unchanged** |

After Phase 171B, all readers see only the launcher's canonical writes. The
dashboard no longer overwrites them.

### Dashboard launcher behavior — NO CHANGE

The launcher's `CSSRuntimeSupervisor` instance is completely unchanged. Its
`state_dir`, heartbeat cadence, restart logic, alert emission, and all method
calls are identical to current HEAD.

### Broker safety — NO CHANGE

Neither `CSSRuntimeSupervisor` nor `RuntimeSupervisor` participate in broker
execution. The `state_dir` change has no pathway to any broker adapter,
OANDA firewall, Coinbase integration, or IBKR stub.

---

## 9. Runtime Behavior: Before vs. After

### Startup sequence

| Event | Before (current) | After (Phase 171B) |
|---|---|---|
| Launcher creates Instance A, calls `start()` | Writes `runtime/supervisor/css_runtime_supervisor_state.json` with `supervisor_id=UUID-A` | **Identical** |
| Dashboard process starts, creates Instance B, calls `start()` | **Overwrites canonical file with `supervisor_id=UUID-B`** | Writes `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` — canonical file **untouched** |
| Mission Control reads canonical file | May see UUID-B (dashboard's ID) | Always sees UUID-A (launcher's ID) |

### Heartbeat steady state

| Event | Before (current) | After (Phase 171B) |
|---|---|---|
| Launcher heartbeat (every 10s) | Writes canonical file — may be immediately overwritten by dashboard | Writes canonical file — **never overwritten** by dashboard |
| Dashboard heartbeat (every ~60 cycles) | **Overwrites canonical file**, erasing launcher's `failure_count`, `restart_count`, `last_heartbeat_at` | Writes to subordinate file only — canonical file unaffected |
| FreshnessManager reads canonical file mtime | Updated by both processes; staleness clock reset by either | Updated only by launcher writes (every 10s) — deterministic |

### Race condition

| Scenario | Before (current) | After (Phase 171B) |
|---|---|---|
| Concurrent write | Non-atomic truncate-then-write from two processes on the same file — can produce truncated JSON | Two processes write to **different files** — no concurrent access to canonical file |
| Mission Control shows UNAVAILABLE | Can occur during overlapping writes (truncated JSON → parse failure) | Cannot occur from race — canonical file is single-writer |
| supervisor_id instability | Alternates between UUID-A and UUID-B on consecutive reads | Always UUID-A (launcher's identity) |
| restart_count accuracy | Erased to 0 on every dashboard heartbeat | Preserved; only launcher writes update it |

---

## 10. Regression Test Plan

### Unit Tests (new file: `tests/test_phase171b_supervisor_path_isolation.py`)

| Test ID | Test Description | Pass Criterion |
|---|---|---|
| U-01 | Launcher instantiation uses default `state_dir` | `CSSRuntimeSupervisor().state_dir == "runtime/supervisor"` |
| U-02 | Dashboard instantiation uses subordinate `state_dir` | `CSSRuntimeSupervisor(state_dir="runtime/supervisor/dashboard").state_dir == "runtime/supervisor/dashboard"` |
| U-03 | Launcher and dashboard state files do not share the same path | `launcher_state_file != dashboard_state_file` |
| U-04 | Launcher `start()` writes only to canonical path | `runtime/supervisor/css_runtime_supervisor_state.json` exists; `runtime/supervisor/dashboard/` does not |
| U-05 | Dashboard `start()` writes only to subordinate path | `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` exists; canonical file contains launcher's UUID only |
| U-06 | Dashboard heartbeat does not update canonical file mtime | After dashboard `heartbeat()`, canonical file mtime is unchanged |
| U-07 | Canonical file `supervisor_id` is stable across launcher+dashboard heartbeat sequence | `supervisor_id` in canonical file is always UUID-A |
| U-08 | `record_restart()` on dashboard instance writes to subordinate path only | Canonical file `restart_count` is unchanged after dashboard `record_restart()` |
| U-09 | `record_failure()` on dashboard instance writes to subordinate path only | Canonical file `failure_count` is unchanged |
| U-10 | `_ensure_state_dir()` creates `runtime/supervisor/dashboard/` automatically | Directory exists after first dashboard supervisor operation |
| U-11 | `record_restart()` called with no arguments succeeds (Change 2) | No TypeError; `restart_count` increments correctly |
| U-12 | FreshnessManager canonical path is unchanged | `FreshnessManager().paths["supervisor_state"]` resolves to canonical path |
| U-13 | `RuntimeArtifactReader` default `supervisor_state_path` is unchanged | Default constructor value unchanged |
| U-14 | `LauncherConfig.SUPERVISOR_STATE_FILE` is unchanged | Path value identical to pre-171B |

### Integration Tests

| Test ID | Test Description | Pass Criterion |
|---|---|---|
| I-01 | Simulate concurrent launcher + dashboard writes; confirm canonical file is not truncated | After N write cycles, canonical JSON is valid and parseable |
| I-02 | `RuntimeSnapshotProvider.get_snapshot()` with canonical file written only by launcher | Returns GREEN freshness; `supervisor_id` matches launcher's UUID |
| I-03 | `RuntimeArtifactFreshnessManager.evaluate()` with canonical file at 10s mtime age | Returns `freshness_status: GREEN` for `supervisor_state` (threshold 120s) |
| I-04 | Dashboard secondary file is a valid JSON artifact independently | `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` parses correctly |
| I-05 | Mobile launcher routes read canonical file correctly via `LauncherConfig` | Snapshot provider receives launcher's `supervisor_id` |

### Runtime Validation (attended, short-duration)

| Test ID | Test Description | Pass Criterion |
|---|---|---|
| R-01 | Start launcher; confirm `runtime/supervisor/css_runtime_supervisor_state.json` is created with launcher UUID | UUID is stable; file exists within 1 second of launcher start |
| R-02 | Start dashboard (child process); confirm canonical file UUID **does not change** | Same UUID as R-01 after dashboard `start()` |
| R-03 | Wait 10 seconds; confirm canonical file mtime advances (launcher heartbeat) | `stat().st_mtime` increases every 10 seconds |
| R-04 | Confirm `runtime/supervisor/dashboard/css_runtime_supervisor_state.json` is created | File exists after first dashboard cycle |
| R-05 | Read canonical file after 5 minutes of operation | `supervisor_id` is still launcher's UUID; `restart_count` reflects only launcher restarts |
| R-06 | Read Mission Control snapshot during runtime | `source` is `RUNTIME_ARTIFACT` or `RUNTIME_REGISTRY`; `freshness_status` is `GREEN` |
| R-07 | Kill dashboard subprocess; confirm launcher detects failure and restart logic fires | Launcher's canonical file shows `failure_count=1`, `status=DEGRADED` |
| R-08 | Dashboard restarts; confirm canonical file shows `restart_count=1` | `restart_count` increments from launcher restart logic, not from dashboard |

### Long-Duration Validation (unattended, 60+ minutes)

| Test ID | Test Description | Pass Criterion |
|---|---|---|
| L-01 | 60-minute run with continuous mode enabled | Canonical `supervisor_id` never changes during run |
| L-02 | 60-minute run; FreshnessManager evaluated every 2 minutes | `supervisor_state` freshness never goes STALE (should be FRESH throughout, launcher writes every 10s) |
| L-03 | 60-minute run; Mission Control snapshot checked at t=0, t=30min, t=60min | `restart_count` in canonical file is 0 (no crashes); dashboard UUID visible only in subordinate file |
| L-04 | Simulate dashboard crash at t=30min; confirm launcher restarts it and canonical file reflects restart | `restart_count=1` in canonical file; `supervisor_id` unchanged (still launcher's UUID) |

### Mission Control Validation

| Test ID | Test Description | Pass Criterion |
|---|---|---|
| MC-01 | `RuntimeArtifactReader.read_candidate()` returns `critical_available=True` | Supervisor, session, account all readable |
| MC-02 | `RuntimeSourceResolver.resolve()` selects `RUNTIME_ARTIFACT` source | `selected.source_type == SOURCE_RUNTIME_ARTIFACT` |
| MC-03 | `RuntimeSnapshotProvider.get_state_payload()` contains `advisory_only: True` | Advisory governance fields intact |
| MC-04 | No `runtime_artifacts_not_fresh` failure in RuntimeArtifactReader | Freshness check passes with launcher-only writes |
| MC-05 | `supervisor_id` in Mission Control snapshot is stable across dashboard heartbeat cycles | UUID does not change mid-session |

---

## 11. Pre-existing Defect Inventory (Phase 171B Secondary Items)

The following defect was discovered during evidence collection and is bundled
into the Phase 171B commit. It is not introduced by the primary change.

| Defect ID | Location | Description | Severity | Plan |
|---|---|---|---|---|
| D-01 | `scripts/css_live_dashboard.py:3845` | `css_supervisor.record_restart("RESUME_PREVIOUS_SESSION")` passes an invalid positional argument to a method that takes only `self`. Raises `TypeError` when `CSS_RESUME_SESSION=true` and saved session state exists, crashing the dashboard startup at module level. | HIGH (silent in normal operation; crashes on session resume) | Remove the invalid positional argument (Change 2 in this plan) |

---

## 12. Risk Assessment

| Change | Risk Classification | Rationale |
|---|---|---|
| Change 1: `state_dir="runtime/supervisor/dashboard"` in dashboard constructor | **LOW** | Single keyword argument to an existing parameter with a well-tested default. Zero impact on all consumers (all hardcode or default to canonical path). The directory is created automatically. No interface change anywhere. |
| Change 2: Remove `"RESUME_PREVIOUS_SESSION"` positional arg from `record_restart()` call | **LOW** | The argument was never valid. Removing it restores correct behavior. Affected only when `CSS_RESUME_SESSION=true`, which is a deliberate operator action. Normal operation is unaffected. |
| New test file | **LOW** | Static inspection and path assertion tests. No side effects. |
| No change to Mission Control consumers | **ZERO** | No files modified. |
| No change to broker files | **ZERO** | No files modified. |
| No change to risk/strategy files | **ZERO** | No files modified. |

**Overall implementation risk: LOW**

The narrowest possible intervention surface. The `CSSRuntimeSupervisor`
constructor was specifically designed to accept an explicit `state_dir`
parameter for exactly this purpose — the current codebase uses it in every
test (`state_dir=temp_dir`). The change to production code adds one keyword
argument to an existing, tested constructor call.

---

## 13. Implementation Complexity and Estimated Time

| Item | Effort |
|---|---|
| Change 1 (dashboard constructor) | 2 minutes — one `str_replace` |
| Change 2 (remove invalid arg) | 2 minutes — one `str_replace` |
| New test file (14 unit + 5 integration tests) | 45–60 minutes |
| Manual runtime validation (R-01 through R-08) | 20–30 minutes (attended) |
| Compile checks | 2 minutes |
| Commit | 2 minutes |
| **Total** | **~75–100 minutes** |

---

## 14. Rollback Plan

If regression is observed after Phase 171B is merged:

1. The canonical path is unchanged — Mission Control is unaffected by any
   rollback.
2. The secondary artifact path (`runtime/supervisor/dashboard/`) is new and
   unused by any consumer — removing it is consequence-free.
3. Full rollback is `git revert <171B_commit_hash>` — one commit, two changed
   lines in one file, no side effects on any runtime artifact consumers.

---

## 15. Commit Specification

**Target branch:** `css-unified-consolidation-2026-07-13`  

**Commit message:**
```
Phase 171B: isolate dashboard CSSRuntimeSupervisor to subordinate state_dir

Root cause (Phase 171A): launcher and dashboard both instantiate
CSSRuntimeSupervisor with default state_dir="runtime/supervisor", causing
non-atomic concurrent writes to the same canonical artifact. This overwrites
the launcher's supervisor_id, restart_count, and failure_count on every
dashboard heartbeat cycle.

Fix: pass state_dir="runtime/supervisor/dashboard" to the dashboard's
CSSRuntimeSupervisor constructor (scripts/css_live_dashboard.py line 900).
The canonical artifact runtime/supervisor/css_runtime_supervisor_state.json
is now exclusively written by the launcher process.

Bundled fix: remove spurious positional argument from record_restart() call
at line 3845 — pre-existing TypeError raised on CSS_RESUME_SESSION=true.

No changes to: launcher, Mission Control readers, freshness manager,
mobile launcher, broker code, risk/strategy logic.

Adds: tests/test_phase171b_supervisor_path_isolation.py
```

**Files committed:**
1. `scripts/css_live_dashboard.py` (2 line changes)
2. `tests/test_phase171b_supervisor_path_isolation.py` (new)
3. `docs/governance/PHASE_171A_RUNTIME_PUBLICATION_AUDIT.md` (new, from 171A)
4. `docs/governance/PHASE_171B_IMPLEMENTATION_PLAN.md` (this document)

---

## 16. Open Questions (Carried from Phase 171A)

| OQ | Status |
|---|---|
| OQ-1: Does Mission Control cache `supervisor_id` across requests? | Not observed. No action needed for 171B. |
| OQ-2: Are there CI fixtures that write to `runtime/supervisor/`? | Not confirmed. Recommend verifying in Phase 171C or CI review. |
| OQ-3: Is `record_canonical_decision()` ever called in the launcher? | Not called in launcher (confirmed). No action. |
| OQ-4: Should the subordinate dashboard artifact be exposed via a Mission Control diagnostic endpoint? | Out of scope for 171B. Phase 172 candidate. |

---

**STOP. Awaiting explicit approval before any production code modification.**

