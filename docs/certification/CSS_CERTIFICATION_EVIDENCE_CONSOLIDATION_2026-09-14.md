# CSS Certification Evidence Consolidation — Cloud Closure Pass

## Purpose

This workstream resolves the remaining certification-register items that can be
proved safely in cloud CI, while keeping operator/runtime and external items
explicitly separate.

It does not reinterpret historical evidence registers as fully approved and it
does not manufacture runtime screenshots, live broker evidence, legal approval,
or human sign-off.

## Cloud-verifiable domains

The dedicated CI gate captures current deterministic evidence for:

- risk governor behavior;
- margin engine and canonical margin snapshots;
- MarginTradeGate and enforcement integration;
- broker margin contracts and simulated/practice adapters;
- broker guardrail foundations and broker registry behavior;
- credential-separation behavior;
- QRO replay/portfolio behavior;
- runtime health, heartbeat, operational state, and supervisor behavior;
- authentication/security controls;
- password-reset/recovery controls;
- permission matrix and mobile governance;
- mobile kill-switch visibility behavior;
- mode reconciliation;
- margin dashboard integration;
- full regression non-regression.

## Evidence classification rule

Historical `NOT_STARTED` entries are not automatically promoted. They are
classified as follows:

### CLOUD_VERIFIABLE
Items whose proof can be obtained from deterministic code/tests and repository
artifacts. These are exercised by
`.github/workflows/css_certification_evidence_consolidation.yml`.

### OPERATOR_EVIDENCE
Items that require a real sustained runtime, browser/mobile screenshots,
operator sign-on, restart/corruption drill capture, or COW-001 evidence.

### EXTERNAL_BLOCKER
Items that depend on Questrade/provider authorization, signed legal/regulatory
review, commercial specialist review, or other third-party action.

### HUMAN_APPROVAL
Items requiring Robert, operations, legal, risk, or reviewer acceptance cannot
be auto-approved by CI.

## Safety

This consolidation does not:

- enable live trading;
- arm broker execution;
- authorize money movement;
- introduce client-fund authority;
- expose credentials;
- claim live broker evidence.

The certified fail-closed posture remains authoritative.
