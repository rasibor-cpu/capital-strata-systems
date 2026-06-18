# PHASE 86 — OPTIONS GREEKS DASHBOARD INTEGRATION

## Executive Summary

Phase 86 integrates the Options Greeks data model into the CSS runtime dashboard.

This phase assumes completion of:

* Phase 80 Options Greeks Framework
* Phase 83 Greeks Implementation Roadmap
* Phase 85 Options Greeks Data Model

The objective is visibility only.

No Greeks calculations are introduced.

No broker integrations are introduced.

No live-trading permissions are expanded.

---

# Objective

Expose stored Greeks values to CSS operators in a clear, auditable, fail-closed manner.

The dashboard must display Greeks that already exist in position data structures.

The dashboard must not fabricate Greeks.

---

# Dashboard Principles

1. Display only known values.
2. UNKNOWN is preferred to fabricated values.
3. No synthetic calculations.
4. No hidden substitutions.
5. Preserve existing dashboard behavior.

---

# Position-Level Greeks Display

Every OPTIONS position should be capable of displaying:

```text
Delta
Gamma
Theta
Vega
Rho
Greeks Source
```

Example:

```text
AAPL-C-250

Delta: 0.42
Gamma: 0.03
Theta: -0.02
Vega: 0.18
Rho: 0.01
Source: BLACK_SCHOLES
```

---

# Unknown Greeks Display

If Greeks unavailable:

```text
Delta: UNKNOWN
Gamma: UNKNOWN
Theta: UNKNOWN
Vega: UNKNOWN
Rho: UNKNOWN
Source: UNKNOWN
```

Never:

```text
0.00
```

unless that is the actual stored value.

---

# Options Position Summary Panel

Required fields:

```text
Symbol
Position ID
Contracts
Entry Price
Current Price
Floating PnL

Delta
Gamma
Theta
Vega
Rho
Greeks Source
```

Classification:

REQUIRED

---

# Portfolio Greeks Summary

Future-ready dashboard section.

Display:

```text
Net Delta
Net Gamma
Net Theta
Net Vega
Net Rho
```

If portfolio aggregation not implemented:

```text
NOT AVAILABLE
```

Classification:

REQUIRED

---

# Greeks Source Visibility

Display source exactly as stored:

Valid values:

```text
BROKER
MARKET_DATA
BLACK_SCHOLES
UNKNOWN
```

No translation.

No abbreviations.

---

# Dashboard Filtering

Future capability:

Filter options positions by:

```text
High Delta
High Gamma
High Vega
Negative Theta
Unknown Greeks
```

Classification:

PLANNED

---

# Dashboard Alerts

Future capability:

Examples:

```text
HIGH DELTA EXPOSURE

HIGH VEGA EXPOSURE

EXCESS NEGATIVE THETA

UNKNOWN GREEKS PRESENT
```

Classification:

PLANNED

---

# Multi-Leg Strategy Readiness

Dashboard architecture must remain compatible with:

```text
Iron Condor
Iron Butterfly
Bull Call Spread
Bear Call Spread
Calendar Spread
Diagonal Spread
Straddle
Strangle
```

Phase 86 does not implement these.

Only preserve future compatibility.

---

# Fail-Closed Requirements

If Greeks missing:

Display:

```text
UNKNOWN
```

Do not calculate.

Do not infer.

Do not estimate.

---

# Testing Requirements

Required tests:

1. Known Greeks render correctly.
2. UNKNOWN Greeks render correctly.
3. Invalid source displays as UNKNOWN.
4. Non-options positions unaffected.
5. Existing dashboard functionality preserved.

---

# Out of Scope

Do NOT implement:

* Greeks calculations
* Portfolio Greeks aggregation
* Black-Scholes
* Volatility analytics
* Strategy classification
* Broker Greeks retrieval

These belong to later phases.

---

# Expected Files

Potential implementation targets:

```text
scripts/css_live_dashboard.py
dashboard/
tests/
```

Actual targets depend on authoritative dashboard architecture.

---

# Success Criteria

CSS operators can:

* see stored Greeks
* identify missing Greeks
* identify Greeks source

without changing any trading logic.

---

# Phase 87 Recommendation

PHASE87_PORTFOLIO_GREEKS_AGGREGATION

Scope:

* Net Delta
* Net Gamma
* Net Theta
* Net Vega
* Net Rho
* Portfolio Greeks Dashboard

---

# Closeout Decision

Phase 86 establishes the dashboard integration architecture for options Greeks.

No calculations are introduced.

No trading behavior changes are introduced.

This phase is strictly visibility and observability.

STATUS: APPROVED FOR FUTURE IMPLEMENTATION
