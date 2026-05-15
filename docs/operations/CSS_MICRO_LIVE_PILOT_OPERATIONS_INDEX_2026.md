# CSS Micro-Live Pilot Operations Index 2026

Status: DOCUMENTATION-ONLY OPERATIONS INDEX
Scope: Controlled micro-live pilot operations document set
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This index is the top-level navigation page for controlled micro-live pilot
operations. It ties Phase 30 through Phase 39 into one document set for
operator review, governance review, post-pilot reconciliation, archival review,
and NO-GO handling.

This index does not authorize trading. It does not arm execution, approve
trading, place orders, mutate broker state, bypass governance gates, override a
kill-switch, replace PCNRASS validation, create approval-grant endpoints,
enable unrestricted live trading, or activate persistence.

## 2. Scope

The controlled micro-live pilot document set applies only to this bounded
scope:

- Broker: Coinbase Advanced only
- Symbol: BTC-USD only
- Order type: limit order only
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Automation: not authorized
- Scope expansion: not authorized

Any requested scope outside these boundaries is NO-GO until a separate
governance review approves a new scope.

## 3. Document Map

| Phase | Document | Path | Purpose |
| --- | --- | --- | --- |
| 30 | Controlled pilot runbook | `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | Manual process before, during, and after a controlled micro-live pilot. |
| 30 | Post-pilot evidence template | `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md` | Post-pilot reconciliation, replay/audit review, incident notes, and final conclusion template. |
| 31 | Evidence archive index | `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md` | Central evidence packet index linking pages, APIs, runbook, and templates. |
| 32 | Packet print checklist | `docs/operations/CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md` | Printable operator cover sheet for packet identification, scope, evidence inclusion, and final confirmations. |
| 33 | Governance sign-off register | `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md` | Manual decision register for GO, NO-GO, deferred, review-required, and blocker rejection decisions. |
| 34 | Incident review worksheet | `docs/operations/CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md` | Worksheet for anomalies, blockers, mismatches, safety events, root-cause review, resolution, and closure. |
| 35 | Evidence bundle manifest | `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md` | Artifact ownership, completion status, archive location, and evidence reference manifest. |
| 36 | Archive naming and retention policy | `docs/operations/CSS_MICRO_LIVE_PILOT_ARCHIVE_NAMING_RETENTION_POLICY_2026.md` | Naming conventions, retention guidance, redaction rules, review cadence, and chain-of-custody notes. |
| 37 | Operator daily brief | `docs/operations/CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md` | One-page pre-session brief for scope, readiness, market context, constraints, safety decision, and notes. |
| 38 | NO-GO decision log | `docs/operations/CSS_MICRO_LIVE_PILOT_NO_GO_DECISION_LOG_2026.md` | Template for stopped, deferred, rejected, not-ready, and review-required decisions. |
| 39 | Readiness cross-reference map | `docs/operations/CSS_MICRO_LIVE_PILOT_READINESS_CROSS_REFERENCE_MAP_2026.md` | Risk-control map tying documents, APIs, UI pages, checklists, and evidence to operational protections. |

## 4. Recommended Usage Order

Recommended operator flow:

1. Complete the operator daily brief.
2. Review the evidence archive index.
3. Open the readiness review page and API evidence chain.
4. Complete the packet print checklist.
5. Record or review the governance sign-off register.
6. Run and record final PCNRASS validation.
7. Follow the controlled pilot runbook if a separately approved pilot is being
   considered.
8. Complete the post-pilot evidence template if a pilot ever occurs.
9. Complete the incident worksheet if any anomaly, blocker, mismatch, or safety
   concern appears.
10. Complete or update the evidence bundle manifest.
11. Complete the NO-GO decision log if the pilot is stopped, deferred,
    rejected, or marked not ready.
12. Use the readiness cross-reference map to confirm every risk has an
    evidence control and NO-GO trigger.

## 5. UI And API Evidence References

UI pages:

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

Evidence expectations:

- All evidence must remain read-only.
- `execution_allowed` must remain false where applicable.
- `order_submit_allowed` must remain false where applicable.
- `broker_mutation_allowed` must remain false where applicable.
- `trading_armed` must remain false where applicable.
- Persistence must remain disabled.
- No approval-grant endpoint may exist.

## 6. Safety Rules

- This index does not arm trading.
- This index does not approve trading.
- This index does not execute or place orders.
- This index does not mutate broker account state.
- This index does not create approval-grant endpoints.
- This index does not bypass the kill-switch.
- This index does not replace final PCNRASS validation.
- This index does not bypass broker readiness confirmation.
- This index does not enable unrestricted live trading.
- This index does not activate persistence.
- Final PCNRASS validation remains mandatory before any future controlled pilot
  decision.
- Immediate kill-switch confirmation remains mandatory before any future
  controlled pilot decision.
- Incomplete evidence remains NO-GO.
- Unresolved HIGH or CRITICAL incidents remain NO-GO.
- Unresolved broker, credential/security, ledger/PnL, replay/audit, or
  git/release integrity issues remain NO-GO.

## 7. Next Maturity Layer

Future candidates after this documentation layer:

- Immutable evidence hashing
  - Hash each official evidence artifact and record the digest in the bundle
    manifest.

- Operator action audit ledger
  - Add a governed audit record for manual operator review actions without
    enabling trading.

- Post-pilot reconciliation workflow
  - Convert the post-pilot reconciliation template into a guided, read-only
    workflow.

- Hard live execution firewall
  - Add explicit execution firewall controls that must remain closed unless a
    separate governance-controlled live execution process is approved.

These future candidates must preserve PCNRASS, fail closed, and remain
separate from unrestricted live trading.

