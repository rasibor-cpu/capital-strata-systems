# CSS Broker Failure Response Standard

## Broker Outage Detection
* **Mechanism:** The TradeDecisionOrchestrator and margin checks rely on heartbeats and API request success rates.
* **Threshold:** 3 consecutive API timeouts or connection resets within a 30-second window triggers an outage declaration.

## Broker Degradation Detection
* **Mechanism:** Latency monitoring on critical path API calls (e.g., order placement, margin snapshot).
* **Threshold:** API response times exceeding 2000ms for 5 consecutive requests triggers a degradation warning.

## Fail-Safe Behavior
* **Strict Fail-Closed:** If broker state cannot be verified (e.g., unknown margin state), the system explicitly fails closed. No new risk can be assumed.
* **Existing Orders:** Attempt to cancel any unacknowledged or pending open orders immediately via fallback network routes if available.

## Trade Suspension Procedures
* Automatic engagement of the `live_order_kill_switch` upon confirmed broker outage.
* All executing engines transition to a "HALTED" state.
* Mobile and Web dashboards will reflect the "HALTED" state and prevent any manual ticket submissions.

## Recovery Validation
* Once the broker signals healthy status, the system remains HALTED.
* A mandatory reconciliation process (`post_trade_reconciliation.py`) must be executed to align local ledgers with broker truth.
* Only after clean reconciliation can an authorized operator disengage the kill switch.
