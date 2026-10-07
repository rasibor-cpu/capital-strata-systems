# Configurable governed micro-pilot — implementation stages 1–3

The pilot exposure ceiling is an approved **parameter**, not a permanent code ceiling,
but it can only *narrow* the existing canonical order-limit cap
(`backend/config/order_limit_config.py`, CAD 20). Raising that cap is a separate
governed change. No automatic escalation occurs. CAD-only until cross-currency
handling is certified.

## Stage 1 (commit 8b08193)
- Typed pilot profile; expiry and session binding; one order; no margin.
- Aggregate exposure = current + pending + proposed + fees.
- Fresh (<=30 s) broker reconciliation and minimum net-edge preflight.

## Stage 2 — this increment
| Control | Implementation | Evidence |
|---|---|---|
| No bypass via alternate construction | Validation in `GovernedPilotProfile.__post_init__` (covers `__init__`, `dataclasses.replace`, `from_mapping`); exact-type checks reject subclasses/look-alikes | `test_direct_construction_and_replace_are_validated`, `test_subclass_or_lookalike_profiles_rejected` |
| Unknown fields fail closed | `from_mapping` rejects any key outside the dataclass fields | `test_unknown_fields_fail_closed` |
| Scope validation | amount (positive, whole cents, <= canonical cap), currency (CAD), asset class (cash, non-derivative allow-list), broker/account/instrument/session identifiers, `scope == PILOT_PREFLIGHT_ONE_ORDER`, approver, issued_at < expires_at <= issued_at + 24 h | `test_invalid_profiles_rejected`, `test_scope_mismatch_blocks` |
| Tamper evidence + dual control (stage 3) | Two independently attributable approvals (`PILOT_SPONSOR`, `RELEASE_SECURITY_APPROVER`), each an HMAC-SHA256 over the exact profile digest with a role-registered key; re-verified and re-validated on every evaluation and at consumption | `test_dual_control_required_and_tamper_evident`, `tests/test_pilot_dual_control.py` |
| Replay / duplicate / restart reuse | `PilotAuthorizationLedger`: atomic `O_EXCL` claim per approval, `flock`-serialised, fsync'd, SHA-256 hash-chained journal; revocation burns the claim; tampered journal fails closed | `tests/test_pilot_authorization_ledger.py` (incl. 6-process race) |
| Evaluation never raises | any unexpected error -> `PILOT_BLOCKED_EVALUATION_ERROR` | `test_malformed_inputs_fail_closed_without_raising` |

## Stage 3 — dual-control authorization (owner decision 2026-10-07)
- **Distinct approvers:** the profile names `sponsor_id` (Business Owner / Pilot Sponsor) and
  `release_approver_id` (independent release/security role). They must be different people.
- **Exact release binding:** the profile carries `release_sha`, an exact 40-hex candidate commit, and
  preflight and consumption require `running_release_sha == release_sha`.
- **Signed digest:** each approval signs the canonical profile digest, which binds account, broker,
  instrument, asset class, ceiling, currency, validity window, session and release SHA.
- **Key custody:**
  - Key material comes only from a `PilotSecretProvider`, the owner-approved external secret interface.
    No provider implementation, key or key file is in this repository.
  - Tests use ephemeral random keys, labelled test-only.
  - Evidence and the ledger journal record key IDs/versions only, never key material.
- **Key registry:** metadata only (key ID, role, status, validity). Rotation works through multiple
  versions per role. RETIRED, REVOKED, unknown, out-of-window and wrong-role keys fail closed, including
  a key revoked after signing.
- **Replay:** prevented by the one-time ledger. The ledger records both approvals' attributable evidence.
- **Still needed (owner):**
  - Select and provision the production secret interface.
  - Provision the key registry entries.
  - Designate the release/security approver identity.

## AntiBleedGuard minimum-size incompatibility
AntiBleed's global minimum (50.0) is **unchanged**. A governed exception path exists
but is **disabled by a code constant** (`PILOT_MIN_SIZE_EXCEPTION_ENABLED = False`
in `backend/runtime/pilot_min_size_exception.py`); enabling it requires an owner-approved
source change.

When enabled, it relaxes **only** the `trade_size_too_small` rule, and only for a
capability that is:
- minted from a ledger-recorded one-time consumption receipt (one capability per receipt);
- bound to one symbol, a TTL <= 120 s, and size <= min(pilot ceiling, canonical cap);
- MAC'd with a per-process random key (unforgeable from data, dies on restart);
- burned on first use.

Expected-move-vs-cost, net-edge and cooldown rules still apply, and the approved pilot
order records a cooldown. Ordinary orders (no capability, or any other value) are
rejected exactly as before. Evidence: `tests/test_antibleed_pilot_min_size_exception.py`.
`live_micro_pilot_governor._anti_bleed_live_pilot_compatibility` still reports the
CAD 20 pilot as incompatible. That is intended while the exception is disabled.

## Still NOT implemented (release blockers)
- Not connected to the live order submission path; no caller mints capabilities.
- AntiBleed `trade_size` currency is unspecified at the ExecutionGate call site;
  CAD-denominated sizing must be certified before the exception can be enabled.
- Production secret interface and key registry are not provisioned (owner custody); approver RBAC in the UI is not implemented.
- Concurrent-order reservation against the exposure budget; FX handling.
- Ledger assumes a local POSIX filesystem (flock/O_EXCL); networked storage is not certified.
- Brokerage connectivity, R7 coverage, kill-switch verification and legal
  authorization are not certified by unit tests.

**Live trading remains blocked.** `execution_allowed=false`, `live_trading_blocked=true`,
`broker_execution_armed=false`, `advisory_only=true` are unchanged by this branch.
