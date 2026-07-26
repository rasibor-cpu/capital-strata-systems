# CSS OV-002 — Supervisor and Monitor Remediation Plan

**Programme:** Release Gate 3 — Operational Validation OV-002
**Authority trigger:** Formal invalidation of OV-002 Attempt 2
**Companion:** `docs/release/CSS_OV002_ATTEMPT2_INVALIDATION_REPORT.md`
**Freeze reference (Attempt 2):** `0ff97cba114c051b640eeabe2edacdecc5c02053`
**Status:** PLAN ONLY — no implementation authorized by this document
**Attempt 3:** Must begin from zero only after owner approval

---

## Purpose

Attempt 2 demonstrated that HTTP health, snapshot volume, and wall-clock elapsed time can remain green while supervisor alerts record unexpected runtime exits, restart accumulation beyond the declared limit, and CRITICAL engine heartbeat loss.

This plan defines the remediation required before any future OV-002 Attempt 3 may be declared `READY FOR ENDURANCE`.

---

## Findings to remediate (Attempt 2)

1. Nested / duplicate launcher process trees obscure canonical identity.
2. Unexpected `CSS Runtime` exits were auto-restarted repeatedly.
3. `max_restart_limit=3` did not prevent cumulative `restart_count=8`.
4. Failure counters appear non-durable / reset-prone (`failure_count` not a trustworthy ledger).
5. CRITICAL `ENGINE_HEARTBEAT_LOST` alerts were not ingested by the endurance monitor.
6. Monitor recommended provisional PASS without reconciling alerts, restarts, heartbeat continuity, or process-tree identity.
7. Port/`/health` continuity (including stable mobile PID) is necessary but not sufficient.

---

## Remediation workstreams

### 1. Canonical process-tree identity

- Define a single canonical launcher entry (`launch_css.bat` → one supervisor → managed children).
- Persist a freeze-time process identity record: launcher PID, supervisor PID, runtime PID, mobile PID, bound ports.
- Prohibit nested re-exec of the runtime launcher under a second interpreter as an unlabeled identity.
- Require Attempt N start reports to fingerprint the tree and treat unexplained PID replacement of supervised roles as invalidating (except documented controlled restart).

### 2. Duplicate launcher / supervisor prevention

- Pre-start gate: fail if port `8765` is occupied by a non-canonical tree.
- Pre-start gate: fail if more than one `css_runtime_launcher` / supervisor instance is active for the repo.
- Refuse endurance start when duplicate trees are detected.
- Document a governed single-tree stop/start sequence for operator use (without implying this plan performs it).

### 3. Correct enforcement of `max_restart_limit`

- Enforce the limit on **cumulative successful unexpected restarts** within the supervisor lifetime (and/or within the endurance window), not only on a per-burst attempt counter that resets to `1/3`.
- When the limit is reached: stop auto-restart, emit CRITICAL, mark endurance invalidation candidate.
- Add explicit tests that a fourth unexpected restart cannot be silently applied when limit is 3.

### 4. Durable restart and failure history

- Persist an append-only restart/failure ledger (JSONL or equivalent) with UTC timestamps, service name, PID before/after, exit code, reason, attempt index, and cumulative counts.
- Do not rely solely on a mutable summary file that can reset `failure_count` while `restart_count` climbs.
- Include ledger path in OV evidence packages.

### 5. Heartbeat-loss reconciliation

- Treat `ENGINE_HEARTBEAT_LOST` (CRITICAL) as a first-class continuity fault.
- Correlate heartbeat-loss alerts with runtime process exit/restart events and supervisor heartbeats.
- Require clear distinction between launcher supervisor heartbeat and engine heartbeat; both must be monitored for endurance.

### 6. Endurance-monitor ingestion of supervisor alerts

- Extend OV-002 monitor snapshots (or a sidecar reconciler) to ingest `runtime/alerts` created during the run window.
- Classify severities: WARNING unexpected exit, INFO restart success, CRITICAL heartbeat loss, restart exhausted.
- Surface alert digests in checkpoints and final status; never allow final PASS while unreconciliation CRITICAL/unexpected-restart faults exist.

### 7. Automatic invalidation on unexpected restart or critical heartbeat loss

- Hard invalidation triggers (fail closed):
  - Any unexpected supervised-service restart during the endurance window (unless pre-declared controlled recovery procedure was armed — default: not armed)
  - Any CRITICAL engine heartbeat-loss alert during the window
  - Restart limit exhaustion
  - Canonical process-tree identity break
- On trigger: write `INVALIDATION.json`, set `RUN_STATUS=INVALIDATED`, stop claiming PASS, preserve evidence.

### 8. Process continuity checks in addition to HTTP health

- Each snapshot must verify expected PIDs / roles still match the freeze identity (or record an allowed transition with reason).
- Detect “HTTP green / engine dead” patterns (mobile health OK while runtime repeatedly restarting).
- Keep HTTP checks; add process and alert checks as equal peers.

### 9. Freshness checks for validation timestamps

- Reject stale broker/validation timestamps that predate the Attempt start when used as “current” posture.
- Require freshness windows for telemetry, supervisor heartbeat, and alert ingestion lag.
- Invalidate or flag when monitor snapshots continue while alert/heartbeat streams show material discontinuity.

### 10. Focused regression tests

Add focused tests (no live brokers, no order submission) covering:

- Restart limit enforcement
- Durable ledger append behavior
- Alert ingestion → invalidation mapping
- Heartbeat-loss CRITICAL → INVALIDATED
- Duplicate launcher detection
- Process identity mismatch detection
- Monitor must not emit PASS when invalidating alerts exist in-window

### 11. Clean pre-run checklist for a future Attempt 3

Before any Attempt 3 readiness decision:

1. Owner approval recorded.
2. Remediation items 1–10 implemented or explicitly waived in writing by owner.
3. Single canonical process tree verified.
4. No duplicate launchers/supervisors.
5. Alert directory baseline marked (so in-window alerts are attributable).
6. Safety assertions pass (execution disabled, live blocked, advisory/fail-closed).
7. Fresh freeze SHA recorded; no mid-run commits planned.
8. Monitor build includes alert + process-identity invalidation.
9. Attempt 3 evidence directory is new; Attempt 1/2 packages preserved untouched.
10. Readiness document states exactly one of: `READY FOR ENDURANCE` or `NOT READY FOR ENDURANCE`.

### 12. Attempt 3 start policy

- Attempt 3 begins at **zero** elapsed time only.
- No carry-forward from Attempt 1 or Attempt 2.
- **Owner approval required** before readiness may flip to `READY FOR ENDURANCE`.
- No production, live-execution, broker, or Phase 181 certification claim is implied by completing this plan.

---

## Suggested implementation order

1. Monitor invalidation hooks (alerts + unexpected restart + heartbeat loss) — highest certification integrity value
2. Durable restart/failure ledger + true `max_restart_limit` enforcement
3. Canonical process-tree identity + duplicate prevention
4. Freshness checks
5. Focused regressions
6. Attempt 3 checklist execution under owner approval

---

## Out of scope (this plan)

- Stopping or restarting the currently running CSS server
- Broker access, credential changes, order submission, or execution enablement
- Modifying Attempt 2 evidence files
- Starting Attempt 3
- Claiming Phase 181 certification

---

## Acceptance for closing this remediation

Remediation may be marked implemented only when:

- Focused regressions pass on the freeze SHA intended for Attempt 3
- A dry-run monitor session demonstrates automatic INVALIDATED on injected unexpected restart and on CRITICAL heartbeat-loss fixtures
- Owner signs Attempt 3 readiness separately

Until then, OV-002 remains incomplete and Phase 181 remains **`NOT_CERTIFIED`**.

---

*End of CSS_OV002_SUPERVISOR_AND_MONITOR_REMEDIATION_PLAN.md*
