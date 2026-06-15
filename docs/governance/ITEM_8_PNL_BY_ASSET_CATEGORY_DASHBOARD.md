# Item 8 PnL by Asset Category Dashboard

## Scope

Item 8 adds dashboard visibility for profit and loss grouped by asset category.

This phase is reporting and visibility only. It does not change trading behavior, execution logic, broker behavior, risk behavior, margin behavior, strategy logic, position creation, exit logic, or credential handling.

## Data Sources Reviewed

Reviewed active and transitional PnL sources:

| Source | File | Role |
| ------ | ---- | ---- |
| Dashboard MTM realized PnL maps | `scripts/css_live_dashboard.py` | Active dashboard realized PnL maps for current paper/runtime dashboard categories |
| Dashboard MTM open positions | `scripts/css_live_dashboard.py` | Active open-position source for floating/unrealized dashboard PnL |
| MarkToMarketEngine | `scripts/css_live_dashboard.py` | Runtime dashboard position and floating PnL authority |
| PnL observer compatibility mirror | `scripts/css_live_dashboard.py` | Compatibility/accounting observer retained for reconciliation |
| PnL tracker | `engine/performance/pnl_tracker.py` | Runtime equity/drawdown tracker |
| Canonical PnL adapter | `engine/ledger/pnl_snapshot_adapter.py` | Ledger-backed canonical PnL comparison/diagnostic contract |
| Dashboard summary builder | `dashboard/runtime/summary_builders/pnl_summary_builder.py` | Presentation-layer PnL summary builder with asset realized/unrealized maps |
| Persistence snapshot contract | `backend/app/persistence/services/pnl_runtime_service.py` and `backend/app/persistence/repositories/pnl_snapshot_repository.py` | Runtime snapshot persistence path |

## Aggregation Approach

Added display-only aggregation helpers in:

```text
scripts/css_live_dashboard.py
```

New helpers:

```text
normalize_asset_category(...)
current_realized_pnl_maps_by_asset_category()
aggregate_pnl_by_asset_category(...)
pnl_by_asset_category_dashboard_lines(...)
```

Aggregation behavior:

- realized PnL is summed from dashboard realized PnL maps by category
- unrealized PnL is summed from active open positions using `unrealized_pnl` when present and `floating` as the dashboard fallback
- total category PnL equals realized plus unrealized
- forced-exit positions are excluded from open unrealized category PnL
- category names are normalized to uppercase
- unknown or blank categories are displayed as `UNKNOWN`
- categories are derived dynamically from provided maps and positions

## Dashboard Integration

The dashboard now prints:

```text
=== PNL BY ASSET CATEGORY ===
<CATEGORY> Open <count> | Realized <value> | Unrealized <value> | Total <value>
=== END PNL BY ASSET CATEGORY ===
```

This panel is emitted in:

- `render_trade_dashboard_summary()`
- the main live dashboard cycle PnL summary

The display is read-only and does not participate in trade decisions.

## Future Category Support

The aggregation layer is dynamic. Future categories can appear through:

- open positions with a new `asset_class`
- realized PnL maps supplied through the extension hook `asset_category_realized_pnl_maps`

No dashboard-rendering redesign is required for categories such as:

- `STOCKS`
- `EQUITIES`
- `ETFS`
- `FIXED_INCOME`
- `COMMODITIES`
- any future normalized category name

## Tests Added

Created:

```text
tests/test_pnl_by_asset_category_dashboard.py
```

Coverage:

- category aggregation combines realized, unrealized, and total PnL correctly
- empty categories render safely
- unknown categories are handled safely
- dashboard rendering receives aggregated values
- future categories render without UI changes

Updated:

```text
tests/test_options_greeks_dashboard.py
```

The existing dashboard summary regression now validates the `PNL BY ASSET CATEGORY` panel.

## Tests Executed

Compile validation:

```text
.\.venv\Scripts\python.exe -m py_compile scripts\css_live_dashboard.py tests\test_pnl_by_asset_category_dashboard.py tests\test_options_greeks_dashboard.py
```

Result:

```text
PASS
```

Dashboard PnL and summary tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_pnl_by_asset_category_dashboard.py tests\test_options_greeks_dashboard.py -q
```

Result:

```text
10 passed
```

Related PnL regression tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\dashboard\test_summary_builders.py tests\dashboard\test_pnl_canonical_parity.py tests\engine\test_pnl_snapshot_adapter.py tests\test_pnl_snapshot_persistence_contract.py -q
```

Result:

```text
19 passed
```

Warnings were existing `datetime.utcnow()` deprecation warnings in persistence service tests.

## Certification Findings

Certification status:

```text
PASS
```

CSS now exposes read-only dashboard PnL visibility by dynamic asset category. The implementation supports current and future asset classes without category-specific UI branches and without changing trading, execution, broker, risk, margin, or strategy behavior.

## Boundaries Preserved

| Boundary | Status |
| -------- | ------ |
| Trading behavior changed | No |
| Execution logic changed | No |
| Broker behavior changed | No |
| Risk behavior changed | No |
| Strategy logic changed | No |
| Dashboard display changed | Yes, visibility-only |
| Future categories supported | Yes |
