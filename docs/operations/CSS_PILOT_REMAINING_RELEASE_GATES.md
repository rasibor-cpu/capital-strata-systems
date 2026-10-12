# CSS pilot — release-gate closure register

**Status:** review candidate only; live-order execution prohibited until evidence proves every mandatory gate passed.

## Confirmed from reviewed candidate
- `backend/config/order_limit_config.py` defines CAD 20 per-parent, CAD 40 total, 2 concurrent, CAD 2 daily loss and CAD 4 session loss, 10 orders/session. These are configured ceilings, **not proof of live-path enforcement**.
- `backend/runtime/pilot_exposure_reservation.py`: SQLite durable reservation design; selected unit tests passed.
- `backend/runtime/controlled_pilot_readiness.py`: read-only, fail-closed aggregation; no order submission.
- `engine/execution/execution_gate.py`: governed pilot exception is CAD-only; non-CAD calls reject rather than normalize automatically.
- `backend/runtime/pilot_min_size_exception.py`: `PILOT_MIN_SIZE_EXCEPTION_ENABLED = False`. Do not toggle pending full certification.
- Independent reviewer Diana Whyte was designated and reportedly accepted the role; signing keys absent, no actual production approval signed.
- Isolated extended regression on revision `7b527d24`: 105 passed, 1 skipped. Later governance commits must be rechecked for final freeze.

## Mandatory evidence yet to obtain
| Gate | Evidence needed | State |
|---|---|---|
| Cross-asset risk | Validate effective CAD cash commitment, commissions, leverage-adjusted notional, contract multiplier, max-loss, FX rates and stale prices for crypto/FX/futures/options; unsupported/unbounded positions NO-GO | NOT CERTIFIED |
| Atomic portfolio budget | Test simultaneous FX and derivative orders plus pending/cancel/partial-fill events against 20/40, including reservations after crash/restart | UNIT TESTS ONLY |
| AntiBleed + R7 | Full end-to-end integration with CAD normalization and unchanged profitability/cooldown rules | NOT CERTIFIED |
| Broker readiness | Per-broker accounts, supported instruments, read-only balances, minimum sizing, risk disclosures, order route, kill-switch, no order mutation during checks | NOT CERTIFIED |
| Independent security | Diana or independently verified alternative plus sponsor: distinct keys, independent credentials, role validation, signatures bound to frozen candidate and expiry; no secret sharing | NOT ENROLLED |
| Endurance | Genuine real-host continuous 72-hour safety evidence and independent manifest, or explicit formal governance-approved change to release requirement; do not relabel missing proof as PASS | NOT CERTIFIED |
| Regression | Candidate-specific full tests, CI, independent security/merge/release review | NOT COMPLETE |
| Production activation | Approved runtime identity and signer/candidate, preflight, rollback/kill-switch rehearsal, explicit final operator decision | NO-GO |

## Safe next activity
Run focused read-only repository tests and check CI. Do not alter safety flags, enable exception, connect production broker order submission, merge a draft into operational main, or record orders without all mandatory gates.

**Scope:** CAD 20 individual trial ceiling; CAD 40 global aggregate; max 2 concurrent parents; tighter limits can be imposed inside these maxima. All four asset classes are intended for certification, but actual instruments require individually certified risk envelopes.
