# Micro-Live Pilot Evidence Register

This register details the artifacts and logs that must be captured during the Phase 119A Micro-Live Pilot to achieve final institutional sign-off.

## Required Evidence

1. **Startup logs**: `css_live_dashboard.log` containing the `=== SECURITY STATUS ===` output.
2. **Reconciliation logs**: Output of continuous heartbeat logs showing state deltas.
3. **Trade logs**: Records of all executed strategy orders.
4. **Broker execution logs**: OANDA API responses mapping to TradeLedger entries.
5. **Slippage logs**: Persisted differences between `expected_price` and `actual_fill_price`.
6. **Margin logs**: Margin exhaustion metrics captured pre-trade.
7. **Repair records**: Any formally generated `RepairRecord` instances during the pilot.
8. **Daily summaries**: End-of-day equity, PnL, and drawdown summaries.
9. **Broker statements**: Official PDF/CSV exports directly from the OANDA Web Portal.

## Collection Frequency
* **Live System Logs (1-7):** Captured continuously via standard output routing.
* **Daily Summaries (8):** Captured at the conclusion of each active trading day.
* **Broker Statements (9):** Captured once at the end of the 5-day pilot.

## Evidence Owner
* Primary Operator

## Retention Requirements
* All evidence must be retained indefinitely in cold storage within the CSS repository evidence partition to satisfy future institutional auditing.
