# Phase 128A Trade Outcome Warehouse

## Architecture

Phase 128A adds a backend analytics repository at `backend/analytics/trade_outcome_repository.py`. The module owns canonical completed-trade outcome persistence and a read-side analytics adapter. It intentionally stays outside UI code and execution governance code.

The core components are:

- `TradeOutcomeRecord`: immutable canonical data model for a completed trade outcome.
- `TradeOutcomeRepository`: fail-closed JSON repository with creation, loading, appending, duplicate prevention, and aggregation operations.
- `persist_completed_trade_outcome`: adapter/hook function for a canonical completed-trade close path.
- `build_trade_outcome_analytics_adapter`: analytics adapter exposing top/worst rankings.

## Data Model

Each completed outcome must contain exactly the canonical fields below, with string fields required to be non-empty and numeric fields coerced to `float`:

```json
{
  "trade_id": "str",
  "timestamp_open": "str",
  "timestamp_close": "str",
  "symbol": "str",
  "asset_class": "str",
  "entry_price": 0.0,
  "exit_price": 0.0,
  "quantity": 0.0,
  "realized_pnl": 0.0,
  "holding_duration_seconds": 0.0,
  "strategy_id": "str",
  "market_regime": "str",
  "broker": "str"
}
```

## Persistence Model

Persistence is JSON-file based. Storage is created with an empty JSON list when absent, then every load validates that:

- the file exists for load operations;
- the root JSON value is a list;
- every item matches the canonical model;
- every `trade_id` is unique.

Appends perform a load, reject duplicate `trade_id` values, append the normalized record, and write through an atomic temporary-file replacement.

## Aggregation Model

The repository exposes deterministic realized-PnL aggregations by:

- `symbol`;
- `asset_class`;
- `strategy_id`.

Each aggregate row includes the group key, `trade_count`, and summed `realized_pnl`. Rows are sorted by the group key for stable testable output.

The analytics adapter exposes:

- `top_symbols`;
- `worst_symbols`;
- `top_asset_classes`;
- `top_strategies`.

Rankings are ordered by aggregate realized PnL and capped by a positive `limit`.

## Integration Decision

A safe canonical completed-trade close path was not clearly identifiable for all asset classes. The repository therefore does **not** force a risky direct execution integration in this phase.

The integration point is the `persist_completed_trade_outcome(repository, outcome)` adapter/hook in `backend/analytics/trade_outcome_repository.py`. A future canonical close path should call this hook immediately after final realized PnL is computed and before the close result is considered durable.

## Fail-Closed Design

The repository raises explicit exceptions instead of silently returning partial or invented analytics:

- `TradeOutcomeRepositoryError` for invalid storage, invalid records, missing storage on load, invalid limits, and persistence failures.
- `DuplicateTradeOutcomeError` for duplicate `trade_id` values in storage or on append.

This preserves fail-closed behavior: completed-trade analytics must either be valid and durable or fail explicitly.

## Validation Evidence

Validation performed before commit:

- `git diff --check`
- `python -m pytest tests/test_trade_outcome_repository.py`
- `python -m pytest tests`

The full test suite was run as requested.
