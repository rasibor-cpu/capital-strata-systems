# PHASE 89 - OPTIONS STRATEGY CLASSIFICATION ENGINE

## Summary

Phase 89 implements a safe, display/data-model-only options strategy classification engine for existing OPTIONS positions.

The implementation classifies single-leg option symbols already present in runtime position data. It does not infer multi-leg strategies, execute multi-leg trades, create broker orders, calculate Greeks, or change live trading behavior.

## Files Changed

* `scripts/css_live_dashboard.py`
* `tests/test_options_strategy_classification.py`
* `docs/governance/PHASE89_OPTIONS_STRATEGY_CLASSIFICATION_ENGINE.md`

## Classification Rules

The helper `parse_option_symbol(...)` reads dashboard option symbols with hyphen-delimited fields, including formats such as:

```text
AAPL-C-175
SPY-P-500
```

Rules:

* `C` classifies as `LONG_CALL`.
* `P` classifies as `LONG_PUT`.
* If the option type cannot be parsed, the strategy is `UNKNOWN_OPTIONS_STRATEGY`.
* Multi-leg strategies are not inferred in Phase 89.
* Strategy fields are attached to OPTIONS positions only.

Strategy fields:

```python
{
    "options_strategy": "LONG_CALL",
    "strategy_family": "SINGLE_LEG",
    "strategy_confidence": "HIGH",
}
```

Unknown strategy fields:

```python
{
    "options_strategy": "UNKNOWN_OPTIONS_STRATEGY",
    "strategy_family": "UNKNOWN",
    "strategy_confidence": "LOW",
}
```

## Supported Strategies

Phase 89 supports:

* `LONG_CALL`
* `LONG_PUT`
* `UNKNOWN_OPTIONS_STRATEGY`

Future-compatible placeholders are declared for:

* `COVERED_CALL`
* `CASH_SECURED_PUT`
* `BULL_CALL_SPREAD`
* `BEAR_CALL_SPREAD`
* `BULL_PUT_SPREAD`
* `BEAR_PUT_SPREAD`
* `IRON_CONDOR`
* `IRON_BUTTERFLY`
* `STRADDLE`
* `STRANGLE`
* `CALENDAR_SPREAD`
* `DIAGONAL_SPREAD`

## Unknown Behavior

Malformed or incomplete symbols that do not expose a parseable `C` or `P` option type classify as:

```text
UNKNOWN_OPTIONS_STRATEGY
```

The unknown strategy family is `UNKNOWN` and confidence is `LOW`.

## Tests Run

Required validation:

```text
.venv\Scripts\python.exe -m py_compile scripts/css_live_dashboard.py
.venv\Scripts\python.exe -m pytest tests/test_options_greeks_data_model.py tests/test_portfolio_greeks_aggregation.py tests/test_options_greeks_dashboard.py tests/test_options_strategy_classification.py --maxfail=1
```

## Known Limitations

Phase 89 does not infer or manage multi-leg strategies.

The classifier uses currently available symbol and position fields only. It does not inspect holdings, broker accounts, Greeks, margin, or option-chain data.

## Explicit Non-Changes

Phase 89 did not change:

* multi-leg execution
* broker order creation
* broker logic
* live trading behavior
* Greeks calculations
* Black-Scholes logic
* `.env` or secrets
* `archive/`
* `CLAUDE_FULL_SYSTEM_AUDIT/`
