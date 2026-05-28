# CSS Micro-Live Pilot Archive Naming And Retention Policy 2026

Status: DOCUMENTATION-ONLY ARCHIVE POLICY
Scope: Controlled micro-live pilot evidence archives
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This policy standardizes controlled micro-live pilot evidence artifact naming,
archive structure, retention guidance, redaction rules, chain-of-custody
metadata, and archive review cadence.

The policy supports auditability, retrieval, reconciliation, governance review,
and operator evidence continuity. It does not authorize trading. It does not
arm execution, approve trading, place orders, mutate broker state, bypass
governance gates, override a kill-switch, replace PCNRASS validation, create
approval-grant endpoints, enable unrestricted live trading, or activate
persistence.

## 2. Naming Convention

Use a stable artifact name that can be sorted by date/time and traced to the
pilot packet, phase, artifact type, broker, symbol, and evidence or
correlation ID when available.

General pattern:

```text
YYYYMMDD_HHMMSS_PACKETID_PHASE_ARTIFACTTYPE_BROKER_SYMBOL_EVIDENCEID.ext
```

Allowed phase values:

- PRE
- DURING
- POST
- INCIDENT
- PCNRASS
- BROKER
- REPLAY
- AUDIT

Recommended artifact type values:

- SCREENSHOT
- PDF
- JSON
- REPORT
- INCIDENT_WORKSHEET
- SIGN_OFF
- PCNRASS_LOG
- BROKER_SNAPSHOT
- LEDGER_SNAPSHOT
- REPLAY_EXPORT
- AUDIT_EXPORT

Broker and symbol values:

- Broker: `COINBASE_ADVANCED`
- Symbol: `BTC_USD`

Examples:

- `20260514_213000_MLPACKET001_PRE_SCREENSHOT_COINBASE_ADVANCED_BTC_USD_READINESS.png`
- `20260514_213100_MLPACKET001_PRE_JSON_COINBASE_ADVANCED_BTC_USD_DRYRUNPROBE.json`
- `20260514_213200_MLPACKET001_PRE_PDF_COINBASE_ADVANCED_BTC_USD_PACKETCHECKLIST.pdf`
- `20260514_213300_MLPACKET001_PRE_SIGN_OFF_COINBASE_ADVANCED_BTC_USD_SIGNOFF001.md`
- `20260514_213400_MLPACKET001_PCNRASS_PCNRASS_LOG_COINBASE_ADVANCED_BTC_USD_RUN001.txt`
- `20260514_214000_MLPACKET001_BROKER_BROKER_SNAPSHOT_COINBASE_ADVANCED_BTC_USD_BEFORE.pdf`
- `20260514_214500_MLPACKET001_POST_REPORT_COINBASE_ADVANCED_BTC_USD_POSTPILOT.md`
- `20260514_215000_MLPACKET001_INCIDENT_INCIDENT_WORKSHEET_COINBASE_ADVANCED_BTC_USD_INC001.md`

## 3. Recommended Folder Structure

Recommended archive root:

```text
artifacts/micro_live_pilot/YYYY-MM-DD/
  pre_pilot/
  during_pilot/
  post_pilot/
  screenshots/
  exports/
  incidents/
  pcnrass/
  broker_evidence/
```

Recommended packet-level folder:

```text
artifacts/micro_live_pilot/YYYY-MM-DD/PACKET_ID/
  pre_pilot/
  during_pilot/
  post_pilot/
  screenshots/
  exports/
  incidents/
  pcnrass/
  broker_evidence/
  replay/
  audit/
  manifest/
```

Storage guidance:

- Store screenshots in `screenshots/`.
- Store PDFs in `pre_pilot/`, `post_pilot/`, or `broker_evidence/` as
  appropriate.
- Store exported JSON in `exports/`.
- Store incident worksheets in `incidents/`.
- Store PCNRASS logs in `pcnrass/`.
- Store broker evidence snapshots in `broker_evidence/`.
- Store replay exports in `replay/`.
- Store audit exports in `audit/`.
- Store manifest and packet index records in `manifest/`.

## 4. Retention Policy

Retention guidance:

| Artifact Class | Recommended Retention | Notes |
| --- | --- | --- |
| Pre-pilot evidence | Minimum 7 years or governance-defined retention period | Preserve readiness, intent, dry-run, approval gate, broker confirmation, go/no-go, and checklist evidence |
| Post-pilot evidence | Minimum 7 years or governance-defined retention period | Preserve reconciliation, ledger/PnL, fill, fee, slippage, and conclusion records |
| Incident records | Minimum 7 years and until incident closure plus review period | Preserve root-cause, resolution, sign-off, and lessons learned |
| PCNRASS logs | Minimum 7 years or governance-defined release record period | Preserve immediate pre-pilot validation evidence |
| Broker snapshots | Minimum 7 years or broker/regulatory retention period, whichever is longer | Preserve before/after account and position evidence |
| Screenshots | Minimum 7 years when used as official evidence | Redact sensitive identifiers before archive |
| Exported JSON | Minimum 7 years when used as official evidence | Ensure secrets and private identifiers are redacted |

Retention extensions are required when:

- An incident remains open.
- Reconciliation remains incomplete.
- Broker/CSS balances diverge.
- Audit or replay evidence is incomplete.
- Governance review is pending.
- Legal, regulatory, or operator review requires preservation.

## 5. Redaction Rules

Artifacts must not contain:

- Secrets
- API keys
- Private keys
- PEM contents
- Raw broker tokens
- Full account numbers
- Passwords
- Authorization headers
- Unredacted credential payloads

Artifacts should redact:

- Sensitive personal identifiers
- Sensitive broker account identifiers
- Non-public account references
- Unnecessary raw broker payload fields
- Any operational credential metadata not needed for evidence review

Evidence integrity requirements:

- Preserve timestamp, source, status, and summary values.
- Preserve evidence IDs, correlation IDs, and audit IDs when safe.
- Replace sensitive values with `REDACTED`.
- Document redaction in chain-of-custody notes.
- Do not alter financial values, fill details, fee values, slippage values, or
  reconciliation conclusions unless correcting a documented error.

## 6. Archive Review Cadence

Required review cadence:

- Immediate post-pilot review
  - Confirm all required artifacts are present.
  - Confirm broker/CSS reconciliation evidence is archived.
  - Confirm any incident worksheet is created if needed.

- 24-hour review
  - Recheck archive completeness.
  - Recheck redaction and chain-of-custody notes.
  - Confirm unresolved blockers are tracked.

- 7-day review
  - Review final reconciliation and audit/replay completeness.
  - Confirm incident closure or escalation.
  - Confirm sign-off register and final operator conclusion are archived.

- Monthly governance review
  - Sample archives for completeness and redaction quality.
  - Review retention exceptions.
  - Confirm open incidents and blocked evidence packets are still tracked.

## 7. Chain-Of-Custody Notes

Every archived artifact should include or be accompanied by:

- Artifact creator
- Date/time created
- Source page, API, command, or broker source
- CSS branch
- Commit hash
- Tag if applicable
- PCNRASS status
- Packet ID
- Artifact ID
- Evidence ID or correlation ID where available
- Redaction status
- Archive path
- Notes

Recommended chain-of-custody entry:

```text
Artifact ID:
Created by:
Created at:
Source:
Branch:
Commit:
Tag:
PCNRASS status:
Packet ID:
Evidence/correlation ID:
Redaction status:
Archive path:
Notes:
```

## 8. Safety Disclaimers

- This archive policy does not arm trading.
- This archive policy does not approve trading.
- This archive policy does not execute or place orders.
- This archive policy does not mutate broker account state.
- This archive policy does not create approval-grant endpoints.
- This archive policy does not bypass the kill-switch.
- This archive policy does not replace final PCNRASS validation.
- This archive policy does not bypass broker readiness confirmation.
- This archive policy does not enable unrestricted live trading.
- This archive policy does not activate persistence.
- Incomplete archive artifacts mean the evidence chain is incomplete.
- Missing final PCNRASS evidence means NO-GO.
- Missing kill-switch confirmation evidence means NO-GO.
- Missing broker readiness evidence means NO-GO.

