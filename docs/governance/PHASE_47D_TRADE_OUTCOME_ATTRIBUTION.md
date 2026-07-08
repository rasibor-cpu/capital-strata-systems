# PHASE 47D: Trade Outcome Attribution Engine

This document details the governance framework, mathematical models, success/failure matrices, and safety invariants for the **Trade Outcome Attribution Engine** under Phase 47D.

---

## 1. Governance & Safety Framework

The **Trade Outcome Attribution Engine** is a post-trade explainability layer that analyzes trade performance.

### Architectural & Safety Invariants
1. **Advisory-Only / Shadow Execution**: The engine strictly evaluates outcomes *post-facto*. It has zero impact on live execution paths, broker routing, or position scaling.
2. **Canonical Analytics Location**: All implementation files reside strictly under `backend/analytics/`. The files under `backend/trading/` are never created or modified. Test compatibility for the Phase 47A trade quality engine is satisfied at test execution runtime using a dynamic mock in `conftest.py`.
3. **Fail-Closed Processing**: Validates candidate mappings. Missing required identifiers (`trade_id`, `symbol`, `asset_class`) or missing PnL metrics immediately raise `TradeOutcomeAttributionError` (fails closed).
4. **Context Isolation**: Missing optional inputs (`quality_output`, `explanation_output`, `execution_output`, `market_regime`, `execution_metrics`, `risk_metrics`) fall back to neutral default contributions instead of crashing.

---

## 2. Contribution Score Models

The engine calculates contribution scores (ranging from -100.0 to +100.0) across 5 core dimensions:

| Dimension | Formula / Scale | Attribution Behavior |
|---|---|---|
| **Trade Quality** | `(trade_quality_score - 60.0) * 2.5` | If quality score was high, maps to positive contribution. Poor quality maps to negative contribution. |
| **Execution Quality** | `(execution_quality_score - 60.0) * 2.5` | If execution score was high, positive contribution. Wide slippage/latency maps to negative. |
| **Regime Alignment** | Alignment match vs. mismatch | Match $\implies +50.0$. Mismatch $\implies -50.0$. |
| **Risk Parameters** | Risk level & Concentration warnings | Warnings $\implies -40.0$. Acceptable/normal $\implies +30.0$. |
| **Execution Timing** | Latency and slippage penalties | Latency $> 500$ms $\implies -30$. Latency $< 50$ms $\implies +20$. Slippage $> 20$ bps $\implies -30$. Slippage $= 0$ bps $\implies +20$. |

---

## 3. Overall Attribution Score

The overall attribution score measures how well the system's upfront predictions aligned with the realized outcome:
- **Winning Trade (PnL > 0)**:
  $$\text{overall\_attribution\_score} = \text{trade\_quality\_score}$$
  (High trade quality predicted win is accurate)
- **Losing Trade (PnL <= 0)**:
  $$\text{overall\_attribution\_score} = 100.0 - \text{trade\_quality\_score}$$
  (High score means poor trade quality warning was accurate)

---

## 4. Structured Output Contract

The deterministic payload has the following structure:

```python
{
    "attribution_summary": str,               # Human-readable paragraph explanation
    "primary_success_factors": list[str],     # Success factors (if PnL > 0)
    "primary_failure_factors": list[str],     # Failure factors (if PnL <= 0)
    "execution_contribution": float,          # Execution contribution (-100 to 100)
    "trade_quality_contribution": float,      # Trade quality contribution (-100 to 100)
    "regime_contribution": float,             # Regime contribution (-100 to 100)
    "risk_contribution": float,               # Risk contribution (-100 to 100)
    "timing_contribution": float,             # Timing/latency contribution (-100 to 100)
    "overall_attribution_score": float,       # System accuracy score (0 to 100)
    "confidence": float,                      # Score reliability metric (0.0 to 1.0)
    "lessons_learned": list[str],             # Generated operational advice
    "advisory_only": True,                    # MUST always be True
    "shadow_mode": True,                      # MUST always be True
    "execution_action": "NO_EXECUTION"        # MUST always be "NO_EXECUTION"
}
```
