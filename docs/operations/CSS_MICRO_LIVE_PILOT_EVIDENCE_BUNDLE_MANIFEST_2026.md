# CSS Micro-Live Pilot Evidence Bundle Manifest 2026

Status: DOCUMENTATION-ONLY EVIDENCE MANIFEST
Scope: Controlled micro-live pilot evidence packet completeness
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This manifest is the central checklist for controlled micro-live pilot evidence
packet completeness. It tracks every artifact required before, during, and
after pilot review, including the expected owner, phase, completion status,
archive location, evidence reference, and notes.

This manifest does not authorize trading. It does not arm execution, approve
trading, place orders, mutate broker state, bypass governance gates, override a
kill-switch, create approval-grant endpoints, enable unrestricted live trading,
or activate persistence.

## 2. Pilot Scope

The controlled pilot evidence bundle applies only to this bounded scope:

- Broker: Coinbase Advanced only
- Symbol: BTC-USD only
- Order type: limit order only
- Maximum pilot capital: CAD $15
- Maximum slippage: 0.35%
- Maximum live orders: 1
- Automation: not authorized
- Scope expansion: not authorized

Any evidence bundle that references a different broker, symbol, order type,
capital limit, slippage limit, or order count must be treated as incomplete and
NO-GO until corrected.

## 3. Manifest Fields

Each artifact entry should include:

- Artifact ID
- Artifact name
- Document, API, or UI path
- Owner
- Required phase: pre-pilot / during-pilot / post-pilot
- Status: NOT_STARTED / IN_PROGRESS / COMPLETE / BLOCKED / NOT_APPLICABLE
- Archive location
- Evidence ID or reference
- Notes

## 4. Required Pre-Pilot Artifacts

| Artifact ID | Artifact Name | Document/API/UI Path | Owner | Required Phase | Status | Archive Location | Evidence ID/Reference | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PRE-001 | Pilot readiness dashboard | `/micro-live-pilot-readiness` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-002 | Order intent package | `/api/v1/micro-live-pilot-order-intent` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-003 | Coinbase dry-run probe | `/api/v1/coinbase-micro-live-dry-run-probe` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-004 | Operator approval gate | `/api/v1/micro-live-operator-approval-gate` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-005 | Broker readiness confirmation | `/api/v1/micro-live-broker-readiness-confirmation` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-006 | Pre-pilot go/no-go evidence record | `/api/v1/micro-live-pre-pilot-go-no-go` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-007 | Manual pilot checklist/export pack | `/micro-live-manual-pilot-checklist` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-008 | Evidence archive index | `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-009 | Packet print checklist | `docs/operations/CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-010 | Sign-off register | `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md` | Operator/Reviewer | pre-pilot | NOT_STARTED |  |  |  |
| PRE-011 | Incident review worksheet | `docs/operations/CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md` | Operator/Reviewer | pre-pilot | NOT_STARTED |  |  | If needed |
| PRE-012 | Controlled pilot runbook | `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md` | Operator | pre-pilot | NOT_STARTED |  |  |  |
| PRE-013 | Final PCNRASS result | `scripts/pcnrass_release_check.py` output | Operator | pre-pilot | NOT_STARTED |  |  | Must pass immediately before pilot review |
| PRE-014 | Final git commit/tag reference | Git status, commit, and tag notes | Operator | pre-pilot | NOT_STARTED |  |  | Document CSS-CLAUDE exclusion if intentionally dirty |

## 5. During-Pilot Artifacts

These artifacts are required only if a pilot is separately approved and occurs.
They do not authorize execution.

| Artifact ID | Artifact Name | Document/API/UI Path | Owner | Required Phase | Status | Archive Location | Evidence ID/Reference | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DUR-001 | Operator observation notes | Manual operator notes | Operator | during-pilot | NOT_STARTED |  |  |  |
| DUR-002 | Kill-switch state confirmation | Manual confirmation record | Operator | during-pilot | NOT_STARTED |  |  | Before and during pilot |
| DUR-003 | Order ticket preview if applicable | Approved execution path evidence | Operator | during-pilot | NOT_APPLICABLE |  |  | Preview only unless separately approved |
| DUR-004 | Execution observation log if pilot occurs | Manual execution observation log | Operator | during-pilot | NOT_APPLICABLE |  |  | One live order maximum |
| DUR-005 | Incident worksheet if needed | `docs/operations/CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md` | Operator/Reviewer | during-pilot | NOT_APPLICABLE |  |  | Required for anomaly or blocker |

## 6. Post-Pilot Artifacts

These artifacts are required only after any separately approved pilot activity.

| Artifact ID | Artifact Name | Document/API/UI Path | Owner | Required Phase | Status | Archive Location | Evidence ID/Reference | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST-001 | Post-pilot evidence template | `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md` | Operator | post-pilot | NOT_STARTED |  |  |  |
| POST-002 | Broker balance before/after | Broker export or screenshot | Operator | post-pilot | NOT_STARTED |  |  | Cash, BTC, holds, open orders |
| POST-003 | CSS ledger before/after | CSS dashboard/ledger evidence | Operator | post-pilot | NOT_STARTED |  |  | Cash, position, PnL, costs |
| POST-004 | Fee, slippage, and fill review | Post-pilot template section | Operator | post-pilot | NOT_STARTED |  |  | Must verify 0.35% slippage cap |
| POST-005 | Replay correlation IDs | Replay/API/export evidence | Operator | post-pilot | NOT_STARTED |  |  | Capture all applicable IDs |
| POST-006 | Audit event review | Audit/replay evidence | Operator/Reviewer | post-pilot | NOT_STARTED |  |  | Include missing event notes |
| POST-007 | Incident notes | Incident worksheet if needed | Operator/Reviewer | post-pilot | NOT_APPLICABLE |  |  | Required if anomaly occurred |
| POST-008 | Final operator conclusion | Post-pilot evidence template | Operator | post-pilot | NOT_STARTED |  |  | PASS / REVIEW REQUIRED / FAIL |

## 7. Archive Guidance

Recommended archive root:

```text
artifacts/micro_live_pilot/YYYYMMDD_PACKET_ID/
```

Recommended folder structure:

```text
artifacts/micro_live_pilot/YYYYMMDD_PACKET_ID/
  00_manifest/
  01_pre_pilot/
  02_during_pilot/
  03_post_pilot/
  screenshots/
  exported_json/
  pdf/
  logs/
  incidents/
```

Recommended naming convention:

```text
YYYYMMDD_HHMMSS_PACKETID_ARTIFACTID_DESCRIPTION.ext
```

Examples:

- `20260514_213000_MLPACKET001_PRE001_readiness_dashboard.png`
- `20260514_213100_MLPACKET001_PRE003_coinbase_dry_run_probe.json`
- `20260514_214000_MLPACKET001_POST002_broker_balance_after.pdf`
- `20260514_214500_MLPACKET001_POST005_replay_correlation_ids.json`

Storage guidance:

- Store screenshots in `screenshots/`.
- Store rendered PDFs in `pdf/`.
- Store exported JSON in `exported_json/`.
- Store logs in `logs/`.
- Store incident worksheets in `incidents/`.
- Store the completed manifest in `00_manifest/`.
- Do not store credentials, API tokens, private keys, PEM contents, or raw
  secrets in any archive path.

## 8. Safety Disclaimers

- This manifest does not arm trading.
- This manifest does not approve trading.
- This manifest does not execute or place orders.
- This manifest does not mutate broker account state.
- This manifest does not create approval-grant endpoints.
- This manifest does not bypass the kill-switch.
- This manifest does not replace final PCNRASS validation.
- This manifest does not bypass broker readiness confirmation.
- This manifest does not enable unrestricted live trading.
- This manifest does not activate persistence.
- Incomplete required pre-pilot artifacts mean NO-GO.
- Unresolved HIGH or CRITICAL incidents mean NO-GO.
- Unresolved broker, kill-switch, credential/security, PCNRASS, ledger/PnL, or
  replay/audit issues block pilot consideration.

## 9. Bundle Completion Summary

- Packet ID:
- Prepared by:
- Prepared date/time:
- Pre-pilot artifacts complete:
- During-pilot artifacts complete or not applicable:
- Post-pilot artifacts complete or not applicable:
- Archive root:
- Final PCNRASS result:
- Git status reviewed:
- CSS-CLAUDE exclusion documented if applicable:
- Final bundle status: NOT_STARTED / IN_PROGRESS / COMPLETE / BLOCKED / NOT_APPLICABLE
- Operator signature:
- Reviewer signature:

