# PHASE 47A: Trade Quality Scoring Engine

This document details the specifications, design choices, scoring formulas, and governance rules for the **Trade Quality Scoring Engine** under Phase 47A.

---

## 1. Executive Summary & Intent

The **Trade Quality Scoring Engine** evaluates approved trade candidates that have already successfully cleared the **Unified Trade Gate**. It produces a multidimensional quality score (0–100) and grade (A/B/C/D/F) to act as advisory metadata.

### Crucial Safeguards
1. **Advisory & Shadow Enforcement**: Under no circumstances shall the scoring engine's output influence real-time execution routing, position sizing execution, or risk limits. It is strictly non-blocking.
2. **Fail-Closed Processing**: To maintain data and state integrity, the engine must immediately raise `TradeQualityScoringEngineError` and halt the evaluation stream if it receives invalid, malformed, or missing required fields.
3. **No Side Effects**: The engine does not modify any broker configurations, internal balances, database records, or Unified Trade Gate limits.

---

## 2. Scoring Methodology

The overall score is a simple average of the following eight core dimensions, normalized from 0 to 100:

| Dimension | Metric / Target | Decaying / Increasing Behavior |
|---|---|---|
| **Expected Edge** | `expected_value - cost` vs. `target_edge` (default: 0.05) | Higher edge increases the score. If edge <= 0, score is 0. |
| **Risk/Reward Ratio** | `risk_reward` (default: rewards/risk) | Score increases with ratio. Max 100 for ratio >= 3.0. |
| **Signal Agreement** | confirm/agreement metrics | Scale 0.0–1.0 or 0–100. Higher agreement increases the score. |
| **Historical Reliability** | win rate / strategy reliability | Scale 0.0–1.0 or 0–100. Higher reliability increases the score. |
| **Regime Alignment** | candidate vs. market regime | Matches = 100, Mismatch = 20. Poor alignment reduces the score. |
| **Liquidity Quality** | `HIGH` / `MEDIUM` / `LOW` or score | String or numeric scale. Low liquidity reduces the score. |
| **Spread Quality** | bid-ask spread vs. max spread | Spread of 0 -> 100. Spread exceeding max (default: 50 bps) -> 0. |
| **Volatility Suitability** | suitability bool or score | Boolean (True=100, False=20) or numeric scale. Unsuitable volatility reduces score. |

### Formulas & Scoring Scales

1. **Expected Edge**:
   $$\text{Score} = \min\left(100.0, \max\left(0.0, \frac{\text{Edge}}{\text{Target Edge}} \times 100.0\right)\right)$$
2. **Risk/Reward Ratio**:
   $$\text{Ratio} = \frac{\text{Expected Reward}}{\text{Expected Risk}}$$
   - Ratio $\ge 3.0 \implies 100.0$
   - $2.0 \le \text{Ratio} < 3.0 \implies 85.0 + (\text{Ratio} - 2.0) \times 15.0$
   - $1.0 \le \text{Ratio} < 2.0 \implies 50.0 + (\text{Ratio} - 1.0) \times 35.0$
   - $0.5 \le \text{Ratio} < 1.0 \implies 20.0 + (\text{Ratio} - 0.5) \times 60.0$
   - $\text{Ratio} < 0.5 \implies \text{Ratio} \times 40.0$
3. **Signal Agreement & Historical Reliability**:
   - For input $x \in [0.0, 1.0]$, scaled score $= x \times 100$.
   - Clamped strictly between $0.0$ and $100.0$.
4. **Regime Alignment**:
   - Identical candidate and market regimes $\implies 100.0$
   - Mismatched regimes $\implies 20.0$
5. **Liquidity Quality**:
   - `"HIGH"` $\implies 100.0$
   - `"MEDIUM"` $\implies 70.0$
   - `"LOW"` $\implies 30.0$
6. **Spread Quality**:
   - Using percentage spread:
     $$\text{Score} = \max\left(0.0, \min\left(100.0, \left(1.0 - \frac{\text{Spread}}{\text{Max Acceptable Spread}}\right) \times 100.0\right)\right)$$
     (Default $\text{Max Acceptable Spread} = 0.005$ or 50 bps).
7. **Volatility Suitability**:
   - `True` $\implies 100.0$
   - `False` $\implies 20.0$

---

## 3. Output Contract

Every invocation of `score_trade` returns a deterministic dictionary payload matching the contract:

```python
{
    "trade_quality_score": float,         # Average score (0.0 to 100.0)
    "quality_grade": str,                 # A/B/C/D/F
    "dimension_scores": dict[str, float], # Individual score breakdown
    "strengths": list[str],               # Dimensions scored >= 85.0
    "weaknesses": list[str],              # Dimensions scored < 60.0
    "advisory_only": True,                # MUST always be True
    "shadow_mode": True,                  # MUST always be True
    "execution_action": "NO_EXECUTION"    # MUST always be "NO_EXECUTION"
}
```

### Grade Boundaries
- **A**: $\ge 90.0$
- **B**: $\ge 80.0$ and $< 90.0$
- **C**: $\ge 70.0$ and $< 80.0$
- **D**: $\ge 60.0$ and $< 70.0$
- **F**: $< 60.0$

---

## 4. Governance & Audit Trails

To comply with our system safety principles:
- **Zero Live Execution Influence**: Downstream routers check the `advisory_only` and `shadow_mode` flags and ensure they never override decisions or trade executions based on this grade.
- **Fail-Closed Exception Handling**: Any mapping validation failures immediately raise `TradeQualityScoringEngineError` to halt processing of bad trade candidate payloads.
