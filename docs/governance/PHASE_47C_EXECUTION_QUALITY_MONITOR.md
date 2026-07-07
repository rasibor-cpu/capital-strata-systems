# PHASE 47C: Execution Quality Monitor

This document outlines the specifications, mathematical scoring models, and governance rules for the **Execution Quality Monitor** under Phase 47C.

---

## 1. Executive Summary & Intent

The **Execution Quality Monitor** evaluates execution quality after simulated, paper, or live-read-only trade events without altering the execution path.

### Critical Invariants
1. **Advisory-Only Enforcement**: The monitor strictly runs in shadow mode, providing post-trade analytics. It must never block, cancel, or alter any orders or active trade flows.
2. **Fail-Closed Principle**: To ensure metric purity, any invalid inputs (e.g. non-mapping inputs or missing/empty identifier fields like `trade_id`, `symbol`, or `fill_status`) raise `ExecutionQualityMonitorError` to block processing of malformed execution metrics.
3. **Optional Metric Isolation**: Missing optional metrics default to neutral assumptions rather than causing runtime crashes.

---

## 2. Mathematical Scoring Models

The overall score is calculated as a simple average of 4 execution dimensions (each ranging 0–100):

| Dimension | Formula / Scale | Scoring Behavior |
|---|---|---|
| **Slippage Quality** | `slippage_bps = abs(actual - expected)/expected * 10000` | Score $= \max(0.0, \min(100.0, 100.0 - \text{slippage\_bps} \times 2.0))$ |
| **Spread Quality** | `spread_bps` vs. `expected_entry_price` | Score $= \max(0.0, \min(100.0, 100.0 - \text{spread\_bps} \times 2.0))$ |
| **Latency Quality** | `latency_ms` (from `order_latency` * 1000) | Score $= \max(0.0, \min(100.0, 100.0 - (\text{latency\_ms} / 10.0)))$ |
| **Fill Status** | `"FILLED"` / `"PARTIALLY_FILLED"` / other | `"FILLED"` $= 100.0$, `"PARTIALLY_FILLED"` $= 60.0$, others $= 0.0$ |

### Aggregation Rules
- If `fill_status` is in `{"REJECTED", "FAILED"}`, the overall `execution_quality_score` is directly set to `0.0`.
- Otherwise, it is:
  $$\text{execution\_quality\_score} = \frac{\text{slippage\_score} + \text{spread\_score} + \text{latency\_score} + \text{fill\_status\_score}}{4.0}$$

---

## 3. Output Contract

Every execution evaluation returns a deterministic dict matching this contract:

```python
{
    "execution_quality_score": float,     # Aggregated score (0.0 to 100.0)
    "execution_grade": str,               # A/B/C/D/F
    "slippage_bps": float,                # Calculated slippage in basis points
    "latency_ms": float,                  # Order latency in milliseconds
    "spread_bps": float,                  # Bid-ask spread in basis points
    "strengths": list[str],               # Dimensions scored >= 85.0
    "weaknesses": list[str],              # Dimensions scored < 60.0
    "advisory_only": True,                # MUST always be True
    "shadow_mode": True,                  # MUST always be True
    "execution_action": "NO_EXECUTION"    # MUST always be "NO_EXECUTION"
}
```

### Grade Thresholds
- **A**: $\ge 90.0$
- **B**: $\ge 80.0$ and $< 90.0$
- **C**: $\ge 70.0$ and $< 80.0$
- **D**: $\ge 60.0$ and $< 70.0$
- **F**: $< 60.0$
