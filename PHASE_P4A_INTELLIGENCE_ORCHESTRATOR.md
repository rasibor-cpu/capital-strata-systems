# P4A Intelligence Orchestrator

## Scope

Implemented a canonical, recommendation-only intelligence orchestrator that coordinates the existing analytics engines without broker execution, persistence changes, UI changes, or RBAC changes.

## Inputs

- `trade_id`
- `symbol`
- `asset_class`
- `direction`
- `strategy`
- `current_price`
- `market_snapshot`
- `portfolio_snapshot`

## Orchestration

The orchestrator consults:

- `MarketRegimeEngine`
- `StrategyIntelligenceEngine`
- `CapitalAllocationEngine`
- `AdaptivePositionSizingEngine`
- `PortfolioCorrelationEngine`
- `ConcentrationGuard`
- `AdaptiveExitEngine`

## Output

The resulting `IntelligenceDecision` contains:

- `market_regime`
- `strategy_score`
- `allocation`
- `position_size`
- `portfolio_risk`
- `concentration_score`
- `exit_plan`
- `overall_confidence`
- `decision`
- `diagnostics`

## Decision Rules

- `ALLOW`
- `REDUCE_SIZE`
- `DEFER`
- `BLOCK`

The orchestrator is fail-closed and deterministic.