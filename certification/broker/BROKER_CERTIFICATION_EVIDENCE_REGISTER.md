# Broker Certification Evidence Register

## 1. Purpose

This register is the Phase 101E broker certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify broker evidence required for certification review, separate captured broker architecture claims from pending evidence attachments, and preserve the broker safety boundary during certification assembly. This document is documentation-only. It does not change broker behavior, credentials, adapters, runtime behavior, dashboard behavior, execution behavior, risk logic, margin logic, governance logic, or trading permissions.

No secrets, API keys, tokens, account IDs, credential values, or broker authentication material are included in this register.

## 2. Broker Certification Scope

Broker certification evidence covers broker selection, paper/practice separation, live mode authorization, real balance and capital synchronization, broker adapter behavior, broker-specific read-only evidence, and live execution blocking.

This register covers:

* broker selection evidence
* paper and practice broker evidence
* live broker mode evidence
* real balance and capital sync evidence
* broker adapter evidence
* OANDA evidence
* Coinbase evidence
* IBKR evidence
* live execution blocking evidence
* known broker evidence gaps

This register does not approve live trading or broker execution. It records broker evidence requirements and known gaps for certification review.

## 3. Broker Selection Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-SELECT-001 | Selected broker display evidence | Pending evidence attachment. | NOT_STARTED | Certification requires selected broker evidence and broker mode evidence. |
| BROKER-SELECT-002 | Broker mode display evidence | Pending evidence attachment. | NOT_STARTED | Runtime and dashboard evidence must distinguish simulated, paper, practice, and live contexts. |
| BROKER-SELECT-003 | Unsupported broker fallback evidence | Pending evidence attachment. | NOT_STARTED | Missing or unsupported broker data must fail safely or degrade to safe display-only fallback. |
| BROKER-SELECT-004 | Broker independence evidence | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Broker independence is defined as a certification principle; concrete runtime evidence remains pending. |

## 4. Paper / Practice Broker Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-PAPER-001 | Paper broker selection evidence | Pending evidence attachment. | NOT_STARTED | Controlled paper operation is the current recommended posture. |
| BROKER-PAPER-002 | Practice broker mode evidence | Pending evidence attachment. | NOT_STARTED | Practice mode must be visibly distinct from live mode. |
| BROKER-PAPER-003 | Paper run confirming no live order placement | Pending evidence attachment. | NOT_STARTED | Phase 101A identifies paper run proof with no live order placement as required evidence. |
| BROKER-PAPER-004 | Simulated broker source labeling evidence | Pending evidence attachment. | NOT_STARTED | Simulated and live sources must be clearly labeled. |
| BROKER-PAPER-005 | Paper/practice credential safety evidence | Pending evidence attachment. | NOT_STARTED | Evidence must confirm no secrets are exposed in logs, docs, screenshots, or commits. |

## 5. Live Broker Mode Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-LIVE-001 | Live mode explicit authorization evidence | Pending evidence attachment. | NOT_STARTED | Live broker mode requires explicit authorization and retained approval evidence. |
| BROKER-LIVE-002 | Live broker read-only evidence | Pending evidence attachment. | NOT_STARTED | Phase 101A requires OANDA and Coinbase read-only live evidence without trade placement. |
| BROKER-LIVE-003 | Live broker fallback evidence | Pending evidence attachment. | NOT_STARTED | Broker credential, account, API, and network failures must not crash CSS. |
| BROKER-LIVE-004 | Live mode credential non-disclosure evidence | Pending evidence attachment. | NOT_STARTED | Credential values must not be exposed in certification materials. |
| BROKER-LIVE-005 | Production broker certification approval | Pending evidence attachment. | NOT_STARTED | Phase 100C identifies production broker certification as missing. |

## 6. Real Balance / Capital Sync Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-CAPITAL-001 | Real balance retrieval evidence | Pending evidence attachment. | NOT_STARTED | Evidence must show approved read-only balance retrieval without exposing account identifiers or secrets. |
| BROKER-CAPITAL-002 | Capital sync evidence | Pending evidence attachment. | NOT_STARTED | Evidence must show how broker-reported capital is reconciled to CSS state under approved scope. |
| BROKER-CAPITAL-003 | Capital sync fallback evidence | Pending evidence attachment. | NOT_STARTED | Missing broker capital data must degrade safely and be visible to operators. |
| BROKER-CAPITAL-004 | Paper/live capital separation evidence | Pending evidence attachment. | NOT_STARTED | Certification must prove paper or simulated capital is not represented as live capital. |

## 7. Broker Adapter Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-ADAPTER-001 | Broker margin contract evidence | `engine/risk/broker_margin_contract.py`; `tests/test_broker_margin_contract.py` | REFERENCED | Existing margin evidence references canonical broker margin snapshot behavior; certification output attachment remains pending. |
| BROKER-ADAPTER-002 | OANDA margin adapter evidence | `engine/risk/oanda_margin_adapter.py`; `tests/test_oanda_margin_adapter.py` | REFERENCED | Existing adapter supports simulated fallback and live retrieval attempt; full live-read attachment remains pending. |
| BROKER-ADAPTER-003 | Coinbase margin adapter evidence | `engine/risk/coinbase_margin_adapter.py`; `tests/test_coinbase_margin_adapter.py` | REFERENCED | Existing adapter supports simulated fallback and Coinbase spot non-margin default behavior; full live-read attachment remains pending. |
| BROKER-ADAPTER-004 | Broker adapter execution isolation evidence | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Phase 100C records that margin adapters do not place trades; certification runtime proof remains pending. |
| BROKER-ADAPTER-005 | Adapter credential reuse evidence | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Phase 100C records credential infrastructure reuse for OANDA and Coinbase; no credential values are included. |

## 8. OANDA Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OANDA-001 | OANDA broker selection evidence | Pending evidence attachment. | NOT_STARTED | Must show OANDA selected under approved mode without exposing account values. |
| OANDA-002 | OANDA practice or paper mode evidence | Pending evidence attachment. | NOT_STARTED | Must distinguish OANDA practice from live context. |
| OANDA-003 | OANDA live read-only margin/account evidence | Pending evidence attachment. | NOT_STARTED | Phase 101A identifies this as missing broker evidence. |
| OANDA-004 | OANDA simulated fallback evidence | `engine/risk/oanda_margin_adapter.py`; `tests/test_oanda_margin_adapter.py` | REFERENCED | Existing adapter/test references support fallback behavior; retained test output remains pending. |
| OANDA-005 | OANDA execution isolation evidence | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Phase 100C records that the OANDA margin adapter does not place trades. |
| OANDA-006 | OANDA production broker certification | Pending evidence attachment. | NOT_STARTED | Production certification requires live-read evidence, operational validation, and approval. |

## 9. Coinbase Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| COINBASE-001 | Coinbase broker selection evidence | Pending evidence attachment. | NOT_STARTED | Must show Coinbase selected under approved mode without exposing account values. |
| COINBASE-002 | Coinbase paper or simulated evidence | Pending evidence attachment. | NOT_STARTED | Must distinguish simulated Coinbase evidence from live context. |
| COINBASE-003 | Coinbase live read-only account or margin-like evidence | Pending evidence attachment. | NOT_STARTED | Phase 101A identifies this as missing broker evidence. |
| COINBASE-004 | Coinbase spot non-margin default evidence | `engine/risk/coinbase_margin_adapter.py`; `tests/test_coinbase_margin_adapter.py` | REFERENCED | Existing adapter/test references cover spot non-margin default behavior; retained test output remains pending. |
| COINBASE-005 | Coinbase execution isolation evidence | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Phase 100C records that the Coinbase margin adapter does not place trades. |
| COINBASE-006 | Coinbase production broker certification | Pending evidence attachment. | NOT_STARTED | Production certification requires live-read evidence, operational validation, and approval. |

## 10. IBKR Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| IBKR-001 | IBKR broker scope decision | Pending evidence attachment. | NOT_STARTED | Current certification evidence references OANDA and Coinbase; IBKR scope requires explicit certification decision. |
| IBKR-002 | IBKR adapter evidence | Pending evidence attachment. | NOT_STARTED | No IBKR adapter evidence is attached in this broker certification package. |
| IBKR-003 | IBKR paper or simulated evidence | Pending evidence attachment. | NOT_STARTED | Required only if IBKR enters approved certification scope. |
| IBKR-004 | IBKR live read-only evidence | Pending evidence attachment. | NOT_STARTED | Required only if IBKR enters approved live-read scope. |
| IBKR-005 | IBKR execution blocking evidence | Pending evidence attachment. | NOT_STARTED | Required only if IBKR execution paths enter approved scope. |

## 11. Live Execution Blocking Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| BROKER-BLOCK-001 | No unauthorized live execution evidence | Pending evidence attachment. | NOT_STARTED | Unauthorized live execution path is a certification failure condition. |
| BROKER-BLOCK-002 | Live broker execution requires explicit authorization evidence | Pending evidence attachment. | NOT_STARTED | Phase 100A lists explicit authorization as required. |
| BROKER-BLOCK-003 | Unknown live broker or margin state fail-safe evidence | Pending evidence attachment. | NOT_STARTED | Missing broker data and unknown risk state must fail safely or fail closed where enforced. |
| BROKER-BLOCK-004 | Broker adapter read-only behavior evidence | Pending evidence attachment. | NOT_STARTED | Must prove read-only certification activities do not place orders. |
| BROKER-BLOCK-005 | Credential failure safe fallback evidence | Pending evidence attachment. | NOT_STARTED | Missing or invalid credentials must not crash CSS or expose secrets. |

## 12. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| BROKER-GAP-001 | OANDA live-read evidence is incomplete. | OANDA | Approved read-only OANDA account or margin evidence with secrets redacted or excluded. |
| BROKER-GAP-002 | Coinbase live-read evidence is incomplete. | Coinbase | Approved read-only Coinbase account or margin-like evidence with secrets redacted or excluded. |
| BROKER-GAP-003 | IBKR certification scope is not established. | IBKR | Explicit scope decision and evidence plan before any IBKR certification claims. |
| BROKER-GAP-004 | Paper/live broker separation evidence is not attached. | Broker Mode | Controlled runtime evidence showing paper/practice/live separation. |
| BROKER-GAP-005 | Real balance and capital sync evidence is not attached. | Capital Sync | Read-only balance and capital reconciliation evidence under approved scope. |
| BROKER-GAP-006 | Live execution blocking evidence is not attached. | Execution Safety | Proof that unauthorized live execution is blocked and broker read-only evidence does not place orders. |
| BROKER-GAP-007 | Production broker certification approvals are not attached. | Broker Certification | Final broker-specific operational approval and Robert review disposition. |

## 13. Certification Notes

This register is a broker evidence map, not a broker production approval.

Current broker certification posture:

* OANDA and Coinbase margin adapter references exist.
* OANDA and Coinbase fallback and read-only design claims are referenced in governance audit materials.
* Full OANDA and Coinbase live-read certification evidence remains pending.
* IBKR scope is not certified by this register.
* No broker secrets, account identifiers, API keys, tokens, or credential values are included.

Certification implication:

CSS may continue broker evidence assembly in controlled paper or approved read-only contexts. CSS is not production broker certified until broker evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No broker behavior was changed.
* No credentials were changed.
* No broker adapters were changed.
* No runtime behavior was changed.
* No dashboard behavior was changed.
* No execution behavior was changed.
* No risk behavior was changed.
* No margin behavior was changed.
* No trading logic was changed.
* No tests were modified.
