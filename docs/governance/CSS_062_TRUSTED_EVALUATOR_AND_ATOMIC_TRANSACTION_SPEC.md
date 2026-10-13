# CSS-062 — Trusted Evaluator Ownership and Atomic Nonce/Reservation Specification

**Status:** Implementation specification (NOT implemented, NOT wired into live or production paper execution).
**Scope:** Engineering design specification for the trusted-authorization-issuer and atomic-transaction boundary required to complete CSS-062 (independent pilot security review).
**Approval required:** Separate owner approval before any live or production-paper wiring. This document does NOT authorize any release, trading, or deployment.

---

## 1. Problem

PR #107 added `simulate_governed_paper_order` as **scaffolding**. Two gaps remain:

1. **Trusted-evaluator ownership:** `PaperGateEvaluators` callables are caller-supplied. A test can pass `lambda req: {"approved": True}`. The issuer *invokes* these callables internally, but the callables themselves are not trusted — they do not bind to a verified risk-decision producer. This demonstrates signing scaffolding, not trusted authority.
2. **Atomic nonce/reservation transaction:** The simulation calls `authorization_ledger._claim()` (a private helper) to consume the nonce, then separately calls `reserve_converted_pilot_exposure()` on a different ledger (SQLite). A crash between the two leaves the nonce burned but no reservation (or vice versa). No crash-safe transaction spans both.

---

## 2. Trusted evaluator ownership (design)

### 2.1 Contract

A trusted evaluator is a **named, versioned, config-pinned callable** that:

- lives in a specific module (e.g. `backend/runtime/trusted_risk_evaluators.py`);
- has a stable function name (e.g. `r7_evaluate`, `antibleed_evaluate`, `risk_governor_evaluate`, `kill_switch_evaluate`);
- is constructed at simulation-start from a **pinned config file** (e.g. `config/governance/trusted_evaluators.json`);
- is NOT accepted from the request/kwargs.

### 2.2 Pinned evaluator registry

```json
{
  "schema": "css.trusted_evaluators.v1",
  "candidate_sha": "<40-char hex>",
  "evaluators": {
    "r7": {"module": "backend.runtime.trusted_risk_evaluators", "function": "r7_evaluate", "version": 1},
    "antibleed": {"module": "backend.runtime.trusted_risk_evaluators", "function": "antibleed_evaluate", "version": 1},
    "risk_governor": {"module": "backend.runtime.trusted_risk_evaluators", "function": "risk_governor_evaluate", "version": 1},
    "kill_switch": {"module": "backend.runtime.trusted_risk_evaluators", "function": "kill_switch_evaluate", "version": 1}
  }
}
```

Rules:
- The registry must pin the **candidate_sha**; a mismatch is a hard fail.
- Missing module/function/version fields is a hard fail.
- The module+function must resolve via `importlib` to a callable in the repository's committed source.
- The registry file must NOT contain any secrets, private keys, or credentials.
- The registry is read-only during simulation; any drift (mtime change) is logged and fails closed on the next start.

### 2.3 Wrapping

```python
class TrustedEvaluatorBundle:
    def __init__(self, registry_path, candidate_sha):
        cfg = json.loads(Path(registry_path).read_text())
        if cfg["candidate_sha"] != candidate_sha:
            raise TrustedEvaluatorError("candidate_sha_mismatch")
        self._evaluators = {}
        for name, spec in cfg["evaluators"].items():
            fn = _resolve(spec["module"], spec["function"])   # importlib
            if not callable(fn):
                raise TrustedEvaluatorError(f"evaluator_not_callable:{name}")
            self._evaluators[name] = (fn, spec["version"])
        if set(self._evaluators) != {"r7", "antibleed", "risk_governor", "kill_switch"}:
            raise TrustedEvaluatorError("evaluator_set_incomplete")

    def evaluate(self, name, order_request):
        fn, _version = self._evaluators[name]
        result = fn(order_request)
        if type(result) is not dict or result.get("approved") is not True:
            return {"approved": False, "reason": result.get("reason") if type(result) is dict else "evaluator_unavailable"}
        return result
```

- A failed/missing evaluator returns `approved: False` (fail closed), never raises out.
- The `PaperAuthorityIssuer.issue_paper_intent` accepts a `TrustedEvaluatorBundle` (not raw callables) and refuses `PaperGateEvaluators` in the trusted path.

### 2.4 Anti-substitution

The issuer must reject a `PaperGateEvaluators` (raw callables) when `trusted_only=True` is set in the pinned config. This prevents a test/production path from silently substituting lambdas.

### 2.5 Acceptance tests (must be written before wiring)

1. `test_trusted_bundle_rejects_candidate_sha_mismatch` — a registry pinned to a different `candidate_sha` raises.
2. `test_trusted_bundle_rejects_missing_evaluator` — remove `kill_switch` from the registry → hard fail.
3. `test_trusted_bundle_rejects_unknown_module` — a registry pointing at a nonexistent module → hard fail.
4. `test_trusted_bundle_rejects_non_callable` — registry pointing at a non-callable attribute → hard fail.
5. `test_trusted_bundle_fail_closed_on_evaluator_exception` — an evaluator that raises returns `approved: False`, never propagates.
6. `test_paper_authority_issuer_rejects_raw_gate_evaluators_in_trusted_mode` — passing `PaperGateEvaluators` (raw lambdas) is rejected.
7. `test_paper_authority_issuer_accepts_trusted_bundle` — a `TrustedEvaluatorBundle` produces a valid signed intent.
8. `test_trusted_bundle_registry_drift_fails_closed` — the registry file mtime changes mid-simulation → next start fails.

---

## 3. Atomic nonce/reservation transaction (design)

### 3.1 Goal

Consume the nonce AND create the exposure reservation as **one atomic unit**, so a crash cannot leave one applied and the other not.

### 3.2 Why the current design is not atomic

- `PilotAuthorizationLedger._claim()` creates `<approval_id>.claim` with `O_CREAT|O_EXCL` and fsyncs a JSONL journal (SHA-256 hash chain).
- `PilotExposureReservationLedger.reserve()` opens a separate SQLite DB with `BEGIN IMMEDIATE`.
- These are two **different** storage systems with **no shared transaction**.

### 3.3 Proposed boundary: a single "coordination ledger"

Introduce `backend/runtime/pilot_coordination_ledger.py`:

```python
class PilotCoordinationLedger:
    """One atomic boundary spanning nonce-consumption and exposure-reservation."""

    def atomic_consume_and_reserve(
        self,
        *,
        approval_id: str,
        nonce_payload: dict,          # the signed intent payload
        reservation: dict,            # parent_id, child_id, source_currency, gross, cash, max_loss, fees, rate
    ) -> CoordinationReceipt:
        # Phase 1: prepare
        #   - BEGIN IMMEDIATE on SQLite
        #   - insert a `coordination` row keyed by approval_id (state=PENDING)
        #   - fsync journal WAL
        # Phase 2: claim the nonce
        #   - O_CREAT|O_EXCL on `<approval_id>.claim`
        #   - fsync the claim file
        # Phase 3: create the reservation
        #   - call PilotExposureReservationLedger.reserve(...) *inside* the same
        #     SQLite transaction (the coordination ledger wraps the exposure
        #     ledger's connection)
        # Phase 4: commit
        #   - SQLite COMMIT
        #   - append the CONSUMED entry to the authorization journal
        #   - fsync the journal
        # If any phase fails → ROLLBACK, remove the claim file, return a
        # CoordinationReceipt(success=False, reason)
```

### 3.4 Crash-safe semantics

| Crash point | Effect |
|---|---|
| After Phase 1 (coordination row PENDING), before Phase 2 | Coordination row is ROLLED BACK; no nonce consumed; no reservation. |
| After Phase 2 (nonce claimed), before Phase 3 | Coordination row ROLLED BACK; the `.claim` file is deleted (revert); nonce is NOT consumed. |
| After Phase 3 (reservation created), before Phase 4 COMMIT | SQLite ROLLBACK discards the reservation; the `.claim` file is deleted; nonce is NOT consumed. |
| After Phase 4 COMMIT, before journal append | Reservation is durable; nonce is consumed; the journal is out-of-sync — detected on next `verify_chain()` and surfaced as `PAPER_SIMULATION_JOURNAL_DESYNC` (fail closed). |

### 3.5 New reason codes

- `PAPER_SIMULATION_COORDINATION_REJECTED:<reason>` — any phase failed.
- `PAPER_SIMULATION_JOURNAL_DESYNC` — the journal does not match the coordination ledger.

### 3.6 Acceptance tests

1. `test_atomic_consume_and_reserve_succeeds` — happy path produces a `CoordinationReceipt` with both nonce-consumed AND reservation-created.
2. `test_crash_after_prepare_rolls_back_everything` — simulate a crash between Phase 1 and Phase 2; verify the nonce is NOT consumed and no reservation exists.
3. `test_crash_after_claim_rolls_back_everything` — simulate a crash between Phase 2 and Phase 3; verify the `.claim` file is deleted and the nonce is NOT consumed.
4. `test_crash_after_reservation_rolls_back_everything` — simulate a crash between Phase 3 and Phase 4; verify the reservation is ROLLED BACK and the nonce is NOT consumed.
5. `test_journal_desync_fails_closed` — tamper with the journal after a successful commit; verify the next `verify_chain()` raises.
6. `test_concurrent_atomic_consume_and_reserve_serializes` — two racing threads with the same approval_id; exactly one succeeds.
7. `test_replay_after_commit_rejected` — calling `atomic_consume_and_reserve` twice with the same approval_id is rejected with `PAPER_SIMULATION_INTENT_REPLAYED`.

---

## 4. What this spec does NOT authorize

- Does NOT wire any of the above into `submit_governed_paper_order` (production path).
- Does NOT enable the CAD 20 AntiBleed exception.
- Does NOT lower any AntiBleedGuard threshold.
- Does NOT enroll any production key.
- Does NOT merge PR #107, #108, #105, #106, or #101.
- Does NOT claim release-GO or production-activation.

All of the above require separate owner approval and are gated on CSS-061 (full regression), CSS-063 (broker safeguards), CSS-064 (endurance), and CSS-069 (independent readiness review).

---

## 5. Windows-host acceptance requirements (must run on the real Windows host)

The following must be executed on the actual Windows host (FINANCE) and cannot be certified from Linux:

1. **CSS-061 full regression** — the 24 host-dependent OV-002/phase163 tests must pass on Windows.
2. **CSS-064 governed 72-hour endurance run** — `scripts/css064_endurance_package.py` executed on Windows, producing an independent manifest.
3. **Windows Credential Manager / DPAPI** — sponsor and reviewer key enrollment must be done on the approver's own Windows profile.
4. **`GetTickCount64` reboot detection** — the phase163 endurance reboot-detection test must be re-run on Windows.
5. **Kill-switch confirmation** — the emergency-stop/kill-switch rehearsal must be performed on Windows.
6. **Any live/paper broker connectivity** — read-only evidence collection requires the Windows host with owner-held credentials.

None of these can be simulated, mocked, or claimed as passing from this Linux sandbox.
