# Micro-Live Pilot Risk Acceptance

## Known Risks
1. **Orphaned Live Positions:** A position is opened on the broker but fails to record in the local `TradeLedger`.
2. **Slippage on Execution:** Market conditions cause execution beyond expected thresholds.
3. **Double Execution:** Race conditions causing multiple trades for the same signal.
4. **Rate Limit Exhaustion:** API limits block necessary execution or reconciliation.

## Remaining Open Findings
* **Auto-Flatten Live Execution:** The auto-flatten system is currently in Simulation Mode. It cannot automatically close orphaned positions on the live broker.

## Mitigations
* **Heartbeat Detection:** Continuous reconciliation runs every 5 cycles to detect `ORPHAN_BROKER_POSITION` immediately.
* **Session Lock:** If a divergence is detected, the engine enters a defensive lock, halting all further execution.
* **Slippage Bounds:** OANDA `priceBound` parameter explicitly rejects trades exceeding computed slippage.
* **Manual Repair Workflow:** Formal off-ledger repair workflow allows operators to securely close orphaned positions.

## Residual Risk Assessment
**Medium.**
Due to the absence of a live auto-flatten system, the system relies on human latency to mitigate unhedged positions over the weekend. However, given the strict $1,000 capital and 3 open position limit, the absolute financial risk is contained.

## Operator Responsibilities
* Must physically monitor the dashboard during all active trading hours.
* Must respond immediately to any session lock or `RED` broker health state.
* Must manually flatten the broker account and initiate the repair workflow if an unresolvable divergence occurs.

## Governance Responsibilities
* Oversee execution constraints ($1k capital, $20 daily max loss).
* Provide formal sign-off upon completion of the pilot.
