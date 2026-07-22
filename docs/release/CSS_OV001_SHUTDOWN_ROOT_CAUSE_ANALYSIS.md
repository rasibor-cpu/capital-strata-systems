# OV-001 — OAT SHUTDOWN Root Cause Analysis

**Programme:** Release Gate 3 — Operational Validation OV-001  
**Date:** 2026-07-22  
**Baseline:** RC-001 `6513e6a1e45ffc42aff192e1c784171ad6fc182b`  
**HEAD at analysis:** `b7c3d32678a42d90338d1da7f6ebe34fb200f28a`  
**Rule:** Document root cause before code changes.

---

## 1. Acceptance criterion that fails

Phase 181 OAT requirement **`SHUTDOWN`** under `OPERATIONAL_ACCEPTANCE`.

Evaluator: `backend/certification/operational_acceptance.py` → `OAT_REQUIREMENTS` includes `"SHUTDOWN"`.

Production-profile acceptance requires a `CertificationEvidence` row with:

- `area="SHUTDOWN"`
- `status=PASS`
- `verified=True`
- real filesystem `reference` (not `evidence://`)
- `observed_at` set

Batch 2 pack (`runtime_reports/batch2_certification_evidence_*`) recorded:

```json
"shutdown": {
  "ok": false,
  "status": "NOT_PERFORMED",
  "reason": "Controlled process shutdown observation requires authorized operational run"
}
"shutdown_performed": false
```

OAT percentage: **88.89%** — sole blocker **`SHUTDOWN`**.

---

## 2. Expected shutdown behavior

For Gate 3 Operational Validation, a passing SHUTDOWN observation must demonstrate:

1. Supervisor stop requested and acknowledged.  
2. Runtime/service cycle stopped.  
3. Child process(es) terminated or explicitly accounted for.  
4. Bound probe port released within documented timeout.  
5. PID cleared (process no longer running).  
6. Final state reported accurately (`STOPPED` / complete — never “complete” while process alive).  
7. Start→stop cycle repeatable without false PASS.

Canonical launcher pattern already encodes stop semantics:

```text
KeyboardInterrupt / shutdown request
  → CSSServiceManager.stop() for each child
  → CSSRuntimeSupervisor.stop()
  → “CSS Always-On Runtime Launcher stopped.”
```

(`launcher/css_runtime_launcher.py` finally-block)

---

## 3. Actual shutdown behavior (pre-OV-001)

| Layer | Actual |
| --- | --- |
| Ops host activation | STARTUP / RUNTIME_HEALTH captured via `activate_operations_service` |
| Ops host shutdown | **No `stop`/`deactivate` API** on `host_activation` — no paired SHUTDOWN observation |
| Batch 2 OAT capture | Explicitly skips SHUTDOWN (`NOT_PERFORMED`) |
| Desktop runtime | Live `css_mobile_launcher` on :8765 can stop via process kill / launcher interrupt, but **no Class B OAT artifact** was produced |
| Evidence authority | Correctly fail-closed: missing SHUTDOWN → OAT incomplete |

---

## 4. Cause classification

| Hypothesis | Verdict |
| --- | --- |
| Incomplete process termination (runtime bug) | **Not primary** — launcher `CSSServiceManager.stop()` exists and terminates children |
| Stale PID / lock state | **Not evidenced** as the OAT failure mode |
| Orphaned child processes | Environmental risk during Desktop restarts; not the Batch 2 OAT blocker |
| Incorrect supervisor state | Not the recorded OAT failure |
| Port retention | Soft risk after RC-001 restart; not the Batch 2 SHUTDOWN miss |
| Delayed cleanup | Not the recorded OAT failure |
| Evidence-capture logic | **PRIMARY** — SHUTDOWN observation never executed / never archived |
| Inaccurate OAT assertion | **No** — requiring verified SHUTDOWN evidence is correct for production profile |

**Root cause:** Evidence-capture gap (operational observation not performed), not an invalid OAT criterion and not a proven defect in `CSSServiceManager.stop()` itself.

**Secondary gap:** Ops host activation has no symmetric controlled-shutdown helper that OAT can call without fabricating evidence.

---

## 5. Defect vs environment

| Question | Answer |
| --- | --- |
| Existed in RC-001? | **Yes** — RC-001 inherited Batch 2 AR-013 residual (`SHUTDOWN`) |
| Environmental only? | Partially — Desktop can be stopped, but OV requires **custody-bound observation**, not ad-hoc kill |
| Code change required? | **Yes (minimal)** — add controlled shutdown observation drill + wire into OAT capture; do not weaken fail-closed |

---

## 6. Corrective approach (authorized for Part C)

1. Implement `capture_controlled_shutdown_observation()` that:  
   - starts supervisor + a short-lived probe service (ephemeral port),  
   - requests stop,  
   - verifies process exit + port release within timeout,  
   - archives JSON + custody (never claims PASS if process still alive).  
2. Extend OV-001 / OAT assembly to include SHUTDOWN evidence when observation PASSes.  
3. Add focused regression tests (false-complete forbidden; port/PID checks).  
4. Do **not** fabricate SHUTDOWN PASS without running the drill.  
5. Do **not** amend RC-001; any code change → RC-002 candidate.

---

## 7. Non-goals

- 72-hour endurance  
- Live trading enablement  
- Broad supervisor redesign  
- Killing Desktop :8765 as the sole proof (probe drill is sufficient for OAT SHUTDOWN; Desktop stop may be recorded as supplemental)

---

*End of CSS_OV001_SHUTDOWN_ROOT_CAUSE_ANALYSIS.md — code changes may proceed.*
