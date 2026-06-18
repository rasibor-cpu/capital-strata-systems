# PHASE 80 — OPTIONS GREEKS FRAMEWORK

## Executive Summary

Phase 80 establishes the authoritative architecture for options Greeks within Capital Strata Systems (CSS).

The objective is to provide a consistent framework for:

* options risk measurement
* options opportunity scoring
* portfolio risk aggregation
* strategy selection
* volatility intelligence
* institutional-grade options analytics

This phase is design and governance only.

No live trading permissions are expanded.

No broker gates are modified.

No execution behavior changes are introduced.

---

# Scope

This framework applies to:

* Single-leg options
* Vertical spreads
* Credit spreads
* Debit spreads
* Iron Condors
* Iron Butterflies
* Straddles
* Strangles
* Calendars
* Diagonals
* Future multi-leg options structures

---

# Core Greeks

## Delta

Measures directional exposure.

Interpretation:

* Positive Delta = bullish
* Negative Delta = bearish

Examples:

Long Call:

Delta ≈ +0.50

Long Put:

Delta ≈ -0.50

Use Cases:

* directional exposure
* portfolio bias
* hedge calculation

Classification:

REQUIRED

---

## Gamma

Measures Delta sensitivity.

Interpretation:

How quickly Delta changes.

High Gamma:

* faster exposure change
* higher directional risk

Use Cases:

* risk monitoring
* short-option danger assessment
* volatility event management

Classification:

REQUIRED

---

## Theta

Measures time decay.

Interpretation:

Daily value erosion.

Positive Theta:

income-producing positions

Negative Theta:

premium-buying positions

Use Cases:

* income strategies
* Iron Condors
* Credit Spreads
* Covered Calls

Classification:

REQUIRED

---

## Vega

Measures volatility sensitivity.

Interpretation:

Impact of implied volatility change.

Use Cases:

* volatility strategies
* earnings trades
* IV expansion trades
* IV crush trades

Classification:

REQUIRED

---

## Rho

Measures interest-rate sensitivity.

Interpretation:

Sensitivity to risk-free rate changes.

Use Cases:

* long-dated options
* LEAPS
* institutional analytics

Classification:

OPTIONAL BUT SUPPORTED

---

# Position Greeks Model

Every options position should support:

```python
{
    "delta": float,
    "gamma": float,
    "theta": float,
    "vega": float,
    "rho": float,
    "greeks_source": str
}
```

Accepted source values:

* BROKER
* MARKET_DATA
* BLACK_SCHOLES
* UNKNOWN

UNKNOWN must be explicit.

Silent omission is prohibited.

---

# Portfolio Greeks Model

Aggregate across all positions.

Required fields:

```python
{
    "net_delta": float,
    "net_gamma": float,
    "net_theta": float,
    "net_vega": float,
    "net_rho": float
}
```

Purpose:

Institutional portfolio risk monitoring.

Classification:

REQUIRED

---

# Greeks Data Source Hierarchy

Priority 1:

Broker-Supplied Greeks

Examples:

* Interactive Brokers
* Tradier
* Tastytrade

Priority 2:

Market Data Provider Greeks

Examples:

* Polygon
* Tradier
* OPRA feeds

Priority 3:

Internal Black-Scholes Calculation

Used when Greeks unavailable.

Priority 4:

UNKNOWN

Must display explicitly.

---

# Black-Scholes Fallback Framework

Required Inputs:

* underlying price
* strike
* expiry
* volatility estimate
* risk-free rate

Outputs:

* delta
* gamma
* theta
* vega
* rho

Purpose:

Ensure CSS can calculate Greeks even when broker data is unavailable.

Classification:

PLANNED

---

# Strategy Compatibility

## Single-Leg

Supported:

* Long Call
* Long Put

---

## Credit Spreads

Required:

* Bull Put Spread
* Bear Call Spread

---

## Debit Spreads

Required:

* Bull Call Spread
* Bear Put Spread

---

## Neutral Structures

Required:

* Iron Condor
* Iron Butterfly
* Short Strangle
* Short Straddle

---

## Volatility Structures

Required:

* Long Straddle
* Long Strangle
* Calendar Spread
* Diagonal Spread

---

# Portfolio Risk Engine Integration

Future Portfolio Risk Engine should expose:

* Net Delta
* Net Gamma
* Net Theta
* Net Vega
* Net Rho

Additional Metrics:

* Delta Drift
* Gamma Shock
* Vega Shock
* Theta Projection

Classification:

PLANNED

---

# Dashboard Requirements

Options Dashboard Section:

Display:

* Net Delta
* Net Gamma
* Net Theta
* Net Vega
* Net Rho

Position View:

Display:

* Delta
* Gamma
* Theta
* Vega
* Rho
* Greeks Source

Missing Greeks:

Display:

UNKNOWN

Never blank.

---

# Volatility Alpha Integration

Future Volatility Alpha Engine should leverage:

* Vega
* IV Rank
* IV Percentile
* Skew
* Term Structure

Potential Alpha Sources:

* Earnings Volatility Alpha
* Volatility Risk Premium Alpha
* Skew Alpha
* Regime-Aware Volatility Alpha

Classification:

PLANNED

---

# Institutional Readiness Targets

Minimum Institutional Capability:

* Position Greeks
* Portfolio Greeks
* Dashboard Greeks
* Strategy Greeks

Advanced Institutional Capability:

* Portfolio stress testing
* Greeks shocks
* Volatility alpha
* Multi-leg optimization

---

# Phase 81 Recommendation

Next priority after Greeks Framework:

PHASE81_FUTURES_CONTRACT_INTELLIGENCE_FRAMEWORK

Scope:

* Tick Size
* Tick Value
* Contract Multiplier
* Margin Models
* Expiry Logic
* Contract Rollovers
* Continuous Contracts

---

# Closeout Decision

Phase 80 establishes the authoritative options Greeks architecture for CSS.

No implementation occurs in this phase.

This document serves as the governance foundation for future Greeks development, portfolio risk analytics, options strategy intelligence, and volatility alpha generation.

STATUS: APPROVED FOR FUTURE IMPLEMENTATION
