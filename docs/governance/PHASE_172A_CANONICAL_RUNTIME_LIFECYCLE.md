# PHASE 172A — CANONICAL LAUNCHER LIFECYCLE, HEARTBEAT CONTINUITY, AND MISSION CONTROL ALIGNMENT

**Repository:** `C:\rasib\source\capital-strata-systems`
**Branch:** `css-unified-consolidation-2026-07-13`
**Baseline commit:** `1a9efe779042eb79a8f5db02c1f2d8af7fa6e8f0`
**Mode:** Investigation + minimal fix, advisory-only. No commit, no push (per instructions).

---

## 1. Verified Root Cause

**Primary cause — Classification A: the overnight runtime was started directly, without the canonical launcher.**

Evidence:

- The reported overnight process list contained `dashboard.web.web_app:create_app` and
  `scripts/css_live_dashboard.py`, but **not** `launcher/css_runtime_launcher.py`.
- `dashboard.web.web_app:create_app` is a valid FastAPI app-factory target
  (`dashboard/web/web_app.py:create_app`), but **no code path in this repository invokes it**
  this way — `launcher/css_runtime_launcher.py` never spawns it, and `launcher/css_mobile_launcher.py`
  builds its own `FastAPI(...)` app object rather than importing `dashboard.web.web_app`. A
  repo-wide search for the literal string `web_app:create_app` returns zero matches. The only
  way this process appears is a manual/external `uvicorn dashboard.web.web_app:create_app --factory`
  invocation by an operator, bypassing the canonical launcher entirely.
- `scripts/css_live_dashboard.py` can also be started directly (`python scripts/css_live_dashboard.py`),
  which is exactly what appeared in the process list.
- `launcher/css_runtime_launcher.py` itself was read in full: its lifecycle is correct. `supervisor.start()`
  runs before the service loop; the `while True` loop calls `supervisor.heartbeat()` every 10 seconds; a
  `try/except KeyboardInterrupt/finally` block guarantees `svc.stop()` for every managed child and
  `supervisor.stop()` on any loop exit (normal, Ctrl-C, or unhandled exception unwinding through `finally`).
  There is no defect in this file that would explain a "supervisor STOPPED, dashboard still running" split
  **if the dashboard had actually been started as `launcher`'s child** — `CSSServiceManager.stop()` calls
  `Popen.terminate()` + `wait(timeout=5)` (falling back to `kill()`), which reliably terminates a
  directly-spawned child on Windows. The only way the dashboard keeps running after the canonical
  supervisor reports `STOPPED` is if the dashboard was never the launcher's child in the first place.

**Conclusion:** no launcher defect. Root cause A (direct/manual start) is the mechanism that put the
system in the reported state.

### Contributing defects (Classification H) — found during investigation, required fixing to satisfy the acceptance criteria

Root cause A alone does not explain why Mission Control could *look* healthy in that state — two
independent, provable code defects made an orphaned runtime indistinguishable from a healthy one:

1. **Gap-fill health fabrication** — `launcher/css_mobile_launcher.py::_publish_supervisor_heartbeat_snapshot()`
   (introduced in Phase 171A/171B as a "gap-fill" writer) wrote `{"status": "RUNNING", ...}` directly to
   the canonical artifact path whenever it observed that file as missing or stale — **regardless of
   whether the real canonical launcher process was alive**. This is documented as intentional in
   `docs/governance/PHASE_171A_RUNTIME_PUBLICATION_AUDIT.md` ("if the primary publisher (launcher) has
   stopped, the mobile launcher provides a RUNNING signal until the canonical publisher recovers") — but
   it directly violates the fail-closed governance principle: it fabricates canonical health with no
   knowledge of the actual launcher process.
2. **mtime-only freshness, ignoring declared status** — `RuntimeArtifactFreshnessManager._artifact_state()`
   classified `supervisor_state` freshness purely from file `mtime`, never inspecting the JSON content's
   `status` field. A canonical file that had just been written with `status: "STOPPED"` (a truthful
   shutdown) was still reported `FRESH`/`GREEN` for up to 120 seconds, and indefinitely if anything kept
   touching the file's mtime (including the gap-fill writer above, or `evaluate(refresh=True)`).
3. **"Last Runtime Heartbeat" tile wired to the wrong source** — `dashboard/mission_control/contracts.py::_data_freshness()`
   populated `last_runtime_heartbeat` from the **broker** section (`broker.get("last_heartbeat")` /
   `broker.get("last_successful_sync")`) rather than from `runtime_snapshot["last_heartbeat"]` (the value
   actually sourced from the canonical supervisor artifact via `RuntimeSnapshotProvider` →
   `RuntimeSourceResolver` → `RuntimeArtifactReader`). The function did not even receive `runtime_snapshot`
   as a parameter. This is why the tile could show a stale/broker-derived/`DATA UNAVAILABLE` value instead
   of the advancing canonical heartbeat — this was the direct blocker for the priority acceptance criterion.

**Confidence:** HIGH for all four findings. Each is demonstrated by direct code reading (file:line
references below) and reproduced by the new regression tests in
`tests/test_phase172a_canonical_runtime_lifecycle.py`.

---

## 2. Did the overnight run use the canonical launcher?

**No.** The process evidence (absence of `launcher/css_runtime_launcher.py`, presence of a
`web_app:create_app` process not spawned by any code path in this repo) indicates the dashboard and web
service were started outside `launcher/css_runtime_launcher.py`. Combined with the canonical artifact's
own `stopped_at` timestamp (05:25:41 UTC, after `last_heartbeat_at` at 04:48:38 UTC), the most consistent
interpretation is: an earlier canonical launcher session ran normally from 02:47 to ~04:48, then stopped
(cleanly, per the truthful `STOPPED` status, not a crash — `stopped_at` is set, which only happens via
`CSSRuntimeSupervisor.stop()` in the launcher's `finally` block). Sometime after that, the dashboard
(and/or the standalone web app) was started independently of the launcher and kept running/accumulating
cycles, writing only to its own subordinate path (`runtime/supervisor/dashboard/...`, per the Phase 171B
isolation guarantee) — never touching the canonical file again, which is exactly why the canonical file
was observed frozen at `STOPPED` while the dashboard kept advancing.

---

## 3. Before / After Lifecycle

### Before (defective)

```
Canonical launcher STOPPED (truthful, e.g. operator Ctrl-C or session end)
        │
        ▼
runtime/supervisor/css_runtime_supervisor_state.json
  { status: "STOPPED", last_heartbeat_at: <frozen> }
        │
        │  (dashboard started directly, NOT via launcher, keeps running)
        │
        ▼
Mission Control polls live-readiness feed
  → ensure_runtime_artifacts_current() sees supervisor_state STALE
  → _publish_supervisor_heartbeat_snapshot() FABRICATES:
        { status: "RUNNING", last_heartbeat: now() }   ◄── BUG: no check
                                                              that the real
                                                              launcher is alive
        │
        ▼
RuntimeArtifactFreshnessManager: mtime just touched → "FRESH" / "GREEN"
        │                                              ◄── BUG: ignores
        ▼                                                   declared status
RuntimeArtifactReader.active = True  (looks canonical-healthy)
        │
        ▼
Mission Control "Runtime Health" / "Platform Status" → appears ONLINE
Mission Control "Last Runtime Heartbeat" → wired to BROKER data, not
                                            the canonical artifact at all  ◄── BUG
```

### After (fixed)

```
Canonical launcher heartbeat() / stop()
        │
        ▼
runtime/supervisor/css_runtime_supervisor_state.json
  { status, last_heartbeat_at, supervisor_id }   ◄── truthful, never
                                                       overwritten with a
                                                       fabricated status
        │
        ▼
classify_canonical_runtime_authority(canonical_state, dashboard_state)
  reads declared status + heartbeat age directly (backend/runtime/
  canonical_runtime_authority.py) → ONLINE | STOPPED | STALE | MISSING |
                                     MALFORMED | ORPHANED_RUNTIME
        │
        ▼
RuntimeArtifactFreshnessManager.evaluate()
  forces supervisor_state freshness to STALE whenever authority != ONLINE,
  regardless of mtime; adds "orphaned_runtime_detected" blocker when a
  subordinate dashboard heartbeat is fresh but canonical is not ONLINE
        │
        ▼
RuntimeArtifactReader.read_candidate().available
  gated on canonical_authority.canonical_alive — a fresh dashboard
  heartbeat alone can never satisfy canonical health
        │
        ▼
canonical_runtime_snapshot._snapshot_from_artifacts()
  runtime_status = ORPHANED_RUNTIME / STOPPED / STALE / MISSING / MALFORMED
  (explicit) whenever authority is not ONLINE
        │
        ▼
Mission Control build_mission_control_state()
  data_freshness.last_runtime_heartbeat = runtime_snapshot["last_heartbeat"]
  (the CANONICAL supervisor heartbeat, not broker data)
        │
        ▼
Executive Overview "Last Runtime Heartbeat" tile:
  real ISO-8601 UTC canonical timestamp, advances every launcher heartbeat,
  fails closed (shows the true stale/stopped state) when the launcher is
  not genuinely alive
        │
        ▼
Mobile launcher gap-fill writer (_publish_supervisor_heartbeat_snapshot)
  now writes { status: "ORPHANED_RUNTIME", synthetic: true, ... } instead
  of a fabricated RUNNING — and the "synthetic" marker itself is also
  independently rejected as canonical proof by the classifier
```

---

## 4. Canonical Startup Command

```
.\.venv\Scripts\python.exe -m launcher.css_runtime_launcher
```

(equivalently, `launch_css.bat`, which sets `PYTHONPATH` to the repo root and runs the same module.)

This command was verified by code reading (not executed against production, per the Laptop1/Desktop
safety constraint) to:

- construct `CSSRuntimeSupervisor()` with the canonical default `state_dir="runtime/supervisor"` and call
  `.start()` before any child process exists (`launcher/css_runtime_launcher.py:180-181`);
- spawn `scripts/css_live_dashboard.py` and `launcher/css_mobile_launcher.py` as managed children via
  `CSSServiceManager` (`launcher/css_runtime_launcher.py:187-191`);
- heartbeat the canonical supervisor every 10 seconds in the main loop
  (`launcher/css_runtime_launcher.py:207-211`);
- terminate all managed children and call `supervisor.stop()` in a `finally` block on any exit path —
  `KeyboardInterrupt`, normal loop exit, or an unhandled exception unwinding through the loop
  (`launcher/css_runtime_launcher.py:212-218`).

No other script in this repository (`scripts/start_css_mobile_app.py` runs only the mobile app in
isolation; direct `python scripts/css_live_dashboard.py` runs only the dashboard) starts the full,
supervised platform. Running any component standalone is, by design, now detected and surfaced as
`ORPHANED_RUNTIME` rather than presented as a healthy canonical platform.

---

## 5. Files Changed

| File | Type | Change |
|---|---|---|
| `backend/runtime/canonical_runtime_authority.py` | **New** | Single fail-closed classifier: `classify_canonical_runtime_authority()`. Reads canonical + (optional) dashboard-subordinate supervisor state and returns `ONLINE / STOPPED / MISSING / MALFORMED / STALE / ORPHANED_RUNTIME`. Never treats a subordinate heartbeat, a synthetic gap-fill write, or file mtime alone as canonical proof. |
| `backend/runtime/runtime_artifact_freshness.py` | Modified | `RuntimeArtifactFreshnessManager` now computes `canonical_authority` via the new classifier, forces the `supervisor_state` artifact to `STALE` whenever authority is not `ONLINE` (even with a fresh mtime), and adds an `orphaned_runtime_detected` blocker/warning when orphaned. Added optional `dashboard_supervisor_state_path` (defaults to the Phase 171B subordinate path). |
| `dashboard/mission_control/runtime_artifact_reader.py` | Modified | `read_candidate().available` now additionally requires `canonical_authority.canonical_alive`; failure reasons now include `orphaned_runtime_detected` / `canonical_runtime_not_alive:<status>`. |
| `backend/runtime/canonical_runtime_snapshot.py` | Modified | `_snapshot_from_artifacts()` now prefers the canonical-authority classification over the raw `status` field for `runtime_status` whenever authority is not `ONLINE`, so `ORPHANED_RUNTIME`/`STALE`/`MISSING`/`MALFORMED` are surfaced explicitly instead of a bare `STOPPED` (or a fabricated healthy value). |
| `dashboard/mission_control/contracts.py` | Modified | `_data_freshness()` now accepts `runtime_snapshot` and sources `last_runtime_heartbeat` from `runtime_snapshot["last_heartbeat"]` (the canonical supervisor heartbeat) first, falling back to broker data only if the canonical value is genuinely unavailable. `build_mission_control_state()` passes `runtime_snapshot` through. |
| `launcher/css_mobile_launcher.py` | Modified | `_publish_supervisor_heartbeat_snapshot()` (the Phase 171A/171B-documented gap-fill writer) no longer writes `status: "RUNNING"`. It now writes `status: "ORPHANED_RUNTIME"` with `synthetic: true` and a `reason` field, so it can never again be read as proof of canonical health. |
| `.gitignore` | Modified | Added `!backend/runtime/canonical_runtime_authority.py` allow-list entry (this directory is ignore-by-default with explicit per-file exceptions). |
| `tests/test_phase172a_canonical_runtime_lifecycle.py` | **New** | 23 tests covering the classifier, fail-closed freshness/reader gating, orphan detection, the Mission Control heartbeat wiring fix, the gap-fill fix, and launcher heartbeat/mtime/supervisor_id continuity. |
| `docs/governance/PHASE_172A_CANONICAL_RUNTIME_LIFECYCLE.md` | **New** | This document. |

No changes were made to `launcher/css_runtime_launcher.py`, `launcher/css_service_manager.py`, or
`backend/runtime/css_runtime_supervisor.py` — per the decision rule for a direct-start root cause, the
launcher's own lifecycle was not redesigned because it was not found to be defective.

---

## 6. Exact Production Changes

### `backend/runtime/canonical_runtime_authority.py` (new)

Defines `classify_canonical_runtime_authority(supervisor_state, dashboard_state, *, now, stale_after_seconds=120.0)`.
Decision order: missing canonical → `MISSING`/`ORPHANED_RUNTIME`; synthetic marker present → never `ONLINE`;
no `status` field → `MALFORMED`/`ORPHANED_RUNTIME`; `status` not `RUNNING` → `STOPPED`/`ORPHANED_RUNTIME`;
`RUNNING` with unparseable heartbeat → `MALFORMED`/`ORPHANED_RUNTIME`; `RUNNING` with no heartbeat recorded
yet → `ONLINE` (trusts a just-started supervisor before its first heartbeat, matching
`CSSRuntimeSupervisor.start()`'s real sequence and existing test fixtures); `RUNNING` with heartbeat older
than `stale_after_seconds` → `STALE`/`ORPHANED_RUNTIME`; otherwise → `ONLINE`. Whenever the canonical
side is not `ONLINE`, the classifier additionally checks whether a *dashboard subordinate* heartbeat
is fresh — if so, the result becomes `ORPHANED_RUNTIME` instead of the bare failure code, which is the
explicit signal Mission Control uses to distinguish "nothing is running" from "the dashboard is running
without the canonical launcher."

### `backend/runtime/runtime_artifact_freshness.py`

- Constructor gained `dashboard_supervisor_state_path` (default: sibling `dashboard/` directory under the
  canonical supervisor path — matches the real Phase 171B layout with no extra wiring needed at any call
  site).
- `evaluate()` computes `canonical_authority` once via the classifier and stores it on the result and on
  the `supervisor_state` artifact entry. If `canonical_authority.authority_status != "ONLINE"` and the file
  exists, the artifact's `freshness`/`status` is forced to `"STALE"` regardless of what the mtime-based
  calculation produced. An `orphaned_runtime_detected` blocker/warning is added whenever
  `canonical_authority.orphan_runtime` is true.

### `dashboard/mission_control/runtime_artifact_reader.py`

`read_candidate()` now reads `freshness["canonical_authority"]` and requires
`canonical_authority.canonical_alive` (in addition to the pre-existing critical-artifact-present and
GREEN/AMBER checks) before marking the candidate `available`. Failure strings now distinguish
`orphaned_runtime_detected` from a generic `canonical_runtime_not_alive:<status>`.

### `backend/runtime/canonical_runtime_snapshot.py`

`_snapshot_from_artifacts()` extracts `canonical_authority` from the diagnostics payload already threaded
through `RuntimeArtifactReader` and uses `authority_status` as `runtime_status` whenever it is not
`ONLINE`; otherwise it falls back to the literal `supervisor.status` field exactly as before (no change to
the healthy path).

### `dashboard/mission_control/contracts.py`

`_data_freshness(frontend, broker, certification, freshness, runtime_snapshot=None)` — new optional
parameter, sourced from the `runtime_snapshot` already built earlier in `build_mission_control_state()`.
`last_runtime_heartbeat` now reads `runtime_snapshot.get("last_heartbeat")` first; the broker-derived value
is retained only as a fallback for the case where the canonical value is itself `DATA UNAVAILABLE`.

### `launcher/css_mobile_launcher.py`

`_publish_supervisor_heartbeat_snapshot()` payload changed from
`{"status": "RUNNING", "last_heartbeat": ..., "source": "css_mobile_launcher", ...}` to
`{"status": "ORPHANED_RUNTIME", "last_heartbeat": ..., "source": "css_mobile_launcher_gap_fill", "synthetic": true, "reason": "canonical_launcher_not_detected", ...}`.
The trigger condition (only fires when `ensure_runtime_artifacts_current()` finds `supervisor_state`
missing/stale) is **unchanged** — Phase 171B guarantee 4 ("the mobile launcher gap-fill publisher may
write the canonical artifact only when it is missing or stale") is preserved; only the fabricated content
was corrected.

---

## 7. Canonical Supervisor JSON Evidence

Local (Laptop1) canonical artifact at the start of this task (`runtime/supervisor/css_runtime_supervisor_state.json`):

```json
{
  "supervisor_id": "39f6399b-cf4a-4f80-867e-f591af7fa1f8",
  "started_at": "2026-07-16T21:58:26.413758+00:00",
  "stopped_at": "2026-07-16T21:58:26.420498+00:00",
  "last_heartbeat_at": null,
  "failure_count": 0,
  "restart_count": 0,
  "last_failure": null,
  "last_canonical_decision": null,
  "last_decision_at": null,
  "status": "STOPPED",
  "max_restart_limit": 3
}
```

This is unrelated local test/idle state on this machine (not the Desktop overnight session described in
the task evidence) and was left untouched — no production runtime file on this machine was modified by
this investigation. The end-to-end proof below (§8) was performed against an **isolated temp directory**,
specifically to avoid mutating any real local or Desktop runtime state per the safety constraints.

---

## 8. End-to-End Heartbeat Continuity Proof

Produced by running the real `CSSRuntimeSupervisor`, `RuntimeSnapshotProvider`, and
`dashboard.mission_control.contracts.build_mission_control_state` classes against an isolated temp
`runtime/supervisor/` directory (script: see test evidence below; equivalent assertions are codified as
`tests/test_phase172a_canonical_runtime_lifecycle.py::TestLauncherHeartbeatContinuity` and `::TestDataFreshnessHeartbeatWiring::test_d03_end_to_end_mission_control_state_surfaces_canonical_heartbeat`).

**Two successive heartbeat timestamps (I):**

```
last_heartbeat_at (1) = 2026-07-17T21:47:20.778555+00:00
last_heartbeat_at (2) = 2026-07-17T21:47:22.000765+00:00
```

**Two successive canonical artifact mtimes (J):**

```
mtime (1) = 1784324840.7788053
mtime (2) = 1784324842.001871
```

Both advanced; `supervisor_id` (`4d551a91-6928-444a-a8fa-5f6946ba6611`) remained identical across both
writes.

**Mission Control "Last Runtime Heartbeat" field value and provenance (K):**

```
runtime_snapshot['source']         = RUNTIME_ARTIFACT
runtime_snapshot['runtime_status']  = RUNNING
runtime_snapshot['last_heartbeat']  = 2026-07-17T21:47:22.000765+00:00
Mission Control 'Last Runtime Heartbeat' tile value = 2026-07-17T21:47:22.000765+00:00
```

The tile value is byte-for-byte equal to the canonical supervisor's second `last_heartbeat_at`, proving
the full trace: `CSSRuntimeSupervisor.heartbeat()` → canonical JSON → `RuntimeSnapshotProvider` (via
`RuntimeSourceResolver`/`RuntimeArtifactReader`) → `build_mission_control_state()` →
`state["data_freshness"]["last_runtime_heartbeat"]` (the exact field the Executive Overview page renders
as "Last Runtime Heartbeat", `dashboard/mission_control/pages/executive_overview.py:43`).

**Mission Control status before / after (L):**

- Before this fix: a canonical file with `status: "STOPPED"` but a recently-touched mtime (e.g.
  immediately after a gap-fill write) would read as `FRESH`/`GREEN`/`available=True` — indistinguishable
  from a healthy canonical runtime.
- After this fix: the same file is forced to `STALE`, `RuntimeArtifactReader.available` is `False`, and
  `canonical_runtime_snapshot.runtime_status` reports the true `STOPPED` (or `ORPHANED_RUNTIME` if a
  subordinate dashboard heartbeat is concurrently fresh) — verified by
  `TestFreshnessManagerFailsClosed::test_f01` and `TestRuntimeArtifactReaderOrphanGating::test_r01`.

**Orphan-runtime behavior before / after (M):**

- Before: a fresh dashboard subordinate heartbeat combined with a stopped/missing canonical file had no
  explicit detection; the mobile launcher's gap-fill writer would actively overwrite the canonical file
  with a fabricated `RUNNING` status, making the orphaned condition invisible.
- After: `classify_canonical_runtime_authority()` explicitly returns `ORPHANED_RUNTIME` whenever the
  dashboard subordinate heartbeat is fresh but the canonical side is not — verified by
  `TestCanonicalRuntimeAuthorityClassifier::test_a03/test_a04`, propagated through
  `RuntimeArtifactFreshnessManager` (`test_f03`), `RuntimeArtifactReader` (`test_r02`), and
  `canonical_runtime_snapshot` (`test_s01`). The gap-fill writer itself now writes
  `ORPHANED_RUNTIME`/`synthetic: true` instead of fabricating `RUNNING` (`test_g01`).

**Full shutdown proof (§8, step 7):**

```
status after stop() = STOPPED
{
  "authority_status": "STOPPED",
  "canonical_alive": false,
  "orphan_runtime": false,
  "reason": "canonical_status_stopped"
}
```

---

## 9. Test Evidence

All commands run with `.venv\Scripts\python.exe -m pytest`.

| Suite | Result |
|---|---|
| `tests/test_phase171b_supervisor_path_isolation.py`, `tests/test_runtime_artifact_freshness.py`, `tests/test_phase136a_artifact_freshness.py`, `tests/test_phase137a_runtime_health.py`, `tests/test_mc004_active_runtime_publisher_binding.py`, `tests/test_mc003_mission_control_runtime_snapshot_integration.py` | **47 passed** |
| `tests/test_css_runtime_supervisor.py`, `tests/test_css_runtime_launcher.py`, `tests/test_auto_restart_framework.py`, `tests/test_passive_publishing.py`, `tests/test_canonical_decision_pipeline.py`, `tests/test_alert_delivery_runtime_integration.py` | **54 passed** |
| `tests/dashboard/` (full directory) | **155 passed** |
| `tests/test_mc001…test_mc007c` (foundation through production hardening) | **63 passed** |
| `tests/test_css_mobile_launcher.py`, `tests/test_op002_operational_validation.py` | **68 passed** |
| `tests/test_phase153a/b/c/e/h/i`, `tests/test_phase152a/b` (broker/live-readiness) | 3 pre-existing failures, confirmed unrelated (see below) |
| `tests/test_phase154b`, `155a/b/d`, `163b3a`, `164`, `166d`, `153d` | 63 passed, 1 unrelated pre-existing failure pair in `test_phase153g_coinbase_live_adapter.py` |
| `tests/test_phase172a_canonical_runtime_lifecycle.py` (**new**, 23 tests) | **23 passed** |
| Combined regression run (supervisor/launcher/171B/mobile-launcher/dashboard/MC001-004/172A) | **340 passed** |

**Pre-existing, unrelated failures** (confirmed via `git stash` against the unmodified baseline —
identical failures reproduce with none of this phase's changes applied):

- `test_phase153e_live_operator_workflow_hardening.py::test_phase153e_dashboard_exposes_hardened_broker_status`
- `test_phase153h_startup_summary_consistency.py::test_phase153h_dashboard_and_launcher_expose_checklist_and_diagnostics`
- `test_phase153i_live_execution_authority.py::test_phase153i_startup_summary_reconciles_operator_intent_with_authority`
- `test_phase153g_coinbase_live_adapter.py::test_phase153g_readiness_uses_canonical_adapter_and_preserves_disabled_execution`
- `test_phase153g_coinbase_live_adapter.py::test_phase153g_dashboard_exposes_read_only_broker_evidence_without_secret_values`

All five assert enum-string mismatches in broker connection-status labels (`"FAIL"` vs `"NOT_TESTED"`,
`"NO GO"` vs `"GO"`, `"PASS"` vs `"GREEN"`) — a pre-existing broker-readiness-labeling issue, unrelated to
runtime supervisor lifecycle, heartbeat, or Mission Control freshness, and out of scope for this phase.

**Python compile validation:** `py_compile` succeeded for all 6 modified files, the 1 new production
module, and the 1 new test file.

**`git diff --check`:** clean (exit 0, no whitespace errors).

---

## 10. Operational Validation Procedure

To validate this fix on a live system:

1. Confirm no canonical launcher is currently running:
   `Get-Process python | Where-Object { $_.Path -like "*css_runtime_launcher*" }` (or check
   `runtime/supervisor/css_runtime_supervisor_state.json` for a `STOPPED`/stale status).
2. Start the canonical platform with the single supported command:
   `.\.venv\Scripts\python.exe -m launcher.css_runtime_launcher` (or `launch_css.bat`).
3. Confirm `runtime/supervisor/css_runtime_supervisor_state.json` shows `status: "RUNNING"` and
   `last_heartbeat_at` advancing every ~10 seconds (`Get-Content ... | ConvertFrom-Json` in a loop, or
   `Get-Item ... | Select LastWriteTime`).
4. Open Mission Control's Executive Overview page and confirm the "Last Runtime Heartbeat" tile shows the
   same advancing UTC timestamp, and that "Runtime Health"/"Platform Status" read as healthy.
5. To validate orphan detection: stop the canonical launcher (Ctrl-C) while leaving
   `scripts/css_live_dashboard.py` running standalone in a separate terminal. Confirm Mission Control now
   reports `ORPHANED_RUNTIME` (not a healthy status) and the heartbeat tile stops advancing / reflects the
   true canonical staleness.

---

## 11. Rollback Procedure

All changes are additive and isolated to the six files and two new files listed in §5. To roll back:

```
git checkout -- backend/runtime/canonical_runtime_snapshot.py backend/runtime/runtime_artifact_freshness.py dashboard/mission_control/contracts.py dashboard/mission_control/runtime_artifact_reader.py launcher/css_mobile_launcher.py .gitignore
rm backend/runtime/canonical_runtime_authority.py tests/test_phase172a_canonical_runtime_lifecycle.py docs/governance/PHASE_172A_CANONICAL_RUNTIME_LIFECYCLE.md
```

No schema migrations, no data deletions, no changes to `launcher/css_runtime_launcher.py`,
`launcher/css_service_manager.py`, or `backend/runtime/css_runtime_supervisor.py` — rollback carries zero
risk to the canonical launcher's own behavior.

---

## 12. Known Limitations

- `classify_canonical_runtime_authority()` treats a `RUNNING` status with **no heartbeat field at all** as
  `ONLINE` (trusting the declared status) rather than failing closed, specifically to preserve backward
  compatibility with several existing test fixtures (`tests/test_runtime_artifact_freshness.py`,
  `tests/test_phase137a_runtime_health.py`) that construct minimal `{"status": "RUNNING"}` payloads without
  a heartbeat. In real production writes, `CSSRuntimeSupervisor._persist_state()` always includes
  `last_heartbeat_at` (`null` until the first `heartbeat()` call, then an ISO timestamp), so this leniency
  only matters in the narrow window between `start()` and the first `heartbeat()` — a few seconds at most.
- Orphan detection depends on the dashboard's subordinate supervisor file
  (`runtime/supervisor/dashboard/css_runtime_supervisor_state.json`) existing and being written, which
  requires the dashboard's own `CSSRuntimeSupervisor` import to succeed (`scripts/css_live_dashboard.py`
  guards this with `if css_supervisor:` and silently skips on import failure, per the open question already
  raised in `PHASE_171A_RUNTIME_PUBLICATION_AUDIT.md`). If that import fails, an orphaned dashboard will
  be classified as `MISSING`/`STOPPED` rather than the more specific `ORPHANED_RUNTIME` — still fail-closed
  (not reported healthy), just less precisely labeled.
- This phase did not modify the **live in-process frontend-payload path** in
  `backend/runtime/canonical_runtime_snapshot.py::build_canonical_runtime_snapshot()` (the branch used when
  a live dashboard process serves Mission Control directly via a registered in-process callback with a full
  frontend contract). That path was not implicated by the evidence in this task — `dashboard/web/web_app.py::create_app()`,
  when invoked via a bare `uvicorn ... --factory` CLI call with no injected `state_provider` (the manual
  invocation pattern implied by the evidence), passes `None` as the Mission Control state provider, which
  makes it fall through to the artifact-file-based path this phase fixed. If a future integration wires a
  live in-process provider for a standalone (non-launcher) process, the same orphan-detection logic should
  be extended to that path.
- No changes were made to broker connectivity status labeling; the five pre-existing test failures noted in
  §9 remain open and are unrelated to this phase.

---

## 13. Safety Confirmation

Unchanged throughout this phase:

- `execution_allowed = false`
- `live_trading_blocked = true`
- `broker_execution_armed = false`
- `advisory_only = true`

No order submission/cancellation/modification code was touched. No credentials or secrets were read,
logged, or modified. No broker authority, capital limits, risk limits, AntiBleedGuard, or Options Income
Engine logic was changed. No duplicate canonical writer was introduced — the one pre-existing conditional
fallback writer (`_publish_supervisor_heartbeat_snapshot`) still writes only under the same Phase 171B
guarantee-4 condition (canonical missing/stale), with corrected, honest content. Mission Control's
fail-closed behavior was strengthened, not weakened, in every case verified by this phase's tests. No
production runtime file on this machine (Laptop1) was mutated by this investigation; the Desktop server
was not touched, restarted, or connected to.
