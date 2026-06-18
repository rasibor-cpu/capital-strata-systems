# Item 7 Real-Time Stock Alerts Runtime Integration

## Scope

Item 7 integrates the existing Stock Alerts Information Module framework into CSS runtime visibility through an advisory-only diagnostics path.

This phase is informational only. It does not create trading signals, automatic entries, automatic exits, strategy changes, RiskGovernor changes, ExecutionGate changes, broker execution changes, margin changes, dashboard redesign, or governance-authority changes.

## Framework Reviewed

Reviewed:

```text
docs/information/STOCK_ALERTS_INFORMATION_MODULE_FRAMEWORK.md
```

The framework defines:

- informational-only stock alerts
- alert types such as price threshold crosses, intraday move, volume spike, gap up/down, new high/low, watchlist signal, risk warning, and abnormal-data warning
- severity levels `INFO`, `WATCH`, `WARNING`, and `CRITICAL`
- runtime event/audit considerations
- dashboard display considerations
- explicit execution and risk boundaries

## Runtime Gap Identified

Before Item 7, the stock-alert framework existed as documentation only.

Missing runtime pieces:

- no canonical advisory alert schema
- no deterministic alert evaluator
- no runtime diagnostics visibility path
- no tests proving alerts remain advisory-only

## Integration Approach

Created:

```text
engine/information/stock_alerts.py
engine/information/__init__.py
```

The new information module provides:

- `StockAlertRule`
- `generate_stock_alerts(...)`
- deterministic alert dictionaries with `event_type="STOCK_ALERT"`
- severity normalization
- `advisory_only=True`
- `execution_authority="NONE"`

Integrated into:

```text
engine/engine_loop.py
```

Runtime visibility path:

```text
EngineLoop.stock_alert_rules
-> generate_stock_alerts(...)
-> EngineLoop.stock_alert_records
-> diagnostics["stock_alerts"]
-> EngineLoop.summary()
```

Default behavior:

```text
stock_alert_rules = []
```

With no configured rules, no alerts are generated and runtime trading flow remains unchanged.

## Advisory-Only Controls

Stock alerts are emitted only as runtime diagnostics.

Alerts do not:

- create signals
- create entries
- create exits
- block trades
- approve trades
- alter RiskGovernor state
- alter ExecutionGate state
- call broker APIs
- route orders
- mutate strategy behavior
- mutate margin behavior

Alert payloads explicitly include:

```text
advisory_only=True
execution_authority="NONE"
```

## Runtime Visibility

Operators and future dashboards can read alert visibility through:

```text
EngineLoop.summary()["diagnostics"]["stock_alerts"]
```

This is a read-only information path. It is not a trading authority.

## Tests Added

Created:

```text
tests/engine/test_stock_alerts_runtime_integration.py
```

Coverage:

- alerts generated correctly
- alerts visible to runtime consumers through diagnostics
- alerts do not alter trade decisions
- alerts do not alter RiskGovernor behavior
- alerts do not alter ExecutionGate behavior

## Tests Executed

Compile validation:

```text
.\.venv\Scripts\python.exe -m py_compile engine\information\__init__.py engine\information\stock_alerts.py engine\engine_loop.py tests\engine\test_stock_alerts_runtime_integration.py
```

Result:

```text
PASS
```

Stock alert integration tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\engine\test_stock_alerts_runtime_integration.py -q
```

Result:

```text
5 passed
```

Relevant engine/risk/execution regression tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\engine\test_engine_loop_regime_gate_wiring.py tests\engine\test_risk_governor.py tests\test_margin_trade_gate_enforcement_integration.py -q
```

Result:

```text
18 passed
```

Warnings were existing `datetime.utcnow()` deprecation warnings in pre-existing RegimeGate telemetry and AntiBleedGuard code. The stock-alert integration uses timezone-aware UTC timestamps.

## Certification Findings

Item 7 certification result:

```text
PASS
```

The Stock Alerts Information Module is now available to runtime consumers through a controlled diagnostics path. Alerts are deterministic, advisory-only, and explicitly separated from execution authority.

## Boundaries Preserved

| Boundary | Status |
| -------- | ------ |
| Trading signals changed | No |
| ExecutionGate changed | No |
| RiskGovernor changed | No |
| Broker behavior changed | No |
| Margin behavior changed | No |
| Strategy logic changed | No |
| Dashboard redesign | No |
| Advisory-only preserved | Yes |

## Remaining Notes

This phase does not connect to live market-data providers, persist runtime alert events, or add dashboard rendering panels. Those remain future approved phases.
