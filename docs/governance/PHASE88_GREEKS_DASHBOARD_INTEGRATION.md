# PHASE 88 - GREEKS DASHBOARD INTEGRATION

## Summary

Phase 88 exposes stored OPTIONS position Greeks and Phase 87 portfolio Greeks aggregation in the existing dashboard summary.

This phase is display-only. It does not calculate Greeks, retrieve broker Greeks, add Black-Scholes logic, change trading logic, or change broker behavior.

## Files Changed

* `scripts/css_live_dashboard.py`
* `tests/test_options_greeks_dashboard.py`
* `docs/governance/PHASE88_GREEKS_DASHBOARD_INTEGRATION.md`

## Dashboard Fields Added

OPTIONS position Greeks display:

* Delta
* Gamma
* Theta
* Vega
* Rho
* Greeks Source

Portfolio Greeks display:

* Net Delta
* Net Gamma
* Net Theta
* Net Vega
* Net Rho
* Greeks Source

## UNKNOWN Rendering Behavior

Missing, `None`, boolean, or otherwise non-numeric Greek values render as:

```text
UNKNOWN
```

Missing Greeks are not rendered as `0.00`.

Invalid or missing Greeks source values render as `UNKNOWN`.

## Portfolio Greeks Display Behavior

The dashboard uses the Phase 87 `portfolio_greeks_from_positions(...)` helper to display aggregate Greeks across open OPTIONS positions.

Non-options positions are excluded from the position Greeks display and do not affect portfolio Greeks.

Positions marked `forced_exit` are excluded from displayed open-position Greeks and portfolio Greeks.

## Tests Run

Required validation:

```text
.venv\Scripts\python.exe -m py_compile scripts/css_live_dashboard.py
.venv\Scripts\python.exe -m pytest tests/test_options_greeks_data_model.py tests/test_portfolio_greeks_aggregation.py tests/test_options_greeks_dashboard.py --maxfail=1
```

## Known Limitations

Phase 88 does not add graphical dashboard widgets, web UI controls, persistence, alerts, or Greeks calculations.

The displayed values depend on Greeks already stored on OPTIONS position dictionaries.

## Explicit Non-Changes

Phase 88 did not change:

* Greeks calculations
* broker adapters or broker Greeks retrieval
* Black-Scholes logic
* trading logic
* broker logic
* live trading behavior
* `.env` or secrets
* `archive/`
* `CLAUDE_FULL_SYSTEM_AUDIT/`
