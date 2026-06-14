# CSS Multi-Asset Portfolio Architecture

## 1. Purpose

This document defines the long-term portfolio architecture vision for Capital Strata Systems (CSS). CSS is designed as a unified multi-asset institutional trading platform capable of managing, aggregating, monitoring, and reporting positions across multiple asset classes through a common governance and risk framework.

The architecture establishes a conceptual model for normalized positions, exposure aggregation, PnL aggregation, margin and capital governance, broker abstraction, dashboard visibility, and enterprise reporting.

This phase is documentation-only. It does not change runtime behavior, execution logic, broker behavior, dashboard behavior, authentication, or trading logic.

## 2. Supported Asset Classes

CSS portfolio architecture covers current and future asset classes.

| Asset Class | Description | Typical Exposure Profile | Liquidity Characteristics | Risk Characteristics |
| --- | --- | --- | --- | --- |
| Equities | Shares or equity instruments representing ownership in companies. | Directional single-name exposure, sector exposure, market beta exposure. | Usually exchange-traded with high liquidity for large-cap names and lower liquidity for small-cap names. | Price risk, gap risk, earnings/event risk, sector concentration, liquidity risk. |
| ETFs | Exchange-traded funds representing baskets, sectors, indices, commodities, or strategies. | Basket exposure, index exposure, thematic exposure, cross-asset proxy exposure. | Usually liquid for major ETFs, but liquidity varies by underlying basket and market condition. | Tracking risk, liquidity risk, concentration in underlying holdings, market risk. |
| FX | Foreign exchange instruments and currency pairs. | Currency pair exposure, macro exposure, rate differential exposure. | Major pairs are typically highly liquid; minor and exotic pairs may have wider spreads and event risk. | Leverage risk, spread widening, macro event risk, gap risk, carry/rate sensitivity. |
| Crypto | Digital assets and crypto trading pairs. | Directional token exposure, exchange/custody exposure, high-volatility exposure. | Liquidity varies by venue and asset; market depth can change quickly. | High volatility, custody risk, exchange risk, weekend/event risk, slippage risk. |
| Futures | Standardized exchange-traded derivative contracts. | Leveraged notional exposure to indices, rates, commodities, FX, or other underlyings. | Major contracts are liquid; contract roll and expiry affect liquidity. | Leverage, margin, expiry, basis, gap, and forced liquidation risk. |
| Options | Derivative contracts with nonlinear payoff profiles. | Delta, gamma, theta, vega, rho, expiry, and strike-specific exposure. | Liquidity varies by underlying, strike, expiry, and market condition. | Greeks risk, volatility risk, assignment/exercise risk, liquidity risk, margin risk. |
| Fixed Income | Future coverage for bonds, rates, and credit instruments. | Duration, credit, rate, curve, and issuer exposure. | Liquidity varies materially by issuer, maturity, and market regime. | Rate risk, credit risk, liquidity risk, duration risk, spread risk. |
| Commodities | Future coverage for commodity spot, futures, or ETF-like exposure. | Directional commodity exposure, inflation sensitivity, supply/demand exposure. | Liquidity varies by commodity, contract, venue, and roll period. | Storage/roll risk, weather/geopolitical risk, margin risk, gap risk. |

## 3. Unified Portfolio Model

CSS should normalize all multi-asset activity into a unified enterprise hierarchy:

```text
Enterprise Portfolio
+-- Asset Class
    +-- Strategy
    |   +-- Position
    |   +-- Trade
    +-- Risk Controls
```

### Enterprise Portfolio

The enterprise portfolio is the top-level view of all CSS exposure, capital, PnL, margin, risk, broker, and certification state. It supports cross-asset governance, consolidated reporting, and institutional oversight.

### Asset Class

The asset-class layer groups instruments by risk and market structure. It enables asset-class exposure limits, PnL reporting, margin monitoring, and risk classification across equities, ETFs, FX, crypto, futures, options, and future classes.

### Strategy

The strategy layer groups trades and positions by decision logic, alpha source, allocation model, or operating mandate. It supports strategy-level PnL, risk limits, drawdown review, and performance attribution.

### Position

The position layer represents current open exposure. It includes quantity, direction, mark, market value, realized/unrealized PnL, exposure, margin use, and risk classification.

### Trade

The trade layer represents a discrete entry, adjustment, or exit event. It supports auditability, lifecycle tracking, execution analysis, and PnL attribution.

### Risk Controls

Risk controls apply at every layer. They may include position limits, concentration limits, margin gates, drawdown controls, execution gates, legal/session controls, and incident escalation.

## 4. Position Architecture

All asset classes should ultimately normalize into a common position representation.

Common position attributes:

| Attribute | Description |
| --- | --- |
| Instrument | Canonical symbol, contract, pair, or identifier. |
| Quantity | Units, shares, contracts, notional, or normalized exposure amount. |
| Direction | Long, short, flat, or strategy-specific exposure direction. |
| Entry Price | Original or weighted-average entry price. |
| Current Price | Current mark or valuation price. |
| Market Value | Current value of the position. |
| Realized PnL | Closed or crystallized profit and loss. |
| Unrealized PnL | Open mark-to-market profit and loss. |
| Exposure | Gross, net, notional, delta-adjusted, or asset-class-specific exposure. |
| Margin Usage | Required or allocated margin associated with the position. |
| Risk Classification | Risk label, risk state, concentration label, or escalation level. |

Position normalization must preserve asset-class-specific detail where needed. For example, options require Greeks and expiry information, futures require contract and margin metadata, FX requires pair/base/quote context, and equities may require sector or issuer metadata.

## 5. Exposure Aggregation Framework

CSS exposure should aggregate across five levels.

### Position Level

Position-level exposure measures the size and risk of a single open position.

Examples:

* Equity: long 100 shares of AAPL.
* FX: long EUR/USD notional exposure.
* Crypto: long BTC-USD spot exposure.
* Futures: long one index futures contract.
* Options: long call option with delta-adjusted exposure.

### Strategy Level

Strategy-level exposure aggregates all positions generated by the same strategy or mandate.

Examples:

* Equity momentum strategy exposure.
* FX trend strategy exposure.
* Crypto mean-reversion exposure.
* Futures breakout exposure.
* Options single-leg strategy exposure.

### Asset-Class Level

Asset-class exposure aggregates all positions within one asset class.

Examples:

* Total equities market value.
* Total FX notional.
* Total crypto spot value.
* Total futures notional and margin.
* Total options premium, delta, and vega exposure.

### Portfolio Level

Portfolio-level exposure aggregates all current open positions across asset classes and strategies. It should support gross exposure, net exposure, margin-adjusted exposure, and correlated exposure.

### Enterprise Level

Enterprise-level exposure includes broker, counterparty, operational, certification, and governance state. It answers whether CSS as an institution is operating within approved boundaries.

## 6. Unified PnL Architecture

All future reporting should roll up through a common PnL framework.

PnL categories:

| PnL Category | Description |
| --- | --- |
| Realized PnL | Profit and loss from closed or settled trades. |
| Unrealized PnL | Mark-to-market profit and loss on open positions. |
| Daily PnL | Current business-day realized and unrealized movement. |
| Weekly PnL | Week-to-date realized and unrealized performance. |
| Monthly PnL | Month-to-date realized and unrealized performance. |
| Asset-Class PnL | PnL grouped by equities, ETFs, FX, crypto, futures, options, and future classes. |
| Strategy PnL | PnL grouped by strategy or mandate. |
| Enterprise PnL | Consolidated PnL across all asset classes, strategies, brokers, and portfolios. |

The PnL architecture should preserve source lineage: trade event, position lifecycle, asset class, strategy, broker, session, and timestamp.

## 7. Margin and Capital Model

CSS portfolio architecture must distinguish cash, allocation, reservation, margin, and excess liquidity concepts.

| Capital Concept | Description |
| --- | --- |
| Cash Capital | Cash or cash-equivalent balance available within the account or enterprise context. |
| Available Capital | Capital available for new approved risk after reservations and restrictions. |
| Allocated Capital | Capital assigned to a strategy, asset class, or operating mandate. |
| Reserved Capital | Capital held back for risk buffers, pending orders, withdrawals, or governance requirements. |
| Margin Capital | Capital required to support leveraged or margined positions. |
| Excess Liquidity | Capital remaining after margin requirements and risk reserves. |

Roadmap references:

* Phase 95 Institutional Margin Governance Framework
* Phase 96 Margin Engine
* Phase 97 Broker Margin Integration

Margin and capital state must be visible, auditable, and consistent with enterprise risk governance before production use.

## 8. Dashboard Architecture Requirements

Future dashboard architecture must support:

* Exposure by Asset Class
* Exposure by Strategy
* Portfolio Allocation
* Margin Utilization
* Realized PnL
* Unrealized PnL
* Drawdown
* Concentration Metrics
* Enterprise Capital Summary

Dashboard views should clearly distinguish simulated, paper, practice, and live state. The dashboard should remain a visibility surface unless a later approved phase explicitly introduces enforcement behavior.

## 9. Enterprise Risk Integration

This architecture integrates with:

```text
docs/governance/CSS_ENTERPRISE_RISK_MODEL.md
```

The interaction model:

| Layer | Responsibility |
| --- | --- |
| Portfolio Layer | Owns consolidated position, exposure, PnL, margin, and capital views. |
| Exposure Layer | Aggregates position and strategy exposure across asset classes. |
| Risk Layer | Applies position, strategy, asset-class, margin, drawdown, and concentration governance. |
| Governance Layer | Defines approval, audit, certification, escalation, and operational readiness requirements. |

Portfolio architecture provides the data model and aggregation structure; enterprise risk governance defines limits, controls, oversight, and escalation expectations.

## 10. Broker Abstraction Layer

Multiple brokers may contribute positions, balances, margin data, fills, and account state into a single CSS portfolio view.

Examples:

* OANDA
* Coinbase
* IBKR
* Future broker integrations

Broker abstraction requirements:

* Normalize broker-specific symbols into CSS instrument identifiers.
* Normalize broker-specific position fields into the common position model.
* Preserve broker source, account context, and mode.
* Distinguish live, paper, practice, and simulated broker states.
* Avoid mixing broker execution authority with dashboard or reporting visibility.
* Preserve auditability for broker-originated balances, positions, fills, and margin data.

Broker-specific data should enrich the unified portfolio model without replacing CSS governance, risk, or certification controls.

## 11. Reporting Architecture

Future reporting requirements:

* Daily Portfolio Report
* Risk Report
* Exposure Report
* Capital Allocation Report
* Margin Report
* Executive Summary Report

Reporting must support:

* Asset-class rollups
* Strategy rollups
* Broker rollups
* Realized and unrealized PnL
* Drawdown
* Margin utilization
* Concentration metrics
* Risk events
* Operational incidents
* Certification evidence references

Reports should be reproducible, traceable, and reviewable by governance and operations stakeholders.

## 12. Future Expansion Roadmap

This architecture supports institutional deployment by defining how CSS can scale from controlled paper operation to multi-broker, multi-asset, enterprise reporting.

Future roadmap themes:

1. Define canonical position schemas for every asset class.
2. Implement tested exposure aggregation across strategies and asset classes.
3. Extend unified PnL rollups into daily, weekly, monthly, strategy, and enterprise reporting.
4. Integrate margin and capital state into portfolio-level views.
5. Add broker position and balance normalization for approved brokers.
6. Expand dashboard visibility to enterprise portfolio views.
7. Add report generation for portfolio, exposure, risk, margin, and executive summaries.
8. Build certification evidence for long-duration controlled paper operation.
9. Require Robert and governance review before live production onboarding.

CSS should continue to evolve through documentation, test evidence, controlled paper validation, and explicit approval before production deployment.
