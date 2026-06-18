# Phase 96A — Margin Architecture Definition

## Purpose

Phase 96A establishes the authoritative margin architecture for Capital Strata Systems (CSS).

This phase defines:

* Margin authority ownership
* Margin data contracts
* Margin governance hierarchy
* Margin escalation model
* Broker abstraction requirements
* Dashboard visibility requirements
* Audit requirements

This phase does not:

* Calculate margin
* Fetch broker margin
* Approve leverage
* Execute trades
* Modify positions

Implementation is reserved for later phases.

---

# Margin Authority Model

Margin is a cross-asset institutional risk and capital-control layer.

Margin authority is jointly owned by:

* Capital Governor
* Risk Governor
* Margin Engine
* Broker Margin Adapter Layer

No trading engine may independently approve margin usage.

No asset-class engine may override margin controls.

---

# Margin Hierarchy

CSS margin authority hierarchy:

1. Broker Margin Authority
2. CSS Margin Engine
3. Capital Governor
4. Risk Governor
5. Trade Gate
6. Dashboard Visibility Layer

The Trade Gate may consume margin decisions.

The Trade Gate may not create margin decisions.

---

# Margin Data Contract

All margin providers must expose:

```text
margin_source
account_id
broker_name

required_margin
available_margin
free_margin

margin_utilization_pct

margin_state
margin_escalation_state

timestamp
```

---

# Portfolio Margin Object

Canonical portfolio margin object:

```text
portfolio_required_margin
portfolio_available_margin
portfolio_free_margin

portfolio_margin_utilization_pct

portfolio_margin_state
portfolio_margin_escalation_state
```

---

# Asset Margin Object

Canonical asset margin object:

```text
asset_class

required_margin
available_margin
free_margin

margin_utilization_pct

margin_state
```

Supported asset classes:

* FX
* Futures
* Options
* Crypto
* Equities
* ETFs

---

# Margin State Model

Margin states:

| State   | Meaning                  |
| ------- | ------------------------ |
| UNKNOWN | Margin state unavailable |
| GREEN   | Normal                   |
| YELLOW  | Elevated monitoring      |
| ORANGE  | Restrict new risk        |
| RED     | Defensive mode           |
| BLACK   | Critical block           |

---

# Margin Escalation Model

Escalation states:

| Escalation        | Action                   |
| ----------------- | ------------------------ |
| NORMAL            | No restriction           |
| MONITOR           | Audit and visibility     |
| RESTRICT_NEW_RISK | New positions restricted |
| DEFENSIVE_ONLY    | Risk reduction only      |
| CRITICAL_BLOCK    | Block new exposure       |

---

# Capital Governor Integration

Capital Governor consumes:

* required margin
* available margin
* free margin

Capital Governor may:

* reduce position sizing
* reduce capital allocation
* deny new allocation

Capital Governor may not override broker margin authority.

---

# Risk Governor Integration

Risk Governor consumes:

* margin utilization
* margin escalation state
* margin source

Risk Governor may:

* elevate risk level
* trigger defensive controls
* trigger escalation logging

Risk Governor may not alter broker margin calculations.

---

# Broker Margin Abstraction Layer

Every broker adapter must map broker-specific fields into the canonical CSS margin contract.

Supported brokers:

* OANDA
* Coinbase
* IBKR

Future brokers must implement the same contract.

---

# Margin Trade Gate Integration

Trade Gate consumes:

* margin utilization
* margin state
* escalation state

Trade Gate may:

* permit trade
* restrict trade
* block trade

Trade Gate must never calculate margin.

---

# Margin Dashboard Integration

Dashboard must display:

* Margin Source
* Required Margin
* Available Margin
* Free Margin
* Utilization %
* Margin State
* Escalation State
* Last Update Time

---

# Margin Audit Requirements

All margin events must record:

* timestamp
* broker
* asset class
* margin source
* required margin
* available margin
* utilization
* state
* escalation
* session id
* user id

---

# Failure Handling

Paper Mode:

* simulated margin permitted
* must display SIMULATED source

Live Mode:

* unknown margin fails closed
* missing broker margin blocks margin-dependent exposure

---

# Successor Phases

Phase 96B — Margin Engine

Phase 97 — Broker Margin Integration

Phase 98 — Margin-Aware Trade Gate

Phase 99 — Margin Dashboard

---

# Acceptance Criteria

Phase 96A is complete when:

* Margin authority hierarchy is defined.
* Margin contract is defined.
* Margin states are defined.
* Escalation model is defined.
* Capital integration is defined.
* Risk integration is defined.
* Broker abstraction requirements are defined.
* Dashboard requirements are defined.
* Audit requirements are defined.
