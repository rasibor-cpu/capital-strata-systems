# Phase 95: Institutional Margin Governance Framework

## 1. Purpose and Scope
This framework establishes the authoritative rules, processes, and systems for managing margin across Capital Strata Systems (CSS). It serves as the sole authority for all future margin functionality, ensuring that CSS maintains safe leverage boundaries, prevents liquidation events, and enforces unified margin governance across all supported asset classes and brokers. The scope covers runtime monitoring, trade-gate integrations, emergency escalations, and audit reporting.

## 2. Margin Authority Model
The Margin Authority Model dictates that all margin-related decisions must stem from the canonical CSS Risk Governor, integrating real-time intelligence from the Broker Margin Abstraction Layer. Synthetic or mock margin metrics are strictly prohibited in live execution paths. All execution gates must fail closed if authoritative margin state is unavailable.

## 3. Cross-Asset Margin Governance
To ensure unified risk exposure management, the margin framework enforces asset-class specific governance rules:
* **Equities**: Governed by standard Reg T / Portfolio Margin rules depending on broker integration. Overnight leverage limits are strictly enforced.
* **FX**: Managed via dynamic leverage adjustments sensitive to high-volatility regime mutations.
* **Crypto**: Enforces highest-tier margin haircuts due to extreme asset volatility and sudden liquidity shifts.
* **Futures**: Uses SPAN-equivalent margin monitoring with real-time maintenance margin threshold tracking.
* **Options**: Adheres to strict risk-based margin bounds, incorporating Greek exposure aggregation into the core margin assessment.

## 4. Margin State Definitions
Margin health is classified into the following discrete states to trigger programmatic system responses:
* **NORMAL**: Margin utilization is within safe operational bounds (e.g., < 50%).
* **WARNING**: Margin utilization is elevated (e.g., 50% - 70%). Capital Strata Systems will alert the Trade Decision Orchestrator to exercise caution.
* **RESTRICTED**: High margin utilization (e.g., 70% - 85%). New risk-increasing positions are blocked by the Margin Trade Gate.
* **CRITICAL**: Extreme margin utilization (e.g., > 85%). All non-hedging trades are strictly prohibited. System triggers SEV2 alerts.
* **LIQUIDATION_RISK**: Immediate risk of forced broker liquidation. Auto-flattening protocols may be engaged to protect equity.

## 5. Margin Escalation Framework
When margin states transition to RESTRICTED, CRITICAL, or LIQUIDATION_RISK, the following escalation paths apply:
* RESTRICTED: The `TradeDecisionOrchestrator` automatically rejects new opening orders. The runtime logs a WARN-level event.
* CRITICAL: SEV2 Incident is raised. The `OperationsCommanderAgent` is notified. Manual overrides require `SUPER_USER` intervention.
* LIQUIDATION_RISK: SEV1 Incident is raised. Immediate halt of all non-flattening operations. The `Global Kill Switch` may be engaged automatically.

## 6. Margin Breach Response Framework
In the event of a margin breach (where broker margin requirements are violated):
1. **Detection**: The Broker Margin Abstraction Layer identifies the breach via canonical API sync.
2. **Halt**: All autonomous trading agents are paused.
3. **Assessment**: The Risk Governor evaluates open positions to identify the most capital-efficient flattening path.
4. **Action**: Only risk-reducing or closing orders are routed to the Execution Gate.
5. **Review**: The incident is logged for mandatory Post-Trade Reconciliation and Governance Audit.

## 7. Capital Governor Integration
The Margin Governance Framework runs concurrently with the Capital Governor. The Capital Governor determines the max capital allocation per trade, while the Margin Framework asserts whether the *portfolio's aggregate margin state* can support the allocation. If the Margin Framework returns `RESTRICTED`, the Capital Governor's allocation is overridden to 0 for risk-increasing trades.

## 8. Risk Governor Integration
The Risk Governor incorporates the current Margin State into its regime evaluation. Under `RESTRICTED` or worse margin states, the Risk Governor applies a global risk multiplier that penalizes high-volatility assets, ensuring the portfolio naturally gravitates toward safety until margin pressure subsides.

## 9. Trade Gate Integration Requirements
All trade tickets must pass through the `MarginTradeGate` within the `ExecutionGate` sequence.
* The gate must enforce a fail-closed policy.
* It must fetch canonical margin state directly from the `MarginAdapter`.
* It must evaluate the projected margin impact of the requested trade.
* Trades causing a transition into `CRITICAL` state must be rejected.

## 10. Broker Margin Abstraction Layer
CSS must implement a unified `MarginAdapter` interface that abstracts broker-specific margin mechanics.
* All brokers (e.g., Coinbase, Oanda) must implement methods to return a standardized `MarginSnapshot` containing: `total_margin`, `used_margin`, `available_margin`, and `margin_state`.
* If a broker's API is unreachable, the adapter must return a `MARGIN_SNAPSHOT_UNAVAILABLE` status, triggering a fail-closed response downstream.

## 11. Margin Audit Requirements
Every margin state transition must be recorded in the `css_event_ledger`.
* The `GovernanceAuditorAgent` will review margin snapshots hourly.
* Any time the system enters `CRITICAL` or `LIQUIDATION_RISK` states, a detailed forensic log of the portfolio state and the triggering market conditions must be preserved.

## 12. Margin Dashboard Requirements
The CSS Unified Dashboard must feature a dedicated Margin Widget:
* Real-time display of Current Margin State (NORMAL, WARNING, RESTRICTED, CRITICAL).
* Visual gauge of Margin Utilization %.
* Alert banners for WARNING states or above.
* Aggregated cross-asset margin view.

## 13. Future Engine Requirements (Phase 96–99)
* **Phase 96**: Implementation of the `MarginTradeGate` and unified `MarginSnapshot` schemas.
* **Phase 97**: Broker-specific margin adapter migrations (Oanda, Coinbase).
* **Phase 98**: Autonomous flattening agent for `LIQUIDATION_RISK` mitigation.
* **Phase 99**: Full Cross-Asset Margin Dashboard integration.

## 14. Certification Criteria
To consider the Institutional Margin Governance Framework complete and certified:
* This documentation must be committed to the governance repository.
* All future pull requests impacting margin must be evaluated against this document by the `GovernanceAuditorAgent`.
* No runtime execution logic may bypass the frameworks outlined herein.

## 15. Phase 95 Completion Assessment
* Document Phase 95 status: **COMPLETE**.
* Markdown verification: **PASSED**.
* Internal consistency review: **PASSED**.
* No runtime files modified.
