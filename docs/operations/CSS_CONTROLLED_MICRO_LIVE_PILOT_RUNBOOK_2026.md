# CSS Controlled Micro-Live Pilot Runbook 2026

Status: REVIEW ONLY
Scope: Controlled micro-live pilot preparation and post-pilot operations
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This runbook defines the manual operator process for a future controlled CSS
micro-live pilot. It is designed to preserve governance, auditability,
reconciliation, and fail-closed behavior before, during, and after any tightly
bounded pilot activity.

This runbook does not authorize trading by itself. It does not arm trading,
grant approval, bypass governance, place orders, mutate broker state, activate
or disable kill switches, or enable persistence.

## 2. Pilot Scope

Approved pilot scope for review:

- Broker: Coinbase Advanced
- Symbol: BTC-USD
- Order type: limit order only
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Order automation: prohibited
- Approval grant endpoint: prohibited
- Mandatory logging: required
- Mandatory post-trade pause: required
- Fail-closed behavior: required if any evidence or governance check fails

Anything outside this scope is not authorized by this runbook and must be
treated as NO-GO.

## 3. Required Evidence Pages And APIs

Operators must review the current evidence chain before considering any manual
pilot approval.

Pages:

- `/micro-live-pilot-readiness`
- `/micro-live-manual-pilot-checklist`

APIs:

- `/api/v1/micro-live-pilot-readiness`
- `/api/v1/micro-live-pilot-order-intent`
- `/api/v1/coinbase-micro-live-dry-run-probe`
- `/api/v1/micro-live-operator-approval-gate`
- `/api/v1/micro-live-broker-readiness-confirmation`
- `/api/v1/micro-live-pre-pilot-go-no-go`
- `/api/v1/micro-live-manual-pilot-checklist`

All evidence pages and APIs are review-only. They do not grant approval, arm
trading, submit orders, mutate broker state, or enable persistence.

## 4. Pre-Pilot Checklist

Before any manual pilot decision, the operator must confirm:

- Manual pilot checklist is generated and reviewed.
- Pilot readiness status is reviewed.
- Order-intent package confirms non-executing BTC-USD limit-order scope.
- Coinbase dry-run probe confirms no order submit and no broker mutation.
- Operator approval gate confirms approval has not been granted by CSS.
- Approval-grant endpoint does not exist.
- Broker readiness confirmation is reviewed.
- Final pre-pilot go/no-go evidence record is reviewed.
- Manual operator approval is recorded outside CSS evidence pages.
- Immediate pre-pilot kill-switch confirmation is completed.
- Final PCNRASS release check passes immediately before pilot consideration.
- Persistence remains disabled.
- Trading is not armed by any evidence page.

If any item fails or is unavailable, the pilot status is NO-GO.

## 5. Manual Operator Approval Reminder

Manual approval must be explicit, time-bound, and recorded outside the
read-only evidence pages. The approval must reference:

- Operator name or ID
- Date and time
- Pilot scope
- Evidence checklist ID
- Final pre-pilot go/no-go record ID
- Kill-switch confirmation status
- Final PCNRASS validation result

CSS evidence pages do not record approval and must not be treated as approval.

## 6. Immediate Kill-Switch Confirmation

Immediately before any pilot decision, the operator must confirm:

- Global live-order kill switch exists and is reachable.
- Kill-switch state is understood.
- Kill-switch has not been bypassed.
- No live order path may proceed without kill-switch confirmation.
- Operator understands how to halt pilot activity immediately.

If the kill-switch state cannot be verified, the pilot status is NO-GO.

## 7. Final PCNRASS Release Check

Immediately before any pilot decision, run the PCNRASS release check and record
the result in the post-pilot evidence template if a pilot proceeds.

Required command:

```powershell
.\.venv\Scripts\python.exe scripts\pcnrass_release_check.py
```

The pilot remains NO-GO if the release check fails, is incomplete, or cannot be
run.

## 8. Execution Observation Checklist

If a future manual pilot is separately approved and executed through an
approved path, the operator must observe:

- Broker selected: Coinbase Advanced
- Symbol: BTC-USD
- Order type: limit only
- Pilot capital not above CAD $15
- Slippage guard not above 0.35%
- No more than one live order
- No unexpected automation
- No unsupported asset or order type
- Broker order status
- Fill status
- Fees
- Slippage
- CSS ledger impact
- Dashboard display consistency
- Replay and audit event generation
- Kill-switch availability during observation

Any unexpected condition requires immediate pause and incident review.

## 9. Mandatory Post-Trade Pause

After any pilot activity, operators must pause before any further action.

During the pause:

- Do not place a second live order.
- Do not expand scope.
- Do not change live/paper mode.
- Do not alter credentials.
- Do not disable kill switches.
- Do not continue without reconciliation.

The pause remains in effect until post-pilot evidence is completed and reviewed.

## 10. Post-Pilot Reconciliation Checklist

After any future pilot activity, complete the post-pilot evidence template and
confirm:

- Broker balance before and after
- Broker position before and after
- CSS ledger before and after
- CSS PnL before and after
- Fees and commissions
- Slippage
- Fill price and quantity
- Order status
- Replay correlation IDs
- Audit event IDs
- Dashboard state consistency
- Mobile/web display consistency if applicable
- Kill-switch status after pilot
- Any incident or unexpected behavior

If broker and CSS state diverge, classify the pilot as reconciliation failure
until resolved.

## 11. Broker Balance Check

The operator must compare:

- Coinbase available balance before pilot
- Coinbase available balance after pilot
- Coinbase BTC position before pilot
- Coinbase BTC position after pilot
- Any pending orders or holds

No fake balance may be used for live-mode reconciliation.

## 12. CSS Ledger And PnL Check

The operator must compare:

- CSS ledger cash before and after
- CSS position state before and after
- Realized PnL
- Unrealized PnL
- Fees
- Slippage
- Execution costs
- Dashboard PnL display

CSS accounting must remain explainable and aligned with broker evidence.

## 13. Fee, Slippage, And Fill Review

Record:

- Intended limit price
- Submitted limit price if any approved pilot occurs
- Fill price
- Fill quantity
- Fee amount
- Fee currency
- Slippage percentage
- Whether slippage stayed within 0.35%
- Whether order size stayed within CAD $15

Any breach requires incident review.

## 14. Replay And Audit Event Review

Record:

- Replay correlation IDs
- Lifecycle IDs
- Audit event IDs
- Runtime event IDs if available
- Governance gate decisions
- Broker readiness evidence IDs
- Manual checklist ID
- Final go/no-go record ID

Replay and audit records should allow the pilot path to be reconstructed.

## 15. Incident Response Notes

Open an incident review if any of the following occur:

- Order outside BTC-USD
- Market order instead of limit order
- Capital above CAD $15
- Slippage above 0.35%
- More than one live order
- Broker mutation outside approved path
- Missing audit event
- Missing replay event
- Ledger/broker divergence
- UI mode mismatch
- Kill-switch unavailable
- PCNRASS failure
- Credential exposure
- Any unexpected automation

Incident review should preserve logs, screenshots, broker records, replay
records, and operator notes.

## 16. Explicit Non-Authorization Statement

This runbook is an operational governance document only. It does not authorize
trading by itself. It does not create any approval-grant endpoint. It does not
arm trading. It does not place orders. It does not mutate broker account state.
It does not bypass governance gates. It does not enable persistence.

Manual operator approval, immediate kill-switch confirmation, and a passing
final PCNRASS release check remain mandatory before any future controlled pilot
decision.

