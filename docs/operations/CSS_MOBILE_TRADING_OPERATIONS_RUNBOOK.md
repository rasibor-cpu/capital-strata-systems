# CSS Mobile Trading Operations Runbook

## Overview

The CSS Mobile Interface provides an emergency and out-of-band pathway to observe and optionally execute trades from a mobile-optimized UI.

**CRITICAL POLICY CHANGE**: Mobile trading is no longer an independent execution path. All mobile trades, both paper and live, are fully governed by the Canonical CSS `TradeDecisionOrchestrator` and `ExecutionGate`. This ensures that volatility sizing, anti-bleed protections, drawdown scaling, and governance logic apply equivalently to mobile and dashboard trading.

## Operating Modes

The Mobile Interface defaults to a strict `MOBILE_READ_ONLY` mode. The active mode can be managed by a `SUPER_USER` via the System Controls (`/controls`) route.

*   `MOBILE_READ_ONLY`: The default fail-safe state. Allows observing the portfolio and logs but strictly blocks all trade submission attempts at the API boundary.
*   `MOBILE_PAPER_TRADING`: Routes orders through the canonical pipeline to the `CSS_PAPER` broker. Records fills in the `TradeLedger`.
*   `MOBILE_LIVE_TRADING_ARMED`: Authorizes live execution. Trades are evaluated by the institutional ExecutionGate. If approved, orders are sent to live brokers (e.g., OANDA, Coinbase).

## Arming Live Mobile Trading

To execute a live trade from the mobile interface, the following sequence is mandatory:

1.  **Global Broker State**: The overall `SELECTED_BROKER_MODE` in the primary CSS infrastructure must be `LIVE`. If the core is in `PAPER` mode, mobile live requests will be rejected by the orchestrator.
2.  **Mobile Controls Authorization**: A `SUPER_USER` must navigate to the Mobile Controls screen and set the **Mobile Trading Mode** to `MOBILE_LIVE_TRADING_ARMED`.
3.  **Authentication**: The user submitting the trade ticket must be authenticated with the `SUPER_USER` role.
4.  **Confirmation Phrase**: The operator must explicitly type `MOBILE LIVE` into the confirmation field of the mobile trade ticket.

## Audit and Telemetry

The Mobile Interface writes detailed telemetry directly to the mobile audit ledger, which is subsequently ingested by central audit.

**Audit Event Types:**
*   `mobile_mode_changed`: Logged when the mobile mode is altered.
*   `mobile_order_requested`: Logged instantly when a mobile ticket is received.
*   `mobile_order_approved`: Logged if the `ExecutionGate` permits the trade and ledger persistence succeeds.
*   `mobile_order_rejected`: Logged if RBAC, the Orchestrator, the ExecutionGate, or the kill switch blocks the trade. Reason codes include:
    *   `MOBILE_ORDERS_DISABLED`
    *   `MOBILE_LIVE_REQUIRES_SUPER_USER`
    *   `LIVE_CONFIRMATION_REQUIRED`
    *   `ORCHESTRATOR_GATE_REJECTED`
    *   `EXECUTION_GATE_REJECTED`

## Kill Switch

The **Live Order Kill Switch** overrides all other controls. If engaged via `/controls`, the `evaluate_live_order_kill_switch` function returns a blocked status, and the mobile API returns `GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED`, immediately terminating both paper and live trade workflows.
