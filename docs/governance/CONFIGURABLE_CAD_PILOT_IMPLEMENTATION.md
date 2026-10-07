# Configurable governed micro-pilot — implementation stage 2 (hardening)

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
| Tamper evidence | HMAC-SHA256 over canonical SHA-256 profile digest (>=32-byte key from secret store); re-verified and re-validated on every evaluation | `test_signature_required_and_tamper_evident` |
| Replay / duplicate / restart reuse | `PilotAuthorizationLedger`: atomic `O_EXCL` claim per approval, `flock`-serialised, fsync'd, SHA-256 hash-chained journal; revocation burns the claim; tampered journal fails closed | `tests/test_pilot_authorization_ledger.py` (incl. 6-process race) |
| Evaluation never raises | any unexpected error -> `PILOT_BLOCKED_EVALUATION_ERROR` | `test_malformed_inputs_fail_closed_without_raising` |

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
- Signing-key custody/rotation, approver RBAC and dual control are not implemented.
- Concurrent-order reservation against the exposure budget; FX handling.
- Ledger assumes a local POSIX filesystem (flock/O_EXCL); networked storage is not certified.
- Brokerage connectivity, R7 coverage, kill-switch verification and legal
  authorization are not certified by unit tests.

**Live trading remains blocked.** `execution_allowed=false`, `live_trading_blocked=true`,
`broker_execution_armed=false`, `advisory_only=true` are unchanged by this branch.
