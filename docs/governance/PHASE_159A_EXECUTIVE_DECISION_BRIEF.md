# Phase 159A – CSS Executive Decision Brief Governance

## Purpose

The **CSS Executive Decision Brief** is the executive presentation layer for the CSS repository. It acts as a read-only portal to synthesize and format the system state for institutional Chief Investment Officers and other executive stakeholders.

> [!IMPORTANT]
> **Advisory-Only and Non-Execution Policy:**
> This phase is strictly for executive presentation and aggregates data only. It does not contain any trading decision-making logic or execution controls.
> - `advisory_only` is locked to `True`.
> - `execution_allowed` is locked to `False`.
> - `live_trading_blocked` is locked to `True`.
> - `broker_execution_armed` is locked to `False`.
>
> It **NEVER** changes execution authority, alters broker configuration, or triggers order mutations.

---

## Information Ingestion Schema

The brief aggregates and consumes metrics from the following modules without re-calculating them:

1. **Market Intelligence / Regime**: Current market environment state (e.g. Risk-On, Risk-Off).
2. **Adaptive Strategy Intelligence (Phase 157A)**: Strategy Edge recommendations, metrics, and evidence trackers.
3. **Portfolio Construction Intelligence (Phase 157B)**: Preferred portfolio structure, quality, and diversification parameters.
4. **Institutional Portfolio Optimizer (Phase 157C)**: Scenario candidate metrics and Pareto frontier properties.
5. **Investment Committee Intelligence (Phase 158A)**: Member ratings, comments, and consensus recommendations.
6. **Decision Confidence Framework**: Confidence scores and audit evidence.
7. **Broker Health Monitor**: Connectivity metrics for OANDA, Coinbase, or other active brokers.
8. **Runtime Health Aggregator**: Overall supervisor health.

---

## Presentation Layouts

### 1. JSON
A structured, complete dictionary layout that is serializable and suitable for integration into dynamic dashboard endpoints or API responses.

### 2. Markdown
A stylized markdown layout with clear alert headers, bulleted risks, opportunities, and integration checkpoints suitable for email delivery or web view rendering.

### 3. Console Text
Fixed-width ASCII layout matching the presentation layout exactly.

---

## Dashboard Integration Guidelines

When integrating the brief payload into the CSS Executive Dashboard widgets:
- Status indicators (GREEN/AMBER/RED) should bind to theme-specific alerts.
- List fields like `top_opportunities` and `top_risks` should be rendered sequentially.
- If any component is unavailable, the dashboard must fall back to the fail-closed state.
