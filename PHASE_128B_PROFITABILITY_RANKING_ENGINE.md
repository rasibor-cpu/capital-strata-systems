# Phase 128B Profitability Ranking Engine

## Architecture

Phase 128B adds `backend/analytics/profitability_ranking_engine.py`, a read-side analytics engine built directly on the Phase 128A `TradeOutcomeRepository`. The engine loads validated completed-trade outcomes from the warehouse and derives deterministic profitability rankings without creating UI or execution-path side effects.

## Ranking Inputs

The engine consumes the canonical Phase 128A outcome fields and ranks by these grouping dimensions:

- `symbol`
- `asset_class`
- `strategy_id`

The repository remains the source of truth for persistence and base validation.

## Ranking Metrics

Every ranking row includes:

- `trade_count`
- `realized_pnl`
- `win_count`
- `loss_count`
- `win_rate`
- `average_pnl`
- `score`

Wins are trades with positive realized PnL. Losses are trades with negative realized PnL. Flat trades count toward `trade_count` but not `win_count` or `loss_count`.

## Scoring Model

The score favors:

- higher realized PnL;
- higher win rate;
- higher average PnL;
- sufficient trade count for confidence.

The implemented formula is:

```text
confidence = min(trade_count / minimum_trade_count, 1.0)
score = ((realized_pnl * 0.60) + (win_rate * 100.0 * 0.25) + (average_pnl * 0.15)) * confidence
```

This preserves profitability as the dominant factor while reducing confidence for thin samples.

## Symbol Policy Helpers

`preferred_symbols()` returns symbols with enough trades and a positive score.

`restricted_symbols()` returns symbols with too few trades or scores at or below the restricted-score threshold. Restricted symbols are sorted from weakest to strongest so the riskiest symbols appear first.

## Fail-Closed Design

The engine raises `ProfitabilityRankingEngineError` when:

- the repository cannot load valid warehouse data;
- ranking data is missing or malformed;
- limits are non-positive;
- `minimum_trade_count` is non-positive.

Empty warehouses return empty rankings. The engine does not invent rows when there are no completed outcomes.

## Validation Evidence

Validation commands for Phase 128B:

- `git diff --check`
- `python -m pytest tests/test_trade_outcome_repository.py tests/test_profitability_ranking_engine.py -v`
- `python -c "from backend.analytics import ProfitabilityRankingEngine; print('PHASE128B_IMPORT_OK')"`
