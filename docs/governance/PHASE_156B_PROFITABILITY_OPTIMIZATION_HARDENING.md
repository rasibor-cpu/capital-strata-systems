# Phase 156B - Profitability Optimization Hardening

## Objective

Phase 156B improves advisory profitability optimization so trade selection, allocation, position sizing, and strategy-promotion recommendations prefer high-quality, proven, capital-efficient opportunities.

This phase is optimization/advisory only. It does not authorize trades, arm broker execution, enable live trading, or bypass any safety control.

## Canonical Profitability Optimization Score

The canonical score is produced by `backend.analytics.profitability_optimization_score` and considers:

- expected edge
- win rate
- drawdown penalty
- realized PnL reliability
- trade frequency quality
- asset-class concentration penalty
- confidence calibration
- capital efficiency

Missing evidence is scored conservatively. Missing data cannot produce an aggressive recommendation.

## Integration

The score is exposed through `ProfitabilityOptimizer` as `profitability_optimization_rankings`.

`CapitalAllocationEngine` prefers `profitability_optimization_score` when callers provide it, while preserving the existing legacy `score` field for compatibility.

`StrategyPromotionEngine` also prefers `profitability_optimization_score` when present. Promotion output remains recommendation-only and includes no execution authority.

## Governance Boundary

The Phase 156B score and all derived rankings are advisory only:

- `advisory_only = true`
- `execution_allowed = false`
- `can_authorize_trade = false`

The optimizer never replaces or bypasses:

- CSS Unified Trade Gate
- AntiBleedGuard
- margin and capital limits
- live-mode governance
- broker credential diagnostics
- LiveExecutionAuthority
- broker execution controls

## Safety Result

Profitability optimization may reorder recommendations, reduce allocations for unreliable opportunities, and demote weak opportunities. It must never grant execution permission or alter live-mode broker controls.
