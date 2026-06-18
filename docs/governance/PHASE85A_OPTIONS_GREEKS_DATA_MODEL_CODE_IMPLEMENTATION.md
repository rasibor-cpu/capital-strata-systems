# PHASE 85A - OPTIONS GREEKS DATA MODEL CODE IMPLEMENTATION

## Summary

Phase 85A implements the canonical Options Greeks data model in the dashboard runtime position flow.

The implementation is intentionally limited to data model support for OPTIONS positions. It does not add Greeks calculations, dashboard rendering, broker Greeks retrieval, or live trading behavior changes.

## Files Changed

* `scripts/css_live_dashboard.py`
* `tests/test_options_greeks_data_model.py`
* `docs/governance/PHASE85A_OPTIONS_GREEKS_DATA_MODEL_CODE_IMPLEMENTATION.md`

## Correct Position Authority

The authoritative runtime open-position store is `MarkToMarketEngine.self.positions`.

The position creation authority is `MarkToMarketEngine.register_position(...)`.

No new position authority was created.

## Greeks Model Implemented

Canonical OPTIONS Greeks fields:

```python
{
    "delta": None,
    "gamma": None,
    "theta": None,
    "vega": None,
    "rho": None,
    "greeks_source": "UNKNOWN",
}
```

Valid `greeks_source` values:

* `BROKER`
* `MARKET_DATA`
* `BLACK_SCHOLES`
* `UNKNOWN`

Unknown Greeks remain `None`, not `0.0`.

Invalid `greeks_source` values normalize to `UNKNOWN`.

## Backward Compatibility Behavior

The following helpers were added:

* `default_option_greeks()`
* `normalize_option_greeks(...)`
* `attach_default_greeks_to_option_position(...)`

Legacy OPTIONS position dictionaries missing Greeks fields can be normalized safely through the helper path without raising `KeyError`.

Non-options positions are not modified and do not receive Greeks fields.

## Closed-Trade Ledger Behavior

`append_closed_trade_ledger(...)` preserves normalized Greeks fields for OPTIONS records when Greeks fields are present at close time.

Non-options closed-trade ledger records retain their existing shape.

## NewPosition Limitation

`NewPosition(...)` remains a conversion path into `compute_portfolio_snapshot(...)`, not the runtime position authority.

Phase 85A does not force Greeks into `NewPosition(...)` because the current dashboard conversion path only supplies fields supported by the accounting snapshot model. Greeks propagation into that model is deferred until the accounting model explicitly supports it.

## Session Recovery Limitation

`SessionRecoveryEngine.save_state(...)` and `SessionRecoveryEngine.load_state(...)` currently restore realized PnL maps and `position_counter`.

They do not persist or restore open `MarkToMarketEngine.self.positions`. Therefore, open-position Greeks restoration is not applicable in Phase 85A and remains future persistence work.

## Tests Run

Required validation:

```text
python -m py_compile scripts/css_live_dashboard.py
python -m pytest tests/test_options_greeks_data_model.py --maxfail=1
```

## Explicit Non-Changes

Phase 85A did not change:

* dashboard rendering
* broker adapters or broker Greeks retrieval
* Black-Scholes calculations
* live trading behavior
* `.env` or secrets
* `archive/`
* `CLAUDE_FULL_SYSTEM_AUDIT/`
