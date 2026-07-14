# Phase OI-002 - Income Strategy Domain Model

## Objective

Phase OI-002 adds paper-safe domain models for covered calls and cash-secured puts. The phase establishes canonical strategy, collateral, payoff, and risk-profile calculations only.

This phase does not add broker routing, live order creation, execution activation, assignment execution, rolling, scanning, dashboard wiring, or portfolio allocation.

## Scope

Created:

- Covered-call domain model.
- Cash-secured-put domain model.
- Deterministic payoff summaries for both income strategies.
- Additive risk-profile support for both income strategies.
- Focused regression tests for validation, payoff math, collateral, and safety flags.

Explicitly excluded:

- Live broker calls.
- Broker adapter changes.
- Unified execution routing changes.
- Options execution enablement.
- Assignment lifecycle.
- Rolling workflows.
- Opportunity scanning.
- Dashboard/runtime activation.
- Portfolio state mutation or capital reservation.

## Covered-Call Model

The covered-call model validates:

- canonical option contract is present;
- option type is `CALL`;
- short-call intent is explicit;
- underlying quantity and short-call quantity are positive;
- underlying share coverage is sufficient for `short_call_quantity * contract_multiplier`;
- underlying symbol matches the option contract;
- strike, expiry, premium, multiplier, and current underlying price are valid;
- premium is not negative;
- mode is paper-safe only.

The model calculates:

- required covered quantity;
- total premium received;
- maximum profit;
- maximum profit per share;
- breakeven;
- underlying downside exposure;
- assignment exposure;
- capped-upside representation.

Formula summary:

- `required_covered_quantity = short_call_quantity * contract_multiplier`
- `total_premium_received = premium_received * required_covered_quantity`
- `maximum_profit = max(strike - current_underlying_price, 0) * required_covered_quantity + total_premium_received`
- `breakeven = current_underlying_price - premium_received`
- `downside_exposure = max(current_underlying_price - premium_received, 0) * required_covered_quantity`

## Cash-Secured-Put Model

The cash-secured-put model validates:

- canonical option contract is present;
- option type is `PUT`;
- short-put intent is explicit;
- short-put quantity is positive;
- cash collateral evidence is present;
- cash collateral is sufficient for `strike * contract_multiplier * short_put_quantity`;
- underlying symbol matches the option contract;
- strike, expiry, premium, and multiplier are valid;
- premium is not negative;
- mode is paper-safe only.

The model calculates:

- cash collateral required;
- total premium received;
- maximum profit;
- maximum loss / downside exposure;
- breakeven;
- assignment cost basis;
- assignment exposure;
- collateral efficiency.

Formula summary:

- `assigned_quantity = short_put_quantity * contract_multiplier`
- `cash_collateral_required = strike * assigned_quantity`
- `total_premium_received = premium_received * assigned_quantity`
- `maximum_profit = total_premium_received`
- `maximum_loss = cash_collateral_required - total_premium_received`
- `breakeven = strike - premium_received`
- `collateral_efficiency = total_premium_received / cash_collateral_required`

## Collateral Rules

Covered calls require explicit underlying share coverage. The model uses the canonical contract multiplier and does not silently assume 100 shares when the contract supplies another multiplier.

Cash-secured puts require explicit cash collateral evidence. Missing collateral evidence fails closed, even when a theoretical collateral value could be inferred.

No model reserves collateral, allocates capital, mutates positions, or modifies portfolio state.

## Fail-Closed Cases

The models fail closed for:

- missing option contract;
- wrong option type;
- long-option intent;
- zero or negative quantities;
- insufficient share coverage;
- insufficient cash collateral;
- missing collateral evidence;
- symbol mismatch;
- malformed strike, expiry, premium, multiplier, or current price;
- negative premium;
- unsupported live mode;
- malformed contract-like inputs.

Invalid models return `validation_status="FAIL"`, populated `rejection_reasons`, and safe advisory flags.

## Advisory-Only Boundary

Every OI-002 payload preserves:

- `advisory_only=True`
- `execution_allowed=False`
- `live_trading_blocked=True`
- `broker_execution_armed=False`

Phase OI-002 never authorizes live execution, submits orders, cancels orders, arms execution, calls a broker, or changes broker state.

## Tests

Coverage is in:

- `tests/test_oi002_income_strategy_domain_model.py`

The tests cover valid covered calls, valid cash-secured puts, exact/excess/insufficient collateral, option-type rejection, symbol mismatch, malformed inputs, premium validation, payoff calculations, assignment exposure, live-mode rejection, deterministic summaries, advisory-only flags, no broker/execution imports, and regressions for long calls, long puts, and debit spreads.

## Rollback Boundary

Rollback is limited to:

- `backend/options/options_income_strategy_domain.py`
- additive income-strategy branches in `backend/options/option_payoff_engine.py`
- additive income-strategy branches in `backend/options/option_risk_profile_engine.py`
- `tests/test_oi002_income_strategy_domain_model.py`
- this governance document;
- the OI-002 completion-matrix updates.

No broker, execution-routing, runtime, authentication, credential, Desktop, or live-trading files are part of this phase.

## Dependencies For Later Phases

Phase OI-003 can consume the domain builders for paper-safe opportunity scanning and contract selection.

Phase OI-004 can consume validated income strategy summaries for paper short-premium lifecycle states, including expiration and assignment-pending modeling. Assignment execution remains out of scope until separately approved.
