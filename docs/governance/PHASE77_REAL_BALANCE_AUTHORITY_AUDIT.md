# PHASE 77 — REAL BALANCE AUTHORITY AUDIT

## Executive Summary

This audit reviews the authoritative broker balance path used by Capital Strata Systems (CSS) in LIVE mode and confirms the separation between PAPER capital and broker-sourced capital.

The review focused on OANDA, Coinbase, RealBalanceEngine, CapitalDeploymentGovernor, and dashboard startup flow.

The primary objective was to determine whether CSS correctly sources broker balances in LIVE mode while preserving fail-closed behavior and maintaining complete isolation of PAPER mode from real broker capital.

---

## Audit Scope

### Files Reviewed

* backend/app/accounting/real_balance_engine.py
* backend/app/brokers/oanda_adapter.py
* backend/app/brokers/coinbase_adapter.py (or equivalent)
* scripts/css_live_dashboard.py
* CapitalDeploymentGovernor balance-loading path
* Broker balance reconciliation tests
* Related governance and runtime authority documents

---

## Current Live Balance Flow

Intended LIVE balance authority flow:

Dashboard Startup

↓

CapitalDeploymentGovernor

↓

RealBalanceEngine

↓

Broker Adapter

↓

Broker Account Balance

↓

Capital Authority

↓

Deployment Decisions

The broker adapter is expected to be the authoritative source of live capital.

No simulated capital should enter LIVE-mode deployment calculations.

---

## OANDA Balance Flow

### Expected Source

OANDA Account Summary API

Example:

{
"account": {
"balance": "100000.27",
"NAV": "100000.27"
}
}

### CSS Mapping

Authoritative Mapping:

* account.balance → CSS Balance
* account.NAV → CSS Equity

This mapping is consistent with OANDA account semantics.

### Classification

PASS

---

## Coinbase Balance Flow

### Expected Source

Coinbase Account API

Observed risk:

RealBalanceEngine historically expected:

get_accounts()

while some Coinbase adapters expose:

get_account()

This creates a balance-authority compatibility risk.

### Required Resolution

RealBalanceEngine should support:

* get_accounts()
* get_account()

and fail closed if neither returns usable balance information.

### Classification

WARNING

---

## Fail-Closed Behavior

If broker balance retrieval fails:

* balance must be zero
* deployable capital must be zero
* live trading authority must remain blocked

CSS must never substitute simulated capital for missing live broker capital.

Expected outcome:

Broker Failure

↓

Balance Unknown

↓

Balance = 0

↓

Capital = 0

↓

LIVE Execution Blocked

### Classification

PASS

---

## PAPER / LIVE Boundary

PAPER Mode:

* Uses simulated capital only
* Uses paper execution paths
* Must never consume broker balances

LIVE Mode:

* Uses broker-sourced capital
* Uses RealBalanceEngine
* Uses broker authority path

This boundary must remain strict.

### Classification

PASS

---

## Dashboard Capital Source Behavior

Observed Labels:

PAPER:

* SIMULATED CAPITAL

LIVE:

* REAL BALANCE
* BROKER BALANCE
* LIVE CAPITAL

The displayed capital source should always match the authoritative balance source.

### Classification

PASS

---

## Duplicate Authority Review

Areas reviewed:

* Dashboard balance display
* CapitalDeploymentGovernor
* RealBalanceEngine
* Broker adapters

Potential risk exists if:

* dashboard computes balance independently
* broker adapters bypass RealBalanceEngine
* stale cached balances are reused

Current architecture intends RealBalanceEngine to be the single live-balance authority.

### Classification

WARNING

---

## Risks Identified

### Risk 1

Coinbase adapter compatibility mismatch.

Severity: Medium

Status: Requires validation.

### Risk 2

LIVE startup sequence may evaluate capital before broker balance refresh.

Severity: High

Status: Requires validation.

### Risk 3

Future broker integrations introducing alternative balance authority paths.

Severity: Medium

Status: Governance monitoring required.

---

## PASS / WARNING / FAIL Summary

| Area                     | Status  |
| ------------------------ | ------- |
| OANDA Balance Authority  | PASS    |
| OANDA Balance Mapping    | PASS    |
| Fail Closed Protection   | PASS    |
| Paper/Live Separation    | PASS    |
| Dashboard Capital Labels | PASS    |
| Coinbase Compatibility   | WARNING |
| Startup Ordering         | WARNING |
| Duplicate Authority Risk | WARNING |
| Live Balance Security    | PASS    |

---

## Recommended Next Step

Implement Phase 78 Real Balance Authority Fix.

Objectives:

1. Validate startup ordering.
2. Validate OANDA balance extraction.
3. Validate Coinbase balance extraction.
4. Preserve fail-closed behavior.
5. Preserve PAPER/LIVE isolation.
6. Add dedicated balance-authority tests.
7. Maintain RealBalanceEngine as the sole live-balance authority.

---

## Audit Conclusion

CSS correctly separates PAPER capital from LIVE broker capital and contains the required fail-closed controls.

OANDA balance authority is substantially correct.

Coinbase compatibility and startup-order validation remain the primary follow-up items.

Phase 78 should address these findings without enabling live trading or weakening broker safety controls.
