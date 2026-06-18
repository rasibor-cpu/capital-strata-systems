# PHASE 97F: PORTFOLIO MARGIN TREND ANALYTICS FRAMEWORK

## Objective
Build a read-only analytics layer that consumes historical portfolio margin snapshots and risk events to produce institutional early-warning indicators. 

## Read-Only Governance Policy
This phase is strictly observational.
- No execution authority is granted.
- No broker behavior is changed.
- No risk gate behavior is changed.
- No order-routing behavior is changed.

## Authoritative Inputs
The trend analyzer exclusively consumes:
- `PortfolioMarginHistoryStore`
- `PortfolioMarginSnapshot` history
- `Portfolio Margin Risk Events` history

Brokers, execution systems, and external sources are NOT called. 
Synthetic values are NOT generated.

## Fail-Closed & Missing Data Policy
If history is empty, all metrics will safely return `DATA_UNAVAILABLE`.
If history contains malformed dictionaries or missing required fields, a `ValueError` is raised immediately to prevent invalid analysis.

## Trend Methodology
The analyzer calculates:
- **Margin Utilization Trend:** Comparing `portfolio_margin_used` to `portfolio_margin_used + portfolio_margin_available`.
- **Buying Power Trend:** Comparing `portfolio_buying_power` across the latest snapshots.
- **Equity Trend:** Comparing `portfolio_equity` across the latest snapshots.
- **Risk State Trend:** Identifying escalation through `MarginState` severity.
- **Escalation Frequency:** Count of risk events historically logged.

## Early Warning Levels
- **GREEN:** No material deterioration.
- **YELLOW:** Observable deterioration.
- **ORANGE:** Repeated escalation events or restricted states.
- **RED:** Persistent escalation trend or liquidation proximity.
