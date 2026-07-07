# PHASE 47B: Explainable Decision Engine

This document outlines the governance rules, safety frameworks, mathematical details, and auditable specifications for the **Explainable Decision Engine** under Phase 47B.

---

## 1. Governance & Operational Safeguards

The **Explainable Decision Engine** acts as a transparency and explainability layer. It runs in shadow mode to analyze eligible trades and produce structured, human-readable explanations.

### Safety Invariants
1. **Advisory-Only Enforcement**: Under no circumstances shall the Explainable Decision Engine alter trade decisions, influence execution paths, or adjust risk parameters. It is strictly non-blocking.
2. **Fail-Closed Principle**: If the engine receives an invalid trade candidate (missing identifiers like `trade_id`, `symbol`, or `asset_class`, or non-mapping inputs), it raises `ExplainableDecisionEngineError` and fails closed.
3. **Optional Context Isolation**: The engine must never crash due to missing optional contexts (`quality_output`, `signal_context`, `risk_context`, `regime_context`, or `market_metrics`). Missing fields default to neutral or unavailable states gracefully.

---

## 2. Explanation & Scoring Logic

The engine deterministically computes an `explanation_score` and `quality_grade` based on the available inputs:

### Score Calculation
1. **With Phase 47A Output**:
   - If `quality_output` is present, the explanation score is initialized to `trade_quality_score`.
2. **Without Phase 47A Output**:
   - Initialize the score to `70.0` (neutral base).
   - **Signal Context**: Adjusted by up to $\pm 30.0$ points based on the signal strength relative to the $0.5$ midpoint.
   - **Risk Context**:
     - `risk_level == "HIGH"` $\implies -30.0$
     - `risk_level == "LOW"` $\implies +10.0$
     - Concentration risk $> 50\% \implies$ additional penalty.
   - **Regime Alignment**:
     - Candidate and Market regime match $\implies +10.0$
     - Candidate and Market regime mismatch $\implies -30.0$
   - **Market Metrics**:
     - Low liquidity rating or score $< 0.4 \implies -20.0$
     - Wide spread $\ge \text{Max Acceptable Spread} \implies -20.0$
     - Unsuitable volatility suitability $\implies -20.0$
   - Clamped strictly to $[0.0, 100.0]$.

### Grade Mappings
- **A**: $\ge 90.0$
- **B**: $\ge 80.0$ and $< 90.0$
- **C**: $\ge 70.0$ and $< 80.0$
- **D**: $\ge 60.0$ and $< 70.0$
- **F**: $< 60.0$

---

## 3. Structured Factors Matrix

The engine populates supporting/opposing factors, confidence drivers/detractors, and notes fields to detail decision reasoning:

| Dimension | Supporting Criteria ($\ge 85\%$) | Opposing Criteria ($< 60\%$) |
|---|---|---|
| **Trade Quality** | High Trade Quality Assessment | Low Trade Quality Assessment |
| **Signal Strength** | Strong Signal Strength Confirmation | Weak Signal Strength |
| **Regime Alignment** | Aligned Market Regime | Regime Mismatch Detected |
| **Risk Context** | Acceptable Risk Levels | High Portfolio Risk Level / High Concentration Risk |
| **Market Metrics** | Optimal Market Conditions | Low Liquidity Quality / Wide Bid-Ask Spread / Unsuitable Volatility |

---

## 4. Structured Output Contract

The deterministic payload has the following structure:

```python
{
    "decision_summary": str,               # Human-readable paragraph explanation
    "explanation_score": float,            # Deterministic score (0.0 to 100.0)
    "quality_grade": str,                  # A/B/C/D/F
    "supporting_factors": list[str],       # Favorable factors
    "opposing_factors": list[str],         # Unfavorable factors
    "risk_notes": str,                     # Structured notes on risk context
    "regime_notes": str,                   # Structured notes on regime context
    "market_notes": str,                   # Structured notes on market environment
    "confidence_drivers": list[str],       # Favorable confidence drivers
    "confidence_detractors": list[str],     # Unfavorable confidence detractors
    "advisory_only": True,                 # MUST always be True
    "shadow_mode": True,                   # MUST always be True
    "execution_action": "NO_EXECUTION"     # MUST always be "NO_EXECUTION"
}
```
