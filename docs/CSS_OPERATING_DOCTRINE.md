# Capital Strata Systems (CSS)
## Operating Doctrine

---

# 🔒 1. FBL — FOUNDATION BASELINE LOCK

FBL RECORD — FOUNDATION BASELINE LOCK

Baseline Name:
FBL_PCNRASS_YYYY_MM_DD_<short_description>

Date/Time:
<YYYY-MM-DD HH:MM>

Branch:
<current branch name>

Commit Hash:
<git commit hash>

Tag:
<git tag name>

Environment:
- Broker(s): <Coinbase / OANDA / etc>
- Mode: <SAFE / CONSERVATIVE / BALANCED / AGGRESSIVE / EXPANSION>
- Data Source: <live / paper / simulated>

System State Summary:
- Dashboard: RUNNING / NOT RUNNING
- Trade Engine: ACTIVE / IDLE
- PnL Engine: VERIFIED / NOT VERIFIED
- Execution Layer: CONNECTED / DISCONNECTED

Validated Components:
✔ Market Scanner
✔ Regime Detection
✔ Signal Generation
✔ Trade Decision Orchestrator
✔ Execution Cost Engine
✔ PnL Engine (realized/unrealized)
✔ Position Tracking
✔ Dashboard Display

Performance Snapshot:
- Cycles Completed: <number>
- Total PnL: <value>
- Win Rate: <value>
- Max Drawdown: <value>

Known Issues:
- <list anything still imperfect>

Recovery Instructions:
git checkout <branch>
git checkout <commit or tag>

Notes:
<freeform observations>

---

# ✅ 2. PCNRASS — PLEASE CONFIRM NO REGRESSION AND STABLE STATE

Definition:
A mandatory validation gate before any code change, commit, merge, or deployment.

A system is considered PCNRASS-compliant only if:

1. Dashboard loads without error
2. Engine mode selection is visible and functional
3. Broker connection initializes correctly
4. Market scan executes successfully
5. Trade decisions are generated correctly
6. Trades (paper or live) execute without failure
7. PnL updates correctly (realized + unrealized)
8. No previously working feature is broken or missing
9. Logs and audit files are being written correctly
10. No performance degradation (latency / freezing / stalls)

Rule:
NO change proceeds unless PCNRASS is explicitly confirmed.

Violation:
Any missing feature, broken flow, or silent failure = REGRESSION

Response to Violation:
- STOP immediately
- REVERT to last FBL
- DO NOT PATCH blindly
- FIX at root cause

---

# 🧭 3. CSS STABILIZATION PHASE — EXECUTION PLAN

Objective:
Restore system integrity and eliminate regression risk before further development.

Phase 1 — Baseline Recovery
- Identify last known working commit
- Restore dashboard + engine to working state
- Confirm PCNRASS

Phase 2 — Functional Reattachment
- Reattach PnL engine
- Reattach execution layer
- Reattach scanner + regime + signal chain
- Validate each layer independently

Phase 3 — Integration Validation
- Run full system end-to-end
- Execute multiple cycles
- Confirm:
  ✔ trades occur
  ✔ PnL updates
  ✔ no crashes

Phase 4 — FBL Lock
- git add .
- git commit (PCNRASS message)
- git tag FBL_<name>
- push branch + tags

Phase 5 — Directory Control
- Identify production files
- Archive legacy files
- Maintain single source of truth

Output:
Stable, non-regressing, reproducible system baseline

---

# 📚 4. CSS MASTER INDEX

CORE ENTRY POINT
scripts/css_live_dashboard.py

CORE ENGINE LAYERS

1. DATA LAYER
- Market data ingestion
- Candle builders
- Data validation

2. INTELLIGENCE LAYER
- MarketRegimeDetector
- AIOpportunityScorer
- SignalConfluenceEngine
- OpportunityPressureEngine
- PressureAccelerationEngine
- VWAPElasticityEngine

3. DECISION LAYER
- TradeDecisionOrchestrator
- ProbabilityPredictionEngine
- QuantSignalOptimizer

4. GOVERNANCE LAYER
- RiskGovernor
- ExecutionCostEngine
- Bleed Governor (cross-asset protection)

5. EXECUTION LAYER
- Broker adapters (Coinbase / OANDA / etc)
- Order placement logic

6. PnL LAYER
- Realized PnL
- Unrealized PnL
- Cost-adjusted PnL

7. POSITION MANAGEMENT
- Open positions tracking
- Lifecycle management

8. DASHBOARD
- Cycle display
- PnL display
- Trade logs
- Mode + broker status

9. AUDIT / LOGGING
- audit_logs/trades.jsonl
- broker_gate_audit.jsonl

10. ARTIFACTS
- artifacts/css_open_positions.json
- artifacts/css_closed_trades.json

---

# 📈 5. OPTIONS & FUTURES COMPLETION CHECKLIST

PHASE A — STRUCTURAL READINESS
✔ Broker adapter supports asset class
✔ Symbol mapping defined (SPY, QQQ, AAPL, ES, NQ, etc)
✔ Contract specifications handled

PHASE B — SIGNAL COMPATIBILITY
✔ Signals generated for options/futures
✔ Regime detection compatible
✔ Volatility handling integrated

PHASE C — DECISION ENGINE
✔ TradeDecisionOrchestrator supports asset class
✔ ProbabilityPredictionEngine works for options/futures
✔ Risk rules adapted

PHASE D — EXECUTION
✔ Orders successfully placed (paper mode first)
✔ Fill confirmation received
✔ No execution errors

PHASE E — PnL TRACKING
✔ Realized PnL correct
✔ Unrealized PnL correct
✔ Fees/spread/slippage included

PHASE F — DASHBOARD VISIBILITY
✔ Trades visible by asset class
✔ PnL broken down per asset
✔ Win/loss stats visible

PHASE G — GOVERNANCE
✔ Risk limits enforced
✔ Position sizing correct
✔ No runaway exposure

PHASE H — STABILITY TEST
✔ Run ≥ 20 cycles
✔ No crashes
✔ No silent failures

PHASE I — FBL LOCK
✔ PCNRASS confirmed
✔ Baseline tagged
✔ Ready for production expansion