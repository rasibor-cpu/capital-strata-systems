# Capital Strata Systems (CSS) — Master Specification v1

## System Philosophy (Locked)
**Controlled Risk Governance. Controlled Compounding.**

CSS is a governance-first capital allocation system, not just a signal engine.

---

## 1. System Architecture

### 1.1 Data Layer
- Market data ingestion (crypto, FX, futures)
- Inputs:
  - Price
  - Volume
  - Spread
  - Candles (1m, 5m)

---

### 1.2 Intelligence Layer
Modules:
- FeatureBuilder
- MarketRegimeEngine
- SignalConfluenceEngine
- OpportunityPressureEngine
- PressureAccelerationEngine
- VWAPDeviationEngine
- VWAPElasticityEngine
- LiquiditySweepDetector

Output:
- Structured feature map per asset

---

### 1.3 Decision Layer (Core)
Orchestrator:
- TradeDecisionOrchestrator

Inputs:
- AI score
- Confluence
- Pressure
- Acceleration
- VWAP deviation
- Regime

Output:
- Decision: TRADE / WATCH / IGNORE
- Tier: ELITE / QUALIFIED / REJECT

---

### 1.4 Execution Layer
Modules:
- PositionManager
- ProfitCaptureEngine
- ExecutionCostEngine

Responsibilities:
- Trade entry/exit
- Cost modeling
- Trade lifecycle management

---

### 1.5 Governance Layer (Critical)
Controls:
- Profitability Gate
- Allocation Limits
- Regime Enforcement
- Session Policy

---

## 2. Profitability Gate (Locked)

### Rule
Expected Edge (bps) > Total Cost (bps) → ALLOW  
Else → BLOCK

### Cost Model

Crypto:
- Spread: 4–6 bps
- Slippage: 2–4 bps
- Fees: 1–2 bps
- Total: 7–12 bps

FX:
- Spread: 1–2 bps
- Slippage: 1–2 bps
- Fees: 0–1 bps
- Total: 2–5 bps

### Minimum Edge
- Default: 10 bps

---

## 3. Trade Scoring Model (Locked)

Final Score =
0.30 × AI Score +
0.20 × Confluence +
0.20 × Pressure +
0.15 × Acceleration +
0.15 × VWAP Deviation

### Thresholds
- ELITE: ≥ 80
- QUALIFIED: ≥ 65
- WATCH: 50–64
- IGNORE: < 50

---

## 4. Trade Allocation Rules

### Max Trades Per Cycle
- Total: 10

### Allocation
- Crypto: 3
- FX: 3
- Futures: 2
- Options: 2

### Enforcement
- Hard cap (no override without admin policy)

---

## 5. Exit Strategy Framework

### Take Profit (TP)
- VWAP-based dynamic
- Range: +15 to +25 bps

### Stop Loss (SL)
- Volatility-adjusted
- Range: -10 to -15 bps

### Early Exit Triggers
- Momentum reversal
- VWAP snap-back
- Pressure collapse

---

## 6. Expected Value (EV) Model

EV = (WinRate × AvgWin) − (LossRate × AvgLoss) − Costs

### Requirement
- EV must be > 0
- Target ≥ 0.002

---

## 7. Regime to Strategy Mapping

| Regime          | Strategy           |
|-----------------|-------------------|
| Mean Reversion  | VWAP MR           |
| Trend           | Momentum Follow   |
| Volatile        | Breakout          |
| Range           | Oscillation       |

---

## 8. Trade Journal Schema

Fields:
- timestamp
- symbol
- regime
- AI_score
- confluence_score
- entry_price
- exit_price
- pnl
- pnl_bps
- holding_time
- reason_for_entry
- reason_for_exit

---

## 9. Cycle Tracking

System must display:

Cycle #1  
Cycle #2  
Cycle #3  

Purpose:
- Traceability
- Debugging
- Performance attribution

---

## 10. Non-Regression Rule (Absolute)

- No feature removal allowed
- All updates must be:
  - Additive
  - Backward-compatible

Baseline:
CSS_BASELINE_PERF_DASHBOARD_2026_04_05

---

## 11. Known Issues

- Trades not executing
- Flat PnL outputs
- Missing cycle numbering
- Lost engine modes

---

## 12. Immediate Priorities

1. Profitability Gate integration  
2. Scoring model enforcement  
3. Trade allocation enforcement  
4. Cycle tracking  
5. Trade journal restoration  

---

## 13. Strategic Positioning

CSS is:
- A governance-first trading system
- A cost-aware execution engine
- A controlled-risk capital allocator

---

## 14. Commercial Value

CSS solves:
- Overtrading
- Cost blindness
- Signal noise
- Execution inefficiencies
