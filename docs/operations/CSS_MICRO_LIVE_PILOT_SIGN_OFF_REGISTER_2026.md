# CSS Micro-Live Pilot Governance Sign-Off Register 2026

Status: DOCUMENTATION-ONLY SIGN-OFF REGISTER
Scope: Controlled micro-live pilot manual governance decisions
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This register is the formal manual log for controlled micro-live pilot
operator and reviewer decisions. It is used to record approvals for manual
review, rejections, deferrals, review-required states, and NO-GO decisions.

This register does not authorize trading by itself. It does not arm trading,
execute orders, mutate broker state, override kill-switch controls, bypass
governance gates, replace final PCNRASS validation, replace broker readiness
confirmation, create approval-grant endpoints, enable unrestricted live
trading, or activate persistence.

Decision types recorded in this register:

- GO_FOR_MANUAL_PILOT_REVIEW
- NO_GO
- DEFERRED
- REVIEW_REQUIRED
- REJECTED_DUE_TO_BLOCKER

## 2. Register Fields

Every sign-off entry should capture:

- Register entry ID
- Date/time
- Operator or reviewer name
- Role
- Decision type
- Pilot scope
- CSS branch
- CSS commit hash
- PCNRASS status
- Evidence packet ID
- Packet print checklist ID
- Manual pilot checklist ID
- Pre-pilot go/no-go record ID
- Broker readiness confirmation ID
- Coinbase dry-run probe ID
- Kill-switch confirmation status
- Final broker readiness refresh status
- Git status and documented exclusions
- Notes
- Signature or initials

## 3. Decision Categories

### GO_FOR_MANUAL_PILOT_REVIEW

Use only when the evidence packet is complete enough for manual pilot review.
This decision does not place an order and does not arm trading. It means the
packet may be reviewed by the authorized operator or reviewer under the
controlled pilot governance process.

### NO_GO

Use when the pilot should not proceed because a required control, evidence
item, governance condition, broker readiness condition, or PCNRASS condition is
missing or failed.

### DEFERRED

Use when the decision is intentionally delayed pending additional evidence,
operator availability, broker readiness refresh, reconciliation work, or
governance review.

### REVIEW_REQUIRED

Use when evidence is available but requires additional human review before a
GO_FOR_MANUAL_PILOT_REVIEW or NO_GO decision can be recorded.

### REJECTED_DUE_TO_BLOCKER

Use when a specific blocker prevents pilot consideration. The blocker must be
recorded in the blocker log with owner, required fix, and re-review date.

## 4. Required Supporting Evidence

Attach or reference all applicable evidence before recording anything other
than NO-GO or DEFERRED:

- Evidence index:
  `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md`
- Packet print checklist:
  `docs/operations/CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md`
- Controlled pilot runbook:
  `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md`
- Post-pilot evidence template:
  `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`
- Readiness dashboard:
  `/micro-live-pilot-readiness`
- Order-intent package:
  `/api/v1/micro-live-pilot-order-intent`
- Coinbase dry-run probe:
  `/api/v1/coinbase-micro-live-dry-run-probe`
- Operator approval and kill-switch evidence gate:
  `/api/v1/micro-live-operator-approval-gate`
- Broker readiness confirmation:
  `/api/v1/micro-live-broker-readiness-confirmation`
- Pre-pilot go/no-go record:
  `/api/v1/micro-live-pre-pilot-go-no-go`
- Manual pilot checklist:
  `/micro-live-manual-pilot-checklist`

## 5. NO-GO / Blocker Log

Use this section to record any blocker that prevents pilot review or pilot
consideration.

| Blocker ID | Description | Severity | Owner | Required Fix | Re-Review Date | Resolution Notes |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |

Severity examples:

- BLOCKER
- SAFETY
- GOVERNANCE
- BROKER
- RECONCILIATION
- DOCUMENTATION
- REVIEW

## 6. Blank Sign-Off Table

Use this table for manual sign-off records.

| Entry ID | Date/Time | Name | Role | Decision Type | Pilot Scope | Branch | Commit Hash | PCNRASS Status | Evidence Packet ID | Packet Checklist ID | Manual Checklist ID | Go/No-Go Record ID | Broker Readiness ID | Kill-Switch Status | Notes | Signature/Initials |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | Coinbase Advanced / BTC-USD / limit / CAD $15 / 0.35% / one order |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | Coinbase Advanced / BTC-USD / limit / CAD $15 / 0.35% / one order |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | Coinbase Advanced / BTC-USD / limit / CAD $15 / 0.35% / one order |  |  |  |  |  |  |  |  |  |  |  |

## 7. Safety Disclaimers

- This register does not arm trading.
- This register does not execute orders.
- This register does not create approval inside CSS.
- This register does not create an approval-grant endpoint.
- This register does not override the kill-switch.
- This register does not replace final PCNRASS validation.
- This register does not bypass broker readiness confirmation.
- This register does not mutate broker account state.
- This register does not enable unrestricted live trading.
- This register does not activate persistence.
- This register does not replace the controlled pilot runbook.

Manual operator approval, immediate kill-switch confirmation, final broker
readiness refresh, clean git-state review, and a passing final PCNRASS release
check remain mandatory before any future controlled pilot decision.

