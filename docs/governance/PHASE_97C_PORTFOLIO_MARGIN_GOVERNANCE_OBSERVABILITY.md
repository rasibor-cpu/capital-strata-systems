# PHASE 97C: PORTFOLIO MARGIN GOVERNANCE OBSERVABILITY

## Purpose and Scope
The Portfolio Margin Governance Observability phase establishes the standardized presentation layer for portfolio-level margin visibility within the CSS institutional dashboard ecosystem.

This phase introduces:
1. `PortfolioMarginSnapshot` as the canonical dataclass.
2. `PortfolioMarginSummaryBuilder` to map snapshot data into human-readable governance metrics.

## Observability Policy (Read-Only)
The components introduced in Phase 97C are exclusively for read-only visibility.

- No execution decisions are affected.
- No broker routing paths are modified.
- No risk gates, including `ExecutionGate` and `AntiBleedGuard`, are altered.
- `TradeDecisionOrchestrator` remains untouched.
- No synthetic values or direct broker calls are made from the presentation layer.

## Institutional Margin Classifications
The mapping defines the translation of standard `MarginState` enums to executive dashboard banners:

*   **NORMAL**: "Portfolio Margin Healthy"
*   **WARNING**: "Portfolio Margin Warning"
*   **RESTRICTED**: "Margin Restrictions Active"
*   **CRITICAL**: "Margin Stress Detected"
*   **LIQUIDATION_RISK**: "Immediate Margin Intervention Required"

## Security & Canonical Contract
By enforcing the use of the `PortfolioMarginSnapshot` dataclass, the application ensures that the dashboard cannot access unverified dictionary data or invoke broker plugins directly. The snapshot represents the final pre-calculated view of risk state, enforcing the separation between risk determination and interface display.
