# PHASE 87 - PORTFOLIO GREEKS AGGREGATION

## Summary

Phase 87 implements portfolio-level aggregation of stored per-position Greeks for open OPTIONS positions.

The implementation aggregates only data already present on runtime position dictionaries. It does not calculate Greeks, retrieve Greeks from brokers, add Black-Scholes logic, alter dashboard rendering, or change live trading behavior.

## Files Changed

* `scripts/css_live_dashboard.py`
* `tests/test_portfolio_greeks_aggregation.py`
* `docs/governance/PHASE87_PORTFOLIO_GREEKS_AGGREGATION.md`

## Aggregation Rules

The helper `portfolio_greeks_from_positions(positions)` returns:

```python
{
    "net_delta": float | None,
    "net_gamma": float | None,
    "net_theta": float | None,
    "net_vega": float | None,
    "net_rho": float | None,
    "greeks_source": str,
}
```

Rules:

* Only OPTIONS positions are included.
* Positions marked `forced_exit` are ignored.
* Non-options positions do not affect portfolio Greeks.
* Numeric Greek values are summed.
* `None` and non-numeric Greek values are ignored.
* If no numeric value exists for a Greek, that net Greek is `None`.
* If at least one numeric value exists for a Greek, that net Greek is the numeric sum.

## Source Behavior

`greeks_source` behavior:

* `UNKNOWN` when no usable Greek values exist.
* `MIXED` when more than one normalized source contributes numeric values.
* Otherwise the single normalized contributing source is returned.

Invalid or missing source values normalize safely to `UNKNOWN`.

## Tests Run

Required validation:

```text
.venv\Scripts\python.exe -m py_compile scripts/css_live_dashboard.py
.venv\Scripts\python.exe -m pytest tests/test_options_greeks_data_model.py tests/test_portfolio_greeks_aggregation.py --maxfail=1
```

## Known Limitations

Phase 87 does not persist portfolio Greeks and does not render portfolio Greeks on the dashboard.

The aggregation depends on Greeks fields already stored on OPTIONS position dictionaries. It does not synthesize missing per-position values.

## Explicit Non-Changes

Phase 87 did not change:

* Greeks calculations
* broker adapters or broker Greeks retrieval
* Black-Scholes logic
* dashboard rendering
* live trading behavior
* `.env` or secrets
* `archive/`
* `CLAUDE_FULL_SYSTEM_AUDIT/`
