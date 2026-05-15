# CSS Micro-Live Pilot Readiness Cross-Reference Map 2026

Status: DOCUMENTATION-ONLY CROSS-REFERENCE MAP
Scope: Controlled micro-live pilot governance and operational risk controls
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This map explains how the controlled micro-live pilot governance chain
controls operational and governance risk. It ties every relevant document, API,
UI page, checklist, and evidence artifact to the protection it provides.

The map is intended to help operators and reviewers answer:

- Which risk is controlled by each evidence artifact?
- Which page, API, document, or checklist proves the control?
- Who is responsible for review?
- What validation is required?
- What failure condition triggers NO-GO?

This map does not authorize trading. It does not arm execution, approve
trading, place orders, mutate broker state, bypass governance gates, override a
kill-switch, replace PCNRASS validation, create approval-grant endpoints,
enable unrestricted live trading, or activate persistence.

## 2. Pilot Scope Reminder

The controlled pilot evidence chain applies only to:

- Broker: Coinbase Advanced only
- Symbol: BTC-USD only
- Order type: limit order only
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Automation: not authorized
- Scope expansion: not authorized

Any artifact or review path outside this scope is out of policy and must be
treated as NO-GO until corrected.

## 3. Risk Categories

Tracked readiness risks:

- Unauthorized execution risk
- Broker mutation risk
- Governance bypass risk
- Kill-switch failure risk
- Replay/audit integrity risk
- Reconciliation mismatch risk
- Operator error risk
- Credential/security risk
- Market volatility/slippage risk
- Incomplete evidence risk
- Stale readiness evidence risk
- Git/release integrity risk

## 4. Cross-Reference Matrix

| Risk Category | Risk Description | Controlling Document/Page/API | Evidence Artifact | Responsible Operator/Reviewer | Validation Method | Related PCNRASS Requirement | Failure Consequence | NO-GO Trigger Condition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Unauthorized execution risk | A page, packet, or workflow could be mistaken as permission to trade. | `/api/v1/micro-live-pilot-order-intent`, `/micro-live-manual-pilot-checklist`, `CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md` | Order-intent package, manual checklist, packet checklist | Operator and reviewer | Confirm `execution_allowed`, `order_submit_allowed`, and `trading_armed` remain false | Runtime smoke, web smoke, dashboard/engine tests | Accidental execution or operator confusion | Any evidence suggests execution is allowed or trading is armed |
| Broker mutation risk | Evidence review could accidentally mutate Coinbase account state. | `/api/v1/coinbase-micro-live-dry-run-probe`, `/api/v1/micro-live-broker-readiness-confirmation` | Dry-run probe, broker readiness confirmation | Operator | Confirm `broker_mutation_allowed` remains false and no submit path is invoked | Py compile, dashboard/engine tests, runtime smoke | Broker account state changes outside approval | Any broker mutation flag or submit path is enabled |
| Governance bypass risk | Manual approval, RBAC, or governance gates could be skipped. | `/api/v1/micro-live-operator-approval-gate`, `CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md` | Approval gate, sign-off register | Reviewer | Confirm no approval-grant endpoint exists and manual sign-off is external | Web smoke, auth smoke, PCNRASS release check | Pilot proceeds without valid governance review | Missing sign-off, endpoint grants approval, or governance status is unclear |
| Kill-switch failure risk | Pilot consideration could proceed without immediate kill-switch confirmation. | `/api/v1/micro-live-operator-approval-gate`, `CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md`, `CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md` | Kill-switch evidence, runbook, daily brief | Operator | Confirm kill-switch checked immediately before pilot review | Runtime smoke, web smoke, PCNRASS release check | Operator cannot halt unsafe activity | Kill-switch unavailable, unverified, bypassed, or stale |
| Replay/audit integrity risk | Pilot path cannot be reconstructed or reviewed. | `/api/v1/trade-lifecycle-replay`, `CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`, `CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md` | Replay IDs, audit events, post-pilot template, bundle manifest | Operator and reviewer | Capture correlation IDs, audit events, replay exports, and notes | Dashboard/engine tests, runtime smoke | Loss of explainability or audit gap | Missing replay IDs, missing audit events, or unreconciled event mismatch |
| Reconciliation mismatch risk | Broker balances and CSS ledger/PnL diverge. | `CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`, `CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | Broker before/after, CSS ledger before/after, PnL review | Operator and reviewer | Compare broker balances, CSS ledger, PnL, fees, fill, and slippage | Dashboard/engine tests, PCNRASS release check | Accounting truth is uncertain | Any unreconciled broker/CSS balance, position, fee, or PnL mismatch |
| Operator error risk | Operator misses a step or acts outside the defined scope. | `CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md`, `CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md`, `CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | Daily brief, packet checklist, runbook | Operator | Complete daily brief and packet checklist before review | Web smoke, auth smoke, PCNRASS release check | Wrong broker, symbol, order type, size, or process | Missing daily brief, incomplete packet checklist, or scope mismatch |
| Credential/security risk | Evidence archive or payload exposes secrets or sensitive identifiers. | `CSS_MICRO_LIVE_PILOT_ARCHIVE_NAMING_RETENTION_POLICY_2026.md`, `/api/v1/micro-live-broker-readiness-confirmation` | Redacted exports, broker readiness evidence, archive notes | Operator and reviewer | Confirm no secrets, API keys, private keys, tokens, or full account numbers are archived | Frontend payload tests, dashboard/engine tests | Credential exposure or privacy breach | Any unredacted secret, raw token, private key, or sensitive account identifier |
| Market volatility/slippage risk | Market conditions make the tiny pilot unsafe or unrepresentative. | `CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md`, `CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | Market/session context, daily decision, operator notes | Operator | Review volatility, spread, liquidity, and session stability | Manual review plus final PCNRASS check | Slippage exceeds cap or execution quality is poor | Spread, volatility, liquidity, or session condition is unstable |
| Incomplete evidence risk | Required packet artifacts are missing. | `CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md`, `CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md` | Evidence index, bundle manifest, packet checklist | Operator | Confirm required pre-pilot artifacts are complete | PCNRASS release check, markdown sanity, reviewer check | Pilot review lacks required support | Any required artifact is missing, blocked, stale, or not applicable without explanation |
| Stale readiness evidence risk | Readiness evidence is not refreshed immediately before review. | `/micro-live-pilot-readiness`, `/api/v1/micro-live-broker-readiness-confirmation`, `CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md` | Readiness dashboard, broker confirmation, daily brief | Operator | Refresh readiness, broker confirmation, kill-switch, and PCNRASS before review | Runtime smoke, web smoke, PCNRASS release check | Operator relies on stale state | Broker readiness, kill-switch, PCNRASS, or evidence packet is stale |
| Git/release integrity risk | Code state is unclean or unverified at review time. | `CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md`, `CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md`, `scripts/pcnrass_release_check.py` | Git status notes, commit hash, tag, PCNRASS log | Operator and reviewer | Record branch, commit, tag, documented exclusions, and release check output | Full PCNRASS release check | Pilot review does not match validated code | PCNRASS fails, git state is undocumented, or commit/tag is missing |
| Blocker escalation risk | NO-GO blockers are not tracked to owner and closure. | `CSS_MICRO_LIVE_PILOT_NO_GO_DECISION_LOG_2026.md`, `CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md` | NO-GO log, incident worksheet | Reviewer | Assign owner, fix, validation, re-review date, and closure status | PCNRASS release check before close | Known blocker recurs or is ignored | Unresolved HIGH/CRITICAL incident or blocker remains open |
| Archive retrieval risk | Evidence exists but cannot be found or trusted later. | `CSS_MICRO_LIVE_PILOT_ARCHIVE_NAMING_RETENTION_POLICY_2026.md`, `CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md` | Archive folder, manifest, chain-of-custody notes | Operator | Confirm naming, path, retention, redaction, and custody notes | Markdown sanity, reviewer check | Audit evidence cannot be retrieved | Missing archive path, missing custody note, or unredacted artifact |

## 5. Evidence Artifact Reference List

Core UI and API evidence:

- Readiness dashboard: `/micro-live-pilot-readiness`
- Pilot readiness API: `/api/v1/micro-live-pilot-readiness`
- Order-intent package: `/api/v1/micro-live-pilot-order-intent`
- Coinbase dry-run probe: `/api/v1/coinbase-micro-live-dry-run-probe`
- Operator approval gate: `/api/v1/micro-live-operator-approval-gate`
- Broker readiness confirmation: `/api/v1/micro-live-broker-readiness-confirmation`
- Pre-pilot go/no-go record: `/api/v1/micro-live-pre-pilot-go-no-go`
- Manual pilot checklist: `/micro-live-manual-pilot-checklist`
- Manual pilot checklist API: `/api/v1/micro-live-manual-pilot-checklist`

Core documents:

- Runbook: `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md`
- Post-pilot evidence template: `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`
- Evidence index: `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md`
- Packet print checklist: `docs/operations/CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md`
- Sign-off register: `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md`
- Incident worksheet: `docs/operations/CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md`
- Evidence bundle manifest: `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md`
- Archive naming and retention policy: `docs/operations/CSS_MICRO_LIVE_PILOT_ARCHIVE_NAMING_RETENTION_POLICY_2026.md`
- Operator daily brief: `docs/operations/CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md`
- NO-GO decision log: `docs/operations/CSS_MICRO_LIVE_PILOT_NO_GO_DECISION_LOG_2026.md`

## 6. Operational Flow Summary

Intended review flow:

1. Pre-pilot preparation
   - Review pilot scope.
   - Generate or review all evidence artifacts.
   - Complete the daily brief and packet checklist.
   - Confirm no unresolved blockers.

2. Review
   - Review readiness dashboard, order intent, dry-run probe, approval gate,
     broker confirmation, pre-pilot go/no-go, and manual checklist.
   - Complete the evidence bundle manifest and archive index.
   - Record decision in the sign-off register.

3. Approval consideration
   - Confirm manual operator approval externally.
   - Confirm kill-switch immediately before any pilot decision.
   - Run final PCNRASS release check.
   - Confirm git status and documented exclusions.

4. Pilot observation, only if separately approved
   - Observe one BTC-USD limit-order pilot within CAD $15 and 0.35% slippage.
   - Maintain no second order, no market order, no leverage expansion, and no
     additional symbols.
   - Pause immediately after any pilot action.

5. Post-pilot reconciliation
   - Complete post-pilot evidence template.
   - Compare broker before/after and CSS ledger/PnL before/after.
   - Capture fees, slippage, fill details, replay IDs, and audit events.
   - Open incident worksheet for any anomaly.

6. Archival review
   - Archive evidence using naming and retention policy.
   - Record chain-of-custody notes.
   - Perform immediate, 24-hour, 7-day, and monthly review cadence as needed.

## 7. Safety Disclaimers

- This map does not authorize trading.
- This map does not arm execution.
- This map does not approve trading.
- This map does not execute or place orders.
- This map does not mutate broker account state.
- This map does not create approval-grant endpoints.
- This map does not bypass the kill-switch.
- This map does not replace final PCNRASS validation.
- This map does not bypass broker readiness confirmation.
- This map does not enable unrestricted live trading.
- This map does not activate persistence.
- Unresolved high-risk items remain NO-GO.
- Final PCNRASS validation remains mandatory before any future controlled pilot
  decision.
- Immediate kill-switch confirmation remains mandatory before any future
  controlled pilot decision.

