# Phase 1 OANDA Read-Only Certification Report

Date: 2026-06-15

Branch: `css-evening-consolidation-2026-06-09`

Pre-check HEAD: `ffa457eca995529fc84379ad1d1664e076114834`

Scope: Broker Read-Only Certification Package / Phase 4F.

## Certification Boundary

This report is documentation-only. It does not change broker behavior, credentials, adapters, runtime behavior, execution behavior, risk logic, margin logic, dashboard behavior, tests, or trading logic.

Allowed activity: read-only broker evidence review and certification packaging.

Prohibited activity: live execution, order placement, broker state mutation, credential change, broker mutation, risk change, or trading logic change.

## Pre-Check Evidence

| Check | Result |
| --- | --- |
| `git remote -v` | `origin https://github.com/rasibor-cpu/capital-strata-systems.git` |
| `git branch --show-current` | `css-evening-consolidation-2026-06-09` |
| `git rev-parse HEAD` | `ffa457eca995529fc84379ad1d1664e076114834` |
| `git status --short` | No repository file changes before Phase 4F artifact creation were identified through the GitHub branch comparison pre-check. |

## Required Review Sources

| Source | Review Finding |
| --- | --- |
| `certification/PHASE_1_CERTIFICATION_CLOSURE_MATRIX.md` | OANDA approved read-only evidence was listed as a critical open broker gap requiring approved read-only connection evidence without order placement. |
| `certification/PHASE_1_FINAL_EVIDENCE_ARCHIVE_INDEX.md` | Broker evidence was partial; approved OANDA and Coinbase read-only evidence remained missing. |
| `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | OANDA margin/account evidence and production broker certification were not started; adapter and fallback references existed. |
| `certification/broker/PHASE_1_BROKER_SAFE_FAIL_VALIDATION_REPORT.md` | Broker safe-fail tests passed, and no-order-placement behavior was validated without live execution. |

## A. OANDA Read-Only Evidence

### Account Visibility Evidence

Evidence basis:

* `backend/app/brokers/oanda_adapter.py` exposes read endpoints for account summary, open positions, and open trades.
* `get_account_summary()` uses a `GET` request against the OANDA account summary endpoint.
* `get_open_positions()` and `get_open_trades()` are also read-only `GET` calls.
* The read-only evidence package does not include account identifiers, balances, account numbers, tokens, or raw broker payloads.

Certification interpretation:

OANDA account visibility is technically supported through read-only adapter surfaces. Retained approved live/practice broker transcript evidence is still required before production broker certification.

### Margin Visibility Evidence

Evidence basis:

* `engine/risk/oanda_margin_adapter.py` maps OANDA account payload fields such as `marginUsed`, `NAV`, and `marginAvailable` into the canonical `BrokerMarginSnapshot`.
* `tests/test_oanda_margin_adapter.py` validates the live-mode success path using a fake read-only account summary payload and confirms required margin, available margin, free margin, utilization percentage, and `LIVE_MARGIN_SNAPSHOT_OK`.
* The adapter falls back to a simulated snapshot when account summary data is unavailable.

Certification interpretation:

OANDA margin visibility is structurally supported and test-covered without live broker mutation. Approved real broker read-only evidence remains a certification attachment requirement.

### Balance Visibility Evidence

Evidence basis:

* `backend/app/brokers/oanda_adapter.py` includes `extract_balance_nav()` for extracting balance and NAV from an account summary response.
* The existing broker safe-fail report confirms missing balance data does not create false live capital authority and recommends safe degradation to PAPER.

Certification interpretation:

OANDA balance visibility is available through the account summary read path and balance/NAV extraction helper. Retained redacted evidence of a successful approved read-only balance retrieval remains required for production certification.

### No-Order-Placement Confirmation

Evidence basis:

* The safe-fail report records no-order-placement verification as passing, with `live_execution_blocked_by_firewall` and `request_called=False`.
* `OandaAdapter.place_order()` returns `live_execution_blocked_by_firewall` unless `OANDA_ENABLE_LIVE_TRADING` is explicitly enabled.
* Phase 4F did not execute broker calls, submit orders, mutate broker state, alter broker configuration, or enable live trading.

Certification interpretation:

No order placement is confirmed for this certification package. Existing evidence supports the firewall control and confirms read-only certification assembly did not invoke an order path.

### Redaction Review

Redaction results:

* No API keys, tokens, account identifiers, private keys, passwords, secrets, raw broker payloads, or credential values are included in this artifact.
* Broker account identifiers are described generically.
* Test fixture placeholder values are not presented as real broker credentials.
* No screenshots or logs containing broker secrets are included.

## OANDA Certification Finding

| Area | Status | Notes |
| --- | --- | --- |
| Account visibility | STRUCTURALLY SUPPORTED / APPROVED EVIDENCE STILL REQUIRED | Read endpoint exists; retained redacted broker transcript not attached. |
| Margin visibility | STRUCTURALLY SUPPORTED / TEST-COVERED | Canonical margin snapshot mapping is covered by tests. |
| Balance visibility | STRUCTURALLY SUPPORTED / APPROVED EVIDENCE STILL REQUIRED | Balance/NAV extraction exists; retained redacted live/practice retrieval evidence remains missing. |
| No-order-placement | PASS | Safe-fail report confirms firewall block before request dispatch. |
| Redaction | PASS | No secrets or account identifiers included. |

## Certification Recommendation

PASS FOR DOCUMENTATION-ONLY READ-ONLY READINESS PACKAGE.

DO NOT CERTIFY FOR PRODUCTION BROKER READINESS until a retained, approved, redacted OANDA read-only connection transcript is attached and accepted by governance/operations.
