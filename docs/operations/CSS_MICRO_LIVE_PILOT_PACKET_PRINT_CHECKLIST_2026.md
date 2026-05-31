# CSS Micro-Live Pilot Packet Print Checklist 2026

Status: PRINTABLE OPERATOR COVER SHEET
Scope: Controlled micro-live pilot evidence archive packet
Authority: Capital Strata Systems PCNRASS governance

This checklist is a printable cover sheet for assembling a controlled
micro-live pilot evidence packet. It is documentation only. It does not
authorize trading, arm execution, create approval, bypass governance, mutate
broker state, place orders, enable unrestricted live trading, or activate
persistence.

## 1. Packet Identification

- Packet ID:
- Date prepared:
- Time prepared:
- Operator name:
- Operator ID:
- Reviewer name:
- CSS branch:
- CSS commit hash:
- PCNRASS status:
- PCNRASS command reference:
- Evidence index reference:
- Notes:

## 2. Pilot Scope Confirmation

Confirm each item before the packet is considered complete.

| Item | Required Value | Confirmed |
| --- | --- | --- |
| Broker | Coinbase Advanced only | [ ] |
| Symbol | BTC-USD only | [ ] |
| Order type | Limit order only | [ ] |
| Maximum pilot capital | CAD $15 | [ ] |
| Maximum slippage | 0.35% | [ ] |
| Maximum live orders | 1 | [ ] |
| Automation | Not authorized | [ ] |
| Scope expansion | Not authorized | [ ] |

Any scope mismatch means the packet is incomplete and the pilot status is
NO-GO.

## 3. Evidence Included Checklist

| Evidence Item | Reference | Included |
| --- | --- | --- |
| Readiness dashboard reviewed | `/micro-live-pilot-readiness` | [ ] |
| Order-intent package reviewed | `/api/v1/micro-live-pilot-order-intent` | [ ] |
| Coinbase dry-run probe reviewed | `/api/v1/coinbase-micro-live-dry-run-probe` | [ ] |
| Approval and kill-switch gate reviewed | `/api/v1/micro-live-operator-approval-gate` | [ ] |
| Broker readiness confirmation reviewed | `/api/v1/micro-live-broker-readiness-confirmation` | [ ] |
| Go/no-go evidence reviewed | `/api/v1/micro-live-pre-pilot-go-no-go` | [ ] |
| Manual pilot checklist reviewed | `/micro-live-manual-pilot-checklist` | [ ] |
| Controlled pilot runbook attached | `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | [ ] |
| Post-pilot evidence template attached | `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md` | [ ] |
| Evidence index attached | `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md` | [ ] |

## 4. Final Pre-Pilot Confirmations

These confirmations must be completed immediately before any separately
approved controlled pilot decision.

| Confirmation | Required State | Confirmed |
| --- | --- | --- |
| Manual operator approval recorded externally | Yes | [ ] |
| Kill-switch checked immediately before pilot | Yes | [ ] |
| Final PCNRASS release check passed | Yes | [ ] |
| Final broker readiness refreshed immediately before pilot | Yes | [ ] |
| No unresolved git changes except documented exclusions | Yes | [ ] |
| CSS-CLAUDE exclusion documented if intentionally dirty | Yes or N/A | [ ] |
| No approval-grant endpoint exists | Yes | [ ] |
| No evidence page arms trading | Yes | [ ] |
| No persistence activation | Yes | [ ] |

Git status / exclusion notes:

- Main repository status:
- CSS-CLAUDE status if excluded:
- Other exclusions:

## 5. Post-Pilot Evidence Confirmations

Complete these fields after any separately approved pilot activity.

| Evidence Item | Required Record | Completed |
| --- | --- | --- |
| Broker balance before recorded | Cash, BTC, holds, open orders | [ ] |
| Broker balance after recorded | Cash, BTC, holds, open orders | [ ] |
| CSS ledger before recorded | Cash, position, PnL, execution cost | [ ] |
| CSS ledger after recorded | Cash, position, PnL, execution cost | [ ] |
| Fills recorded | Price, quantity, status | [ ] |
| Fees recorded | Amount and currency | [ ] |
| Slippage recorded | Estimated and actual | [ ] |
| Replay correlation IDs recorded | All applicable IDs | [ ] |
| Audit events reviewed | All relevant audit entries | [ ] |
| Incident notes completed | Required if unexpected condition occurred | [ ] |
| Final operator conclusion written | PASS / REVIEW REQUIRED / FAIL | [ ] |

## 6. Signature Block

- Operator conclusion:
- Operator signature:
- Operator date/time:
- Reviewer conclusion:
- Reviewer signature:
- Reviewer date/time:

## 7. Safety Disclaimer

This checklist does not authorize trading. It does not arm execution. It does
not create approval. It does not create an approval-grant endpoint. It does not
place orders. It does not mutate broker account state. It does not bypass
governance gates. It does not enable unrestricted live trading. It does not
activate persistence.

Manual operator approval, immediate kill-switch confirmation, final broker
readiness refresh, and a passing final PCNRASS release check remain mandatory
before any future controlled pilot decision.

