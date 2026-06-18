# CSS Paper Trading Operations Runbook

## Purpose

This runbook defines daily controlled PAPER-mode operating procedures for Capital Strata Systems. It is documentation-only and does not alter runtime, dashboard, broker, execution, credential, risk, margin, or trading logic.

## Daily Startup

1. Follow `docs/operations/CSS_STARTUP_RUNBOOK.md`.
2. Confirm branch, HEAD, operator context, session state, legal acceptance, and dashboard status.
3. Confirm PAPER, PRACTICE, or SIMULATION mode.
4. Confirm live mode is not enabled and live execution is not armed.
5. Record startup evidence in the certification package when a certification run is planned.

## Monitoring Responsibilities

The operator monitors:

* Runtime startup and heartbeat messages.
* Selected broker and broker mode.
* Dashboard mode labels.
* Signal generation output.
* Trade gate decisions.
* Paper position state.
* Realized and unrealized PnL.
* Margin dashboard and margin trade gate visibility.
* Audit or runtime event logs.
* Shutdown and session cleanup output.

## Signal Review

For each observed signal, capture or review:

| Signal Field | Review Expectation |
| --- | --- |
| Instrument or symbol | Must be supported for paper operation. |
| Asset class | Must match expected scan universe. |
| Direction | BUY, SELL, or FLAT. |
| Strength | Must be visible or derivable from runtime output. |
| Regime/style | Should be visible where supported. |
| Source | Must be CSS runtime/simulation signal source, not manual live order input. |

If signal output appears stale, corrupt, unsupported, or inconsistent with the selected mode, stop new paper trade creation and record an incident.

## Trade Gate Review

Before a paper position is created, verify evidence for:

* AntiBleedGuard result.
* MarginTradeGate result.
* RiskGovernor result.
* ExecutionGate final decision.
* Block reason if blocked.
* PAPER or simulated margin source.

Only controlled paper trade creation may proceed after an allowed gate decision. A blocked gate decision must not be overridden during certification operation.

## Paper Position Review

For each paper position:

1. Confirm position was created only after a gate `ALLOW`.
2. Confirm instrument, side, quantity, entry price, and timestamp/step are recorded.
3. Confirm no broker submit-order path was invoked.
4. Monitor position status updates.
5. Confirm position lifecycle remains within paper/simulated state.

## PnL Review

Review:

* Unrealized PnL while position is open.
* Realized PnL when position closes.
* Ledger or journal update.
* Current equity.
* Open position count.
* Any drawdown or risk messages.

PnL evidence is operational visibility and certification evidence. It is not production accounting approval.

## Shutdown Checklist

1. Stop new signal intake or paper position creation.
2. Confirm open paper positions have expected status.
3. Capture final PnL and position summaries.
4. Close the runtime session where supported.
5. Preserve logs, evidence files, and dashboard captures.
6. Confirm no live broker execution occurred.
7. Record warnings, incidents, and recommendations.

## Daily Evidence Checklist

| Evidence | Required For Certification Run |
| --- | --- |
| Git precheck | Yes |
| Startup/session/legal acceptance output | Yes |
| Dashboard startup and mode confirmation | Yes |
| Signal output | Yes |
| Trade gate decision | Yes |
| Paper entry/position lifecycle | Yes |
| Exit and PnL lifecycle | Yes |
| Shutdown output | Yes |
| Issues/warnings summary | Yes |

## Escalation Triggers

Escalate if:

* Live mode appears unexpectedly.
* Broker execution is invoked.
* Credential values appear in logs.
* Trade gates are bypassed.
* Legal acceptance blocks or cannot be verified.
* Session state is corrupt or unknown.
* PnL or position lifecycle becomes inconsistent.
* Dashboard displays contradictory broker/mode state.

Escalation follows `docs/operations/CSS_INCIDENT_RESPONSE_RUNBOOK.md`.
