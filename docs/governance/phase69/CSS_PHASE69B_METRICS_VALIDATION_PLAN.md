# CSS Phase 69B – Metrics Validation Plan

## Status

Approved

## Dependency

Required baseline:

* CSS_PROFITABILITY_GOVERNANCE_BASELINE_2026_06_01
* CSS_PHASE69A_LOCAL_RECREATION_LOCK

No Phase 69B activity may weaken, bypass, or remove protected profitability-governance controls.

---

# Objective

Determine whether CSS already calculates, stores, and exposes the profitability metrics required for institutional validation.

This phase is discovery and validation first.

New architecture is prohibited unless a metric is proven missing.

---

# Metrics To Verify

## Trade Performance

* Win Rate
* Loss Rate
* Total Trades
* Winning Trades
* Losing Trades

## Profitability

* Gross Profit
* Gross Loss
* Net Profit
* Profit Factor
* Average Winner
* Average Loser
* Expectancy

## Edge Metrics

* Expected Edge
* Net Edge
* Adjusted Edge
* Realized Edge
* Edge Drift

## Cost Metrics

* Spread Burden
* Slippage Burden
* Fee Burden
* Total Cost Burden

## Capital Efficiency

* Return Per Trade
* Return Per Dollar Risked
* Capital Utilization

---

# Discovery Rules

For each metric determine:

* ACTIVE
* SUPPORTING
* ARCHIVE
* UNKNOWN

Document:

* File Path
* Function/Class
* Purpose
* Evidence Source

---

# Deliverables

docs/governance/phase69/CSS_PHASE69B_METRICS_VALIDATION_REPORT.md

Supporting evidence folder:

docs/governance/phase69/evidence/phase69b/

---

# Success Criteria

Phase 69B passes if:

1. Existing metrics are inventoried.
2. Missing metrics are identified.
3. No runtime regression occurs.
4. No broker logic changes occur.
5. No dashboard execution authority changes occur.

---

# Non Regression Requirement

The following remain protected:

* AIOpportunityScorer
* ProfitabilityGuard
* ProfitabilityGate
* ExecutionCostEngine
* Expected Edge
* Net Edge
* Adjusted Edge
* LockedProfitLedger
* Realized/Unrealized PnL Separation

No modifications permitted without explicit approval.
