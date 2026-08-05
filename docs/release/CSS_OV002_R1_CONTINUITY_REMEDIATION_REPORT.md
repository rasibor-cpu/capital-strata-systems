# CSS OV002-R1 / R1-R1 — Supervisor and Monitor Continuity Remediation Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Workstream:** OV002-R1 + OV002-R1-R1/R2/R3/R4/R5 (blocker/high/medium repair)
**Branch:** `css-v1.0.1-maintenance`
**Base HEAD:** `9a9263c185680353fac9319577b4a1f82d3311dd`
**Date:** 2026-08-04

**Explicit statements:**
- Phase 181 remains **NOT_CERTIFIED**.
- **Attempt 3 remains prohibited** by this report.
- **No endurance run was started** by this workstream.
- Live trading / broker access / desktop CSS start-stop were **not** performed.
- Prior Attempt 1/2 evidence packages were **not** modified.
- Changes remain **uncommitted** pending second independent review.

---

## 1. Independent-review finding disposition

| Sev | Finding | Disposition |
| --- | --- | --- |
| BLOCKER | Non-atomic certification JSON writes | Fixed — `ov002_persistence.atomic_write_json` + locked writes |
| BLOCKER | INVALIDATED overwriteable / non-monotonic state | Fixed — `persist_attempt_state` terminal + identity-bound |
| BLOCKER | Newest-1000 alert scan hide older criticals | Fixed — full attempt-window scan + critical ledger |
| HIGH | PID-only process identity | Fixed — v2 identity (pid, creation, parent, exe hash, cmd hash, root, role, attempt, commit) |
| HIGH | Malformed evidence can raise / soft-pass | Fixed — guarded parses → ContinuityError / invalidate |
| HIGH | Duplicate discovery exception → empty success | Fixed — discovery result `{ok, owners/processes, error_code}` |
| MEDIUM | Concurrent writer races | Fixed — exclusive writer lock/lease; stale fails closed (no steal) |
| MEDIUM | Legacy marathon/validation PASS/GO/CERTIFIED authority | Fixed — explicit non-authoritative flags + reject helper |

---

## 2. Exact repair mapping

| Component | Path |
| --- | --- |
| Atomic persistence + writer lock | `backend/certification/ov002_persistence.py` |
| Continuity / identity / ledger / cert | `backend/certification/ov002_continuity.py` |
| Monitor wiring | `backend/certification/ov002_endurance_monitor.py` |
| Supervisor atomic state + discovery | `backend/runtime/css_runtime_supervisor.py` |
| Fail-closed discovery | `launcher/css_runtime_launcher.py` |
| Legacy marathon boundary | `scripts/run_48h_paper_marathon.py` |
| Legacy endurance validation boundary | `backend/validation/endurance_validation.py` |
| R1 tests | `tests/test_ov002_r1_continuity_remediation.py` |
| R1-R1 adversarial tests | `tests/test_ov002_r1_r1_blocker_repairs.py` |
| Launcher test updates | `tests/test_css_runtime_launcher.py` |

---

## 3. Persistence and locking guarantees

**Success path:** deterministic JSON (`sort_keys`, UTF-8) → unique temp in destination directory → flush → file `fsync` → `os.replace` → best-effort directory fsync (POSIX; Windows directory fsync not claimed).

**Failure path:** temp cleaned; `PersistenceError` raised; never silent success after exception.

**Writer lock:** exclusive `O_CREAT|O_EXCL` lease file bound to `attempt_id` + `writer_role`; concurrent hold → `writer_lock_held`; expired lease → `writer_lock_stale` (**no silent steal**).

**Residual limitation:** Not a universal crash-proof durability claim across every Windows volume/network filesystem. Atomicity is path-level rename semantics; power-loss metadata flush depends on OS/volume.

---

## 4. Process-identity contract

Schema: `css.ov002.process_identity.v2`

Required comparable fields when frozen strongly: PID, parent PID, creation time, executable identity (hashed path), command identity (hashed redacted command), repo root, service role, attempt ID, baseline commit.

- Same PID + different creation time → fail
- Parent / exe / command / root / role mismatch → fail
- Missing required live fields when required → fail closed
- Secrets never persisted (redaction + hash)
- HTTP `/health` on port 8765 is never continuity proof

---

## 5. Complete-alert reconciliation contract

Chosen design: **(A) full attempt-window scan** with explicit resource bounds **plus (B) monotonic `CRITICAL_EVENTS.jsonl` ledger**.

- No newest-N truncation that can omit older in-window criticals
- Resource bound hit → `alert_scan_incomplete` / fail closed
- Malformed/truncated/unreadable alert or ledger → fail closed
- Final certification reconciles ledger count / sequence / digest
- Heartbeat recovery never erases prior critical ledger rows
- Partial scan cannot be treated as complete

---

## 6. Legacy-authority boundary

`scripts/run_48h_paper_marathon.py` and `backend/validation/endurance_validation.py` remain usable for their non-OV002 purposes but emit:

- `ov002_authoritative: false`
- `phase181_authoritative: false`

`evaluate_final_certification(..., legacy_authority_payload=...)` and `reject_legacy_certification_authority` ensure those PASS/GO/CERTIFIED tokens grant **no** OV002 or Phase 181 credit.

---

## 7. State-transition rules

```text
INITIALIZING → RUNNING | INVALIDATED | NOT_CERTIFIED
RUNNING → INVALIDATED | COMPLETED_ELIGIBLE
COMPLETED_ELIGIBLE → NOT_CERTIFIED | CERTIFIED
INVALIDATED → (terminal — no exit)
```

Clean completion → `COMPLETED_ELIGIBLE` + certification `NOT_CERTIFIED` (Phase 181 never auto-CERTIFIED).

---

## 8. R2 hardening addendum

R2 closes the second independent review findings:

- OV002 initialization now requires strong live process fields; PID-only launcher, supervisor, or service identity fails closed.
- Certification-critical JSON uses duplicate-key rejecting strict decoding for alerts, ledgers, attempt state, run metadata, status, process identity, and authority payloads.
- `INVALIDATED` replay for the same attempt/commit is idempotent and returns the original terminal record without rewriting or weakening it.
- Certification-critical persistence can be bound to the explicit attempt-package root; outside-root, symlink/reparse, substituted lock, and wrong-owner release paths fail closed.

Windows residuals remain accurately bounded: `os.replace` is path-atomic, file data is flushed and fsync'd, directory fsync is not claimed on Windows, and no protection is claimed against races below the OS APIs used for path/reparse inspection.

---

## 9. R3 hardening addendum

R3 closes the latest independent review findings:

- Authoritative live process probing now fails closed when `require_live_fields=True` and the PID is dead, inaccessible, or disappears during the recheck.
- Caller-supplied process fields no longer override OS-observed truth. Supplied parent PID, creation time, executable identity, executable SHA-256, and command identity must match the live probe.
- Windows CIM `/Date(...)` creation timestamps are normalized deterministically before comparison.
- Malformed, duplicate-key, or inaccessible `INVALIDATION.json` and `RUN_STATUS.json` are represented as invalid evidence and block eligibility instead of disappearing as absent evidence.
- Missing `RUN_META.json` in a half-initialized attempt package invalidates deterministically without an uncaught crash.
- Supervisor state and history writes are constrained to a trusted root through containment validation before persistence.
- Launcher startup now cleans up already-started child services and the supervisor if strong process-tree recording fails after child startup.
- Legacy marathon config parsing now uses duplicate-key rejecting strict JSON.
- Writer lock release revalidates lock owner and file identity immediately before unlink.
- SHA-256 collision resistance is treated as the normal cryptographic trust assumption for executable, command, ledger, and evidence hashes; no stronger guarantee is claimed.

---

## 10. Tests and results

## 10. R4 hardening addendum

R4 closes the final independent review findings:

- Final process reconciliation now requires a fresh live OS probe for every frozen launcher, supervisor, and managed service identity.
- Matching frozen and observed JSON is no longer sufficient for final OV002 continuity. The final live probe is authoritative for OS facts and is compared against both frozen initialization identity and current supervisor observation.
- Dead, inaccessible, disappeared, replaced, partially inspected, or probe-exception processes produce deterministic fail-closed reconciliation reasons.
- Monitor final reconciliation now uses `reconcile_process_identity_live(...)` rather than the pure JSON comparison helper.
- `validate_process_identity(...)` remains a non-authoritative pure comparison helper.
- Supervisor construction no longer derives `trusted_root` from caller-supplied `state_dir`.
- Absolute supervisor `state_dir` without explicit `trusted_root` is rejected with `supervisor_trusted_root_required`.
- Relative/default supervisor paths resolve beneath the independently established repository root or an explicit trusted root.
- Production controlled-shutdown observation now supplies an explicit trusted root for its temporary supervisor state.

R4 required a bounded scope expansion beyond the original dirty 12 files to update an existing production call site and its existing supervisor regression tests:

- `backend/certification/controlled_shutdown_observation.py`
- `tests/test_css_runtime_supervisor.py`

---

## 11. R5 hardening addendum

R5 closes the remaining final-reconciliation finding:

- Final process reconciliation now compares the frozen initialization `managed_services` key set with the current observed supervisor `managed_services` key set exactly.
- Service names are case-sensitive. Added, removed, renamed, or case-changed services fail closed.
- Observed-only services produce deterministic sorted reasons: `process_identity_unexpected_service:<service>`.
- Frozen-only services produce deterministic sorted reasons: `process_identity_missing_service:<service>`.
- Unexpected services are not live-probed; their observed-only presence is sufficient to invalidate final continuity.
- Every expected service in the exact intersection is still live-probed after key-set reconciliation.
- Malformed `managed_services` containers, blank service names, non-string names, and non-object service records fail closed.
- Duplicate service keys are rejected through strict duplicate-key JSON decoding on certification-critical JSON.
- The unexpected-service reason is consumed by monitor reconciliation and reaches final eligibility as `NOT_CERTIFIED`.
- Launcher and supervisor top-level roles remain explicit required identities; no schema expansion was required for R5.

The direct exploit reproduction for frozen `{}` and observed `{"Unexpected": <valid live identity>}` now returns:

```json
{"certification": "NOT_CERTIFIED", "eligible": false, "reasons": ["process_identity_unexpected_service:Unexpected"]}
```

---

## 12. Tests and results

- Compile modified Python: **exit 0**
- Supervisor/shutdown compatibility slice: **16 passed** in 31.32s
- Focused R5 blocker repair set: **54 passed** in 127.77s
- Focused R5/launcher set: **62 passed** in 125.00s
- Continuity/endurance pair: **22 passed** in 291.57s
- Full focused + regression battery (OV-002, supervisor, launcher, continuity, alerts, OV-001 shutdown, Phase 181, alert repos): **154 passed** in 457.13s
- `git diff --check`: **clean**
- Port **8765 free**; no CSS/endurance process detected

---

## 13. Residual limitations

1. Attempt 3 still requires separate owner approval — **prohibited here**.
2. Alert scan resource bounds (100k files / 256 MiB) fail closed if exceeded.
3. Windows directory fsync not claimed.
4. Strong live identity probing is mandatory on the OV002 authoritative initialization path. Non-authoritative tests/helpers may still call lower-level helpers without it.
5. ReportLab / unrelated MC gaps unchanged.
6. Phase 181 remains **NOT_CERTIFIED**.

---

## 14. Safety confirmation

- Port 8765 expected free; no CSS/endurance process started by this workstream.
- No broker/credential access.
- Simulation safety limits unchanged.

---

*End of CSS_OV002_R1_CONTINUITY_REMEDIATION_REPORT.md*
