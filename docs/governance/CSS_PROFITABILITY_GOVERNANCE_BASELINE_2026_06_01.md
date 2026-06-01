# CSS Profitability Governance Baseline Lock

## Baseline ID

CSS_PROFITABILITY_GOVERNANCE_BASELINE_2026_06_01

## Status

Protected Non-Regression Baseline

## Date

2026-06-01

## Purpose

This baseline establishes the minimum acceptable institutional profitability-governance state of Capital Strata Systems (CSS).

No future change may reduce, bypass, weaken, disable, remove, or materially degrade any capability listed in this baseline without explicit approval.

---

# Verified Components

## Opportunity Intelligence

* AIOpportunityScorer present
* Opportunity scoring active
* Opportunity ranking active
* Candidate selection driven by opportunity scores

## Profitability Governance

* ProfitabilityGuard present
* ProfitabilityGuard integrated into TradeDecisionOrchestrator
* ProfitabilityGate present
* Edge quality validation active
* Edge quality floor enforcement active

## Cost Awareness

* ExecutionCostEngine present
* Spread modelling present
* Slippage modelling present
* Fee modelling present

Verified calculation path:

Expected Edge
− Spread
− Slippage
− Fees
======

Net Edge

## Edge Validation

Verified components include:

* expected_edge
* net_edge
* adjusted_edge
* edge_floor
* QUALITY_OK_EDGE
* EDGE_BELOW_QUALITY_FLOOR

## PnL Governance

* Realized PnL tracking
* Unrealized PnL tracking
* Cost-adjusted profitability tracking
* LockedProfitLedger present

## Governance Separation

* Dashboard authority separation evidence present
* Mobile execution decoupling evidence present

---

# Non-Regression Rule

The following components are protected:

* AIOpportunityScorer
* ProfitabilityGuard
* ProfitabilityGate
* ExecutionCostEngine
* Spread calculations
* Slippage calculations
* Fee calculations
* Expected Edge calculations
* Net Edge calculations
* Edge quality floor enforcement
* LockedProfitLedger
* Realized/Unrealized PnL separation

Any future modification affecting these areas requires explicit governance review.

---

# Future Priority

The primary objective after this baseline is:

1. Statistical profitability validation
2. Realized expectancy validation
3. Production certification
4. Institutional readiness testing

Architecture expansion is subordinate to preservation of this baseline.
