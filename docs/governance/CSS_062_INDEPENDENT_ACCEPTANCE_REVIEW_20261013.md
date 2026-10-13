# CSS-062 — Independent Security Acceptance Review (2026-10-13)

**PR:** #109 (`css-agent/css062-trusted-atomic-2026-10-13` → `governance/cad20-cross-asset-pilot-closeout`), draft
**Reviewed head:** `bc7d59719f5e4c65e3a75314ef2efd5daaa8834c` (two prior green `candidate-pilot-ci` runs)
**Review fixes:** committed on top of that head in this PR (see git log for the SHA).
**Scope:** simulation-only controls. This review does **not** authorize merge, deployment, broker orders, live trading, or production GO.

## Verdict

**CSS-062 is NOT yet eligible for independent acceptance.** Gates 1 and 4 PASS. Gates 2, 3 and 5 FAIL on items that require an owner decision or owner-held credentials. Code-level defects found during review were fixed and pinned by negative tests; the remaining items are tracked as strict-xfail tests so they cannot silently go stale.

## Five-gate acceptance matrix

| Gate | Finding under review | Verdict | Evidence | Remaining dependency |
|---|---|---|---|---|
| 1 Reservation reconciliation | Legacy and trusted writers must share one capacity view; reconciliation idempotent; concurrency/restart safe | **PASS** | Same SQLite DB and `BEGIN IMMEDIATE` writer lock as `pilot_reservations`; ceilings capped by `CanonicalOrderLimitConfig.validate()` (≤ CAD 20/40/2). Review fix **R-5**: `reconcile_legacy()` created a duplicate legacy record for every trusted-path reservation; fixed + `test_reconcile_does_not_duplicate_trusted_path_records`. Concurrency, restart and SIGKILL-before-commit tests pass (3 repeated runs). | None for simulation scope. |
| 2 Authenticated authority | Trust state must not be caller-established | **FAIL** | Signing/verification mechanics correct; verification now uses the **pinned** public key (review fix). But **G2-A**: any caller can build an `AuthenticatedTrustRegistry` from its own freshly generated key; there is no owner-signed manifest or root-of-trust check in code. `repo_root` is caller-supplied (a fake `.git/HEAD` passes) and the HEAD check ignores uncommitted changes. Strict-xfail: `test_open_self_provisioned_registry_is_rejected`. | **Owner:** generate issuer key outside the repo; produce signed manifest (issuer_id, public key, reviewed SHA); choose root-of-trust format; then engineering adds manifest verification and removes caller-supplied `repo_root` from the trusted path. |
| 3 Signed order/risk binding | Reserved amount must be the signed, evaluated order | **FAIL** | Review fix **R-4**: route re-read the caller's mutable `Mapping` after signing, so the reserved CAD could differ from the signed CAD; now read from the verified signed payload (`test_reservation_uses_signed_payload_not_caller_mapping`). But **G3-A**: `proposed_child_cad` is not derived from the notional the gates evaluated (e.g. RiskGovernor approves 50,000 notional while 0.01 CAD is reserved). The older route bound CAD risk via verified broker + FX-rate evidence; the trusted route dropped it. Strict-xfail: `test_open_reserved_cad_bound_to_evaluated_notional`. | **Owner design decision:** required CAD-normalization contract (instrument/rate evidence) for the trusted route. |
| 4 Fail-closed risk gates | No truthy/forged/error ALLOW; real kill switch authoritative | **PASS** | Explicit `is True` on every adapter and on verification; adapter exceptions → denial; NaN/inf denied; kill switch read from `os.environ`, request `env` ignored; `TrustedRiskEvaluators` final; `pilot_min_size_exception=None`; `PILOT_MIN_SIZE_EXCEPTION_ENABLED = False`. Existing tests + kill-switch suite added to CI. | None for simulation scope. |
| 5 Simulator outcome / crash consistency | Outcomes must be bound; ack-uncertainty reconciled, never assumed | **FAIL** | Review fixes: **R-1** fill evidence could *release* capacity; **R-2** any duck-typed object counted as evidence and evidence was not bound to a child; **R-3** a replayed `approval_id` hitting a SQLite error was reported as a durable success because durability was checked by `approval_id` alone (now by this transaction's unique `transaction_id`); route ignored ACK-uncertain because it was nested under `not success`; corrupt stored amounts escaped as raw exceptions. All fixed and pinned. Remaining **G5-A**: legacy `PilotExposureReservationLedger.transition()` on the same DB can release a trusted reservation with no evidence; the untrusted `simulate_governed_paper_order` (raw callables) is still callable. Strict-xfail: `test_open_legacy_api_cannot_release_trusted_reservation`. Outcome evidence is an in-process typed record, not a cryptographic attestation (acceptable only for local simulation). | **Owner decision:** retire or gate the legacy writer and legacy simulation path. Authenticated outcome evidence before any paper-broker integration. |

## Production route

`submit_governed_paper_order` raises `PAPER_AUTHORITY_PROVENANCE_UNVERIFIED` on every path before order validation, reservation or broker calls. Its body is unchanged from the base branch apart from a pre-existing move of `import math` to module level. Now pinned by an AST test (`test_production_route_raises_unconditionally_before_side_effects`) and the existing `tests/test_governed_paper_route.py`, both added to CI. The trusted route imports no broker module and calls no submit function (AST test).

## Trusted-registry owner provisioning (verified, nothing invented)

- No owner issuer key, manifest or root of trust exists in the repository; every key in tests is an ephemeral `Ed25519PrivateKey.generate()` in-process.
- `config/governance/pilot_approver_enrollment.json`: designations `PILOT_SPONSOR` = robert-asibor, `RELEASE_SECURITY_APPROVER` = diana-whyte; `keys: []` (no production keys enrolled).
- Required from the owner (not doable here): issuer keypair generated and held outside the repo; owner-signed manifest pinning issuer_id, public key hex and the reviewed commit SHA; decision on root-of-trust format; Windows DPAPI enrollment for sponsor and reviewer keys (spec §5).

## Test evidence

| Run | Result |
|---|---|
| Baseline scoped CI suite at `bc7d597` (local, Python 3.13) | 211 passed |
| Independent probes at `bc7d597` | 8/8 defects reproduced |
| New regression tests against original code (mutation check) | 12 of 16 fail as expected (the other 4 are guard tests that already held) |
| Expanded scoped CI suite with fixes (local, Python 3.11.17, pytest 9.1.1, cryptography 50.0.2) | **241 passed, 3 xfailed** |
| Concurrency/crash subset, 3 repeats | 61 passed, 3 xfailed each run |

## Path to acceptance

1. Owner provisions registry inputs and approves a root-of-trust format (G2-A); engineering implements manifest verification.
2. Owner approves the CAD-normalization contract for the trusted route (G3-A); engineering implements it.
3. Owner decides to retire or gate the legacy reservation writer and the untrusted simulation path (G5-A).
4. Re-run this review; the three strict-xfail tests must be converted to passing tests.

Independent of CSS-062, production remains gated on B-5…B-7 of the spec (CSS-061, CSS-063, CSS-064, CSS-069 and Windows-host evidence).
