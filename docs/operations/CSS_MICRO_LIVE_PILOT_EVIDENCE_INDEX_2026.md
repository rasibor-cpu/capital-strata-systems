# CSS Micro-Live Pilot Evidence Archive Index 2026

Status: READ-ONLY EVIDENCE INDEX
Scope: Controlled micro-live pilot governance packet
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This document is the central evidence packet index for controlled micro-live
pilot review. It links the review-only dashboards, API evidence packages,
operator runbook, and post-pilot template required to evaluate a tightly
bounded CSS micro-live pilot.

This index does not authorize trading by itself. It does not arm trading,
grant approval, place orders, mutate broker state, bypass governance, create an
approval-grant endpoint, enable unrestricted live trading, or activate
persistence.

## 2. Pilot Scope

The only pilot scope currently indexed for review is:

- Broker: Coinbase Advanced only
- Symbol: BTC-USD only
- Order type: limit order only
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Automation: not authorized
- Scope expansion: not authorized

Anything outside this scope must be treated as NO-GO.

## 3. Required Evidence Chain

The operator evidence packet consists of these items:

1. Micro-live pilot readiness dashboard
   - UI: `/micro-live-pilot-readiness`
   - API: `/api/v1/micro-live-pilot-readiness`
   - Purpose: consolidated review of pilot readiness, constraints, blockers,
     restrictions, and safety state.

2. Order-intent evidence package
   - API: `/api/v1/micro-live-pilot-order-intent`
   - Purpose: non-executing BTC-USD limit-order intent evidence.

3. Coinbase dry-run probe evidence
   - API: `/api/v1/coinbase-micro-live-dry-run-probe`
   - Purpose: non-executing probe evidence showing order submit and broker
     mutation are not allowed.

4. Operator approval and kill-switch evidence gate
   - API: `/api/v1/micro-live-operator-approval-gate`
   - Purpose: review-only evidence that manual approval is still required,
     trading is not armed, no approval-grant endpoint exists, and kill-switch
     verification remains required.

5. Broker readiness confirmation
   - API: `/api/v1/micro-live-broker-readiness-confirmation`
   - Purpose: review-only Coinbase/BTC-USD/limit-order broker readiness
     confirmation without order submission or broker mutation.

6. Final pre-pilot go/no-go record
   - API: `/api/v1/micro-live-pre-pilot-go-no-go`
   - Purpose: final review-only evidence record summarizing whether the
     evidence chain is internally consistent.

7. Manual pilot checklist/export pack
   - UI: `/micro-live-manual-pilot-checklist`
   - API: `/api/v1/micro-live-manual-pilot-checklist`
   - Purpose: operator checklist/export surface for required, completed, and
     missing manual pilot items.

8. Controlled pilot runbook
   - Document:
     `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md`
   - Purpose: manual operator process before, during, and after a controlled
     pilot.

9. Post-pilot evidence template
   - Document:
     `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`
   - Purpose: reconciliation, replay/audit review, incident notes, and final
     operator conclusion after any separately approved pilot.

## 4. API And Page Reference Table

| Reference | UI Path | API Path | Purpose | Safety Status |
| --- | --- | --- | --- | --- |
| Pilot readiness | `/micro-live-pilot-readiness` | `/api/v1/micro-live-pilot-readiness` | Consolidated readiness review | Read-only, no execution |
| Order intent | N/A | `/api/v1/micro-live-pilot-order-intent` | Non-executing order-intent evidence | Review-only, execution disabled |
| Coinbase dry-run probe | N/A | `/api/v1/coinbase-micro-live-dry-run-probe` | Non-executing dry-run evidence | No submit, no broker mutation |
| Approval gate | N/A | `/api/v1/micro-live-operator-approval-gate` | Manual approval and kill-switch evidence | No approval grant, no trading arm |
| Broker readiness | N/A | `/api/v1/micro-live-broker-readiness-confirmation` | Final broker readiness evidence | No broker mutation, no order submit |
| Pre-pilot go/no-go | N/A | `/api/v1/micro-live-pre-pilot-go-no-go` | Final review-only go/no-go record | No execution, no approval |
| Manual checklist | `/micro-live-manual-pilot-checklist` | `/api/v1/micro-live-manual-pilot-checklist` | Operator checklist/export pack | No trading armed |
| Runbook | `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | N/A | Manual pilot operating process | Documentation only |
| Post-pilot template | `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md` | N/A | Post-pilot reconciliation record | Template only |

## 5. Final Pre-Pilot Checklist

Before any separately approved controlled pilot can be considered, the operator
must confirm:

- Explicit manual operator approval is recorded outside CSS evidence pages.
- Immediate pre-pilot kill-switch confirmation is complete.
- Final PCNRASS release check passes immediately before pilot consideration.
- Final broker readiness confirmation is current and reviewed.
- Manual pilot checklist/export pack is current and reviewed.
- Final pre-pilot go/no-go record is current and reviewed.
- Coinbase Advanced is the only broker target.
- BTC-USD is the only symbol.
- Limit order is the only order type.
- CAD $15 maximum pilot capital is preserved.
- 0.35% maximum slippage is preserved.
- Maximum one live order is preserved.
- No approval-grant endpoint exists.
- No evidence page arms trading.
- No unresolved git changes exist except explicitly documented exclusions.
- Any explicitly documented exclusion, such as an isolated submodule state, is
  recorded in the operator notes.

If any item is incomplete or uncertain, the pilot status is NO-GO.

## 6. Post-Pilot Archive Checklist

If a future pilot is separately approved and performed, the archive packet must
include:

- Completed post-pilot evidence template.
- Broker balance before and after.
- CSS ledger before and after.
- CSS PnL before and after.
- Broker/CSS reconciliation conclusion.
- Fees, slippage, and fill review.
- Replay correlation IDs.
- Lifecycle IDs where available.
- Runtime event IDs where available.
- Audit events reviewed.
- Governance decisions reviewed.
- Kill-switch status before, during, and after pilot.
- Incident notes completed if anything unexpected occurred.
- Final operator conclusion documented.
- Reviewer sign-off if required by governance.

## 7. Safety Disclaimers

- No page, API, document, checklist, or evidence packet arms trading.
- No evidence packet places orders.
- No evidence packet mutates broker account state.
- No evidence packet grants approval.
- No approval-grant endpoint is authorized by this index.
- No unrestricted live trading is authorized.
- No persistence activation is authorized.
- No governance gate may be bypassed.
- Manual operator approval remains external to the read-only evidence pages.
- Immediate kill-switch confirmation remains mandatory before any pilot
  decision.
- Final PCNRASS release check remains mandatory before any pilot decision.

## 8. Archive Packet Completion Record

Use this section as a manual index when assembling an operator packet.

- Pilot readiness dashboard reviewed:
- Order-intent evidence captured:
- Coinbase dry-run probe evidence captured:
- Operator approval gate evidence captured:
- Broker readiness confirmation captured:
- Pre-pilot go/no-go record captured:
- Manual pilot checklist/export captured:
- Runbook reviewed:
- Post-pilot template prepared:
- Manual approval record reference:
- Kill-switch confirmation reference:
- Final PCNRASS release check reference:
- Git status/exclusion note:
- Operator:
- Reviewer:
- Date/time:

