# Phase OI-003 - Income Opportunity Scan and Contract Selection

## Objective

Phase OI-003 adds deterministic, paper-safe opportunity scanning and contract selection for covered calls and cash-secured puts.

This phase consumes the Phase OI-002 income strategy domain builders. It does not add lifecycle management, assignment execution, rolling, order routing, broker calls, live options authority, automatic capital allocation, dashboard activation, or production activation.

## Scanner Architecture

The scanner is implemented in:

- `backend/options/options_income_opportunity_scanner.py`

It accepts canonical option contracts or deterministic in-memory mapping fixtures, evaluates candidates against explicit thresholds, builds the corresponding OI-002 strategy model for accepted candidates, and returns advisory-only candidate summaries.

The scanner is read-only. It does not mutate option contracts, portfolio state, cash balances, positions, broker state, or execution state.

## Accepted Fields

Candidate summaries include:

- strategy type;
- underlying symbol;
- canonical option contract identity and serialized contract;
- option side and type;
- strike;
- expiry;
- DTE;
- delta;
- bid;
- ask;
- midpoint;
- spread and spread percentage;
- volume;
- open interest;
- moneyness;
- premium per contract;
- total premium;
- annualized premium yield;
- assignment exposure;
- collateral required;
- collateral efficiency for cash-secured puts;
- underlying coverage required for covered calls;
- validation status;
- rejection reasons;
- deterministic ranking score;
- OI-002 strategy summary;
- advisory-only safety flags.

## Covered-Call Filters

Covered-call scanning requires:

- `CALL` contracts only;
- matching underlying symbol;
- supported contract multiplier;
- positive bid, ask, and midpoint;
- DTE inside the configured range;
- call delta inside the configured range;
- bid and midpoint above the configured minimum premium;
- bid/ask spread below the configured maximum;
- volume and open interest above configured liquidity minimums;
- sufficient underlying share coverage;
- paper-safe mode only.

Rejected covered-call candidates include deterministic reasons such as:

- `OPTION_TYPE_MUST_BE_CALL`
- `INSUFFICIENT_UNDERLYING_COVERAGE`
- `INVALID_DTE`
- `DELTA_OUTSIDE_RANGE`
- `MISSING_PRICE_FIELDS`
- `EXCESSIVE_SPREAD`
- `LOW_VOLUME`
- `LOW_OPEN_INTEREST`
- `UNDERLYING_SYMBOL_MISMATCH`
- `MALFORMED_MULTIPLIER`
- `UNSUPPORTED_LIVE_MODE`
- `OI002_BUILDER_REJECTED`

## Cash-Secured-Put Filters

Cash-secured-put scanning requires:

- `PUT` contracts only;
- matching underlying symbol;
- supported contract multiplier;
- positive bid, ask, and midpoint;
- DTE inside the configured range;
- put delta inside the configured range;
- bid and midpoint above the configured minimum premium;
- bid/ask spread below the configured maximum;
- volume and open interest above configured liquidity minimums;
- explicit cash collateral evidence;
- sufficient cash collateral;
- paper-safe mode only.

Rejected cash-secured-put candidates include deterministic reasons such as:

- `OPTION_TYPE_MUST_BE_PUT`
- `INSUFFICIENT_CASH_COLLATERAL`
- `MISSING_COLLATERAL_EVIDENCE`
- `INVALID_DTE`
- `DELTA_OUTSIDE_RANGE`
- `MISSING_PRICE_FIELDS`
- `EXCESSIVE_SPREAD`
- `LOW_VOLUME`
- `LOW_OPEN_INTEREST`
- `UNDERLYING_SYMBOL_MISMATCH`
- `MALFORMED_MULTIPLIER`
- `UNSUPPORTED_LIVE_MODE`
- `OI002_BUILDER_REJECTED`

## Ranking Methodology

Covered-call ranking uses a deterministic weighted score from:

- delta alignment;
- annualized premium yield;
- liquidity;
- spread quality;
- preferred DTE alignment;
- moneyness suitability.

Cash-secured-put ranking uses a deterministic weighted score from:

- delta alignment;
- collateral efficiency;
- annualized premium yield;
- liquidity;
- spread quality;
- preferred DTE alignment.

All thresholds are configured through the immutable `IncomeScannerConfig` model.

## Deterministic Tie-Breaking

Accepted candidates are sorted by:

1. ranking score descending;
2. expiry ascending;
3. strike ascending;
4. option symbol ascending;
5. original source index.

This produces stable output across repeated runs.

## OI-002 Integration

Every accepted covered-call candidate must validate through `build_covered_call`.

Every accepted cash-secured-put candidate must validate through `build_cash_secured_put`.

If the OI-002 builder fails, the OI-003 scanner rejects the candidate and carries `OI002_BUILDER_REJECTED` plus the builder rejection reasons. The original canonical option contract object is preserved for accepted candidates.

## Advisory-Only Boundary

Every OI-003 payload preserves:

- `advisory_only=True`
- `execution_allowed=False`
- `live_trading_blocked=True`
- `broker_execution_armed=False`

Phase OI-003 never authorizes live execution, submits orders, cancels orders, arms execution, calls a broker, retrieves live market data, or changes broker state.

## Explicit Exclusions

Out of scope:

- lifecycle states;
- assignment execution;
- rolling;
- order routing;
- broker adapters;
- live market-data calls;
- options execution enablement;
- automatic capital allocation;
- dashboard/runtime activation;
- production certification.

## Tests

Coverage is in:

- `tests/test_oi003_income_opportunity_scanner.py`

The suite covers valid candidates, deterministic ranking, preferred DTE, preferred delta, premium yield, collateral efficiency, spread quality, liquidity, rejection cases, OI-002 builder failure, stable tie-breaking, JSON-safe summaries, advisory-only flags, malformed rows, empty chains, and no mutation of source rows.

## Rollback Boundary

Rollback is limited to:

- `backend/options/options_income_opportunity_scanner.py`
- `tests/test_oi003_income_opportunity_scanner.py`
- this governance document;
- the OI-003 completion-matrix updates.

No broker, execution-routing, runtime server, Desktop, credential, authentication, or live-trading files are part of this phase.

## Dependencies For OI-004

Phase OI-004 can consume accepted OI-003 candidates and their attached OI-002 strategy summaries to implement paper income lifecycle states.

OI-004 must remain paper-safe and must not execute assignment, rolling, broker orders, or live trading without a separately approved phase.
