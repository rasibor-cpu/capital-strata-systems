# CSS Post-Pilot Evidence Template 2026

Status: TEMPLATE ONLY
Scope: Controlled micro-live pilot evidence capture
Authority: Capital Strata Systems PCNRASS governance

This template is for operator records after any separately approved controlled
micro-live pilot. It does not authorize trading, arm trading, grant approval,
place orders, mutate broker state, bypass governance, or enable persistence.

## 1. Pilot Identification

- Pilot date:
- Pilot start time:
- Pilot end time:
- Operator:
- Operator ID:
- Reviewer:
- CSS branch/commit:
- PCNRASS release check command:
- PCNRASS release check result:
- Manual checklist ID:
- Final pre-pilot go/no-go record ID:
- Broker readiness confirmation ID:
- Coinbase dry-run probe ID:
- Order-intent ID:

## 2. Pilot Scope

- Broker: Coinbase Advanced
- Symbol: BTC-USD
- Order type: limit
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Approved side:
- Intended limit price:
- Intended notional:
- Intended quantity:
- Approval reference:

## 3. Actual Result

- Was an order submitted:
- Submitted order ID:
- Submitted side:
- Submitted order type:
- Submitted limit price:
- Submitted notional:
- Submitted quantity:
- Actual result:
- Fill status:
- Filled quantity:
- Average fill price:
- Partial fill notes:
- Cancellation status:
- Rejection status:
- Rejection reason:

## 4. Fees, Slippage, And PnL

- Fee amount:
- Fee currency:
- Estimated slippage:
- Actual slippage:
- Slippage within 0.35%:
- Realized PnL:
- Unrealized PnL:
- Net PnL:
- Execution cost:
- Notes:

## 5. Broker Balance Evidence

Before pilot:

- Broker cash balance:
- Broker BTC balance:
- Broker open orders:
- Broker holds:
- Screenshot or export reference:

After pilot:

- Broker cash balance:
- Broker BTC balance:
- Broker open orders:
- Broker holds:
- Screenshot or export reference:

Broker reconciliation conclusion:

- Balances reconcile:
- Positions reconcile:
- Divergence amount:
- Divergence explanation:

## 6. CSS Ledger Evidence

Before pilot:

- CSS cash balance:
- CSS BTC position:
- CSS realized PnL:
- CSS unrealized PnL:
- CSS execution cost:
- Dashboard state reference:

After pilot:

- CSS cash balance:
- CSS BTC position:
- CSS realized PnL:
- CSS unrealized PnL:
- CSS execution cost:
- Dashboard state reference:

CSS ledger reconciliation conclusion:

- Ledger reconciles to broker:
- PnL reconciles:
- Fee treatment verified:
- Slippage treatment verified:
- Divergence explanation:

## 7. Replay And Audit Evidence

- Replay correlation IDs:
- Lifecycle IDs:
- Runtime event IDs:
- Audit event IDs:
- Governance gate decision IDs:
- Broker readiness evidence IDs:
- Order-intent evidence ID:
- Dry-run probe evidence ID:
- Manual checklist ID:
- Final go/no-go evidence ID:
- Replay viewer export reference:
- Audit viewer export reference:

Event review conclusion:

- Signal path explainable:
- Governance path explainable:
- Broker path explainable:
- Ledger path explainable:
- Dashboard path explainable:
- Missing events:

## 8. Kill-Switch And Safety State

- Kill-switch confirmed immediately before pilot:
- Kill-switch state during pilot:
- Kill-switch state after pilot:
- Kill-switch bypass detected:
- Trading armed by evidence page:
- Approval-grant endpoint used:
- Persistence enabled:
- Unexpected automation detected:

Safety conclusion:

- Safety controls remained intact:
- Fail-closed behavior verified:
- Notes:

## 9. Incident Notes

- Incident occurred:
- Incident category:
- Severity:
- Description:
- Time detected:
- Immediate action taken:
- Operator response:
- Broker response:
- CSS response:
- Evidence preserved:
- Follow-up owner:
- Follow-up due date:

## 10. Final Operator Conclusion

- Pilot outcome: PASS / REVIEW REQUIRED / FAIL
- Broker reconciliation status:
- CSS ledger reconciliation status:
- Replay/audit status:
- UI/dashboard status:
- Risk/governance status:
- Recommended next action:
- Operator signature:
- Reviewer signature:
- Date/time completed:

## 11. Non-Authorization Statement

This evidence template records observations only. It does not authorize further
trading, expand pilot scope, arm trading, grant approval, mutate broker state,
bypass governance, or enable persistence. Any future pilot or production step
requires a separate governance review, immediate kill-switch confirmation, and a
passing PCNRASS release check.

