# Phase 115C: Micro-Live Pilot Definition

## 1. Pilot Objectives
The primary objective of the Micro-Live Pilot is to empirically validate the end-to-end execution pipeline of Capital Strata Systems (CSS) using live capital in a highly constrained environment. Specifically, the pilot aims to verify live order routing, exact market slippage, real-world latency, live MTM (Mark-to-Market) accuracy, and exact API execution behavior under real market conditions, without exposing the system to institutional-level capital risk.

## 2. Allowed Brokers
- OANDA
- Coinbase
- IBKR

## 3. Approved Broker(s) for Pilot
- **OANDA:** APPROVED (Validated in Phase 114V/115A).
- **Coinbase:** APPROVED WITH CONDITIONS (Pending SEC-05 Operational Key Rotation).
- **IBKR:** REJECTED (Architecture supports Shadow UI only; structurally isolated from unified gate).

## 4. Maximum Capital Exposure
**$1,000 USD Equivalent** across all combined broker accounts.

## 5. Maximum Concurrent Positions
**3** (Strict global unified ledger limit).

## 6. Maximum Daily Trades
**10** aggregate completed round-trips per 24-hour cycle.

## 7. Maximum Daily Loss
**-$20.00 USD Equivalent.** (Triggers immediate daily halt).

## 8. Maximum Total Pilot Loss
**-$50.00 USD Equivalent.** (Triggers total pilot abort and system shutdown).

## 9. Pilot Duration
**5 Active Trading Days.**

## 10. Immediate Abort Conditions
- Breach of Maximum Daily Loss.
- Breach of Maximum Total Pilot Loss.
- Any unhandled runtime exception in the core execution loop.
- Any unauthorized persistence failure in the unified ledger.
- API connectivity failure exceeding 3 consecutive retries.
- Identification of duplicate order execution (double-spend/double-trade).

## 11. Required Evidence Collection
- Full session runtime logs (`.log` and stdout traces).
- Database snapshot of `pnl_snapshots` table.
- Database snapshot of `trade_decisions` table.
- Empirical slippage calculation (Expected Execution Price vs. Actual Fill Price).
- Broker statements matching the pilot duration.

## 12. Recovery Procedure
In the event of an abort:
1. Issue manual `SIGINT` to cleanly halt the dashboard and execution loop.
2. Manually execute "Close All Positions" via primary broker web interfaces (OANDA/Coinbase web portals) to guarantee flattening.
3. Export state databases and freeze repository state.
4. Escalate to Governance Officer for post-mortem analysis.

## 13. Success Criteria
- 5 days of continuous operation without an unhandled exception.
- Empirical slippage documented and within tolerable bounds (< 0.05% average).
- PnL metrics in the CSS unified ledger match broker-reported PnL exactly (±$0.01 tolerance due to rounding).
- All risk gates (especially anti-bleed and max loss) enforce dynamically as designed.

## 14. Failure Criteria
- Triggering of any Immediate Abort Condition.
- Mismatch between CSS ledger PnL and Broker PnL exceeding tolerance.
- Structural failure of the RBAC or live session mapping system.

## 15. Final Recommendation
**READY WITH CONDITIONS**
The Micro-Live Pilot is structurally ready to commence, pending the strict resolution of the SEC-05 Coinbase Key Rotation requirement and formal Governance execution approval (activation of `.env.live`).
