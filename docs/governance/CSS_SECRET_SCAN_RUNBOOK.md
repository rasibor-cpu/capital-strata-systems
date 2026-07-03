# CSS Secret Scan Runbook

## Purpose

This runbook defines the required pre-live secret scanning procedure. It must be completed before live broker validation and before any production operational certification.

Live broker validation, Live micro-pilot, and Production operational certification remain separate from this scan runbook.

## Required Tools

Use at least one full-history scanner and preferably both:

- `gitleaks`
- `trufflehog`

## Full-History Commands

Run from repository root:

```powershell
gitleaks detect --source . --redact --verbose
```

```powershell
trufflehog git file://$PWD --no-update --only-verified
```

For broader evidence capture, also run trufflehog without `--only-verified` and triage results without printing secret material into logs.

## Handling Findings

- Do not print secrets into chat, issue trackers, logs, or documentation.
- Record only scanner name, finding id, file path, commit hash if applicable, verification status, and remediation status.
- Rotate any credential that is confirmed or cannot be conclusively dismissed.
- Treat historical findings as active until rotation evidence exists.
- Do not proceed to live broker validation until confirmed findings are remediated or formally risk-accepted by the production certification owner.

## Lightweight Phase 151 Scan

During Phase 151, `gitleaks` and `trufflehog` were not installed locally. A lightweight current-worktree pattern scan was run with filename-only output. It reported one review candidate:

- `docs/governance/next_priority/signon_persistence_discovery.txt`

This lightweight scan is not a substitute for full-history gitleaks/trufflehog scanning.
