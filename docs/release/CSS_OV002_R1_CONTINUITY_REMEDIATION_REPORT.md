# CSS OV002-R1 / R1-R1 — Supervisor and Monitor Continuity Remediation Report

**Programme:** Release Gate 3 — Operational Validation OV-002
**Workstream:** OV002-R1 + OV002-R1-R1/R2/R3/R4/R5 + **OV002-R1-R6** (post-commit IR remediation)
**Branch:** `css-v1.0.1-maintenance`
**R5 committed SHA:** `8f533b9929509b23d85d647794c55dcb3ffcb053`
**Base HEAD (pre-R1):** `9a9263c185680353fac9319577b4a1f82d3311dd`
**Date:** 2026-08-04 / R6: 2026-08-05

**Explicit statements:**
- Phase 181 remains **NOT_CERTIFIED**.
- **Attempt 3 remains prohibited** by this report.
- **No endurance run was started** by this workstream.
- Live trading / broker access / desktop CSS start-stop were **not** performed.
- Prior Attempt 1/2 evidence packages were **not** modified.
- **R5 is committed** at `8f533b9929509b23d85d647794c55dcb3ffcb053`.
- Post-commit independent review (OV002-R5-IR) decision: **CHANGES REQUIRED**.
- **R6 remains uncommitted** pending independent R6 review.

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
7. Stale writer locks are never stolen; operator must clear the lease. When invalidation cannot be durably written, `INVALIDATION_BLOCKED.json` marks the attempt non-eligible (no silent RUNNING/clean interpretation).

---

## 14. R6 post-commit IR remediation addendum

R6 addresses OV002-R5-IR findings against committed SHA `8f533b9…`:

| ID | Finding | Repair |
| --- | --- | --- |
| B1 | Missing freeze → eligible | Reconcile + final cert require freeze/`PROCESS_IDENTITY.json`; reason `process_identity_freeze_missing` |
| H1 | Empty probe mapping accepted | `identity_probe_empty` / `identity_probe_incomplete` under `require_live_fields` |
| H2 | Empty discovery stdout → ok | Structured envelope + `discovery_empty_output` / `discovery_self_missing` |
| H3 | Absolute state_dir tests/callers | Explicit `trusted_root`; absolute-without-root still rejected |
| M1 | Meta self-compare | Expected attempt/commit from `ATTEMPT_STATE` / `PROCESS_IDENTITY` |
| M2 | Silent history append | `last_history_persist_error` + reconcile reason (codes only) |
| M3 | Stale lock blocks invalidation | `INVALIDATION_BLOCKED.json`; no steal |
| M4 | Identity fail as controlled_shutdown | `identity_verification_failed` event/flag |
| L1 | Stale “uncommitted” custody text | Corrected above |
| L2/L3 | Legacy CERTIFIED ambiguity | Marathon labels `LEGACY NON-AUTHORITATIVE` + marker |

---

## 15. R6-R1 final-certification authority repair addendum

R6-R1 addresses the final-certification authority findings from the independent R6 review:

| ID | Finding | Repair |
| --- | --- | --- |
| B1 | Empty or malformed identity records could satisfy container-level validation | Canonical identity-document validation now recursively validates launcher, supervisor, and every managed-service record, including exact fields, strict PID types, canonical hashes, role/service-key agreement, and attempt/commit bindings. The `{"CSS Runtime": {}}` exploit returns `eligible=false` / `NOT_CERTIFIED`. |
| B2 | `evaluate_final_certification` could derive expected bindings from mutable evidence | Process-identity continuity now requires independently supplied `expected_run_id` and `expected_commit`; missing values emit `expected_run_id_missing` / `expected_commit_missing` and cannot become eligible. |
| B3 | Caller-supplied `reconciliation_ok=True` was too authoritative | Final certification now requires a structured process-identity reconciliation result with schema, expected bindings, frozen/evidence digests, verified role/service sets, classification, and deterministic reasons. Final evaluation recomputes digests and rejects booleans, malformed mappings, mismatches, and incomplete results. |
| H4 | Live probes and launcher discovery accepted permissive types/envelopes | Live-probe fields are validated before coercion, rejecting Boolean-as-int, list/dict/object substitutions, uppercase/malformed hashes, and non-string identity fields. Launcher discovery now requires a strict schema envelope; `ok:false` can never be rewritten into success. |

Authoritative final-certification path:

1. `initialize_run` writes `ATTEMPT_STATE.json` and `PROCESS_IDENTITY.json` from the independent attempt boundary.
2. `run_monitor_loop` reloads expected attempt ID and commit only from `ATTEMPT_STATE.json`.
3. The monitor loads persisted process identity, carries live reconciliation reasons, builds a structured reconciliation result, and passes it into `evaluate_final_certification`.
4. `evaluate_final_certification` repeats structural checks, requires the independent bindings, verifies the structured reconciliation schema, recomputes canonical digests, and remains `NOT_CERTIFIED` unless every authority check is satisfied.

R6-R1 validation evidence:

- Compile changed Python: **exit 0**
- Focused R6-R1 / launcher set: **118 passed** in 161.21s
- R1 continuity regression: **12 passed** in 92.03s
- OV002 endurance monitor regression: **10 passed** in 196.51s
- Supervisor/path-isolation regressions: **46 passed** in 44.68s
- Alert delivery / auto-restart regressions: **37 passed** in 41.69s
- Canonical decision / passive publishing regressions: **5 passed** in 4.39s
- Endurance validation / marathon wrapper regressions: **10 passed** in 3.68s
- `git diff --check`: **clean** except existing Git ignore permission and CRLF conversion warnings
- Port **8765 free**; no CSS/endurance runtime or broker access performed

R6-R1 remains **uncommitted** pending another independent review.

---

## 16. R6-R2 identity range and internal authority repair addendum

R6-R2 addresses the final R6-R1 independent-review findings:

| ID | Finding | Repair |
| --- | --- | --- |
| B1 | Non-positive process identifiers could pass structural identity validation | CSS now uses one canonical PID contract for authoritative identity records: exact `int`, Boolean rejected, `1 <= pid <= 4294967295`. Launcher, supervisor, service, live-probe, top-level binding, freeze, persisted evidence, reconciliation, discovery, and final certification paths reject zero, negative, overflow, floats, strings, nulls, lists, mappings, and objects. |
| H1 | Discovery rows accepted incomplete process records | Runtime discovery rows now require the exact committed Windows row schema: `ProcessId`, `ParentProcessId`, `CreationDate`, `ExecutablePath`, and `CommandLine`. Missing or unknown fields and malformed row values fail the complete discovery result. |
| M1 | Caller-created reconciliation mappings could look authoritative | Final certification now requires the exact private frozen reconciliation result produced by the authoritative in-process factory. Public JSON/dict payloads remain audit-only and are rejected as `process_identity_reconciliation_result_not_authoritative`. Serialized/deserialized copies, booleans, nulls, lookalikes, mismatched digests, and cross-attempt/cross-commit reuse fail closed. |

PID range contract:

- Minimum valid PID: `1`
- Maximum valid PID: unsigned 32-bit ceiling `4294967295`
- Parent PID for authoritative CSS identities also follows the same positive range contract.
- No numeric string, float, Boolean, null, collection, or object coercion is accepted on authoritative paths.

Exact discovery-row contract:

- Envelope remains fixed schema/version, `ok is true`, exact anchor PID, `self_observed is true`, `error_code/error_type is null`, and bounded subprocess execution.
- Every process row must have exactly the committed Windows fields. One malformed row fails the full discovery result.
- The prior partial-row exploit containing only `ProcessId` and `CommandLine` now returns `ok=false`.

Private reconciliation authority boundary:

- Production final certification loads expected bindings from `ATTEMPT_STATE.json`, validates `PROCESS_IDENTITY.json`, consumes live reconciliation reasons, builds a private frozen reconciliation result, and passes that object directly to final eligibility.
- The lower-level final evaluator does not deserialize reconciliation authority from JSON and does not treat dictionaries or booleans as authoritative.
- This is an application-level authority boundary. No claim is made against malicious code already executing inside the Python interpreter.

R6-R2 validation evidence:

- Compile changed Python: **passed**
- Focused blocker-repair file: **167 passed** in 174.45s
- Launcher/discovery suite: **44 passed** in 39.62s
- Continuity/endurance pair: **22 passed** in 339.73s
- Supervisor/path/runtime lifecycle: **58 passed** in 83.90s
- Alert/auto-restart/decision/publishing: **42 passed** in 44.52s
- Endurance/Phase181/wrapper: **22 passed** in 17.13s
- OV001/alert/reconciliation: **25 passed** in 51.92s
- Complete approved OV002 battery collection: **380 tests collected**; this reconciles to the R6-R1 287-test baseline plus 93 R6-R2 matrix/regression cases.

R6-R2 remains **uncommitted** pending independent review.

---

## 17. Safety confirmation

- Port 8765 expected free; no CSS/endurance process started by this workstream.
- No broker/credential access.
- Simulation safety limits unchanged.

---

*End of CSS_OV002_R1_CONTINUITY_REMEDIATION_REPORT.md*
