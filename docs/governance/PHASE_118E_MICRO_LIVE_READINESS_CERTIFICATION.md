# Phase 118E: Micro-Live Readiness Certification

## Executive Summary
This document certifies that Capital Strata Systems (CSS) has completed the required technical and governance controls for a controlled Micro-Live Pilot using the OANDA adapter. All critical fail-closed systems, environment isolation layers, and slippage controls have been structurally verified. Auto-Flatten remains in simulation mode, requiring manual execution for any detected divergence during this specific pilot phase.

## Scope
* **Target Broker:** OANDA
* **Execution Engine:** Live Execution Mode
* **Governance Boundary:** Micro-Live Pilot (Maximum $1,000 USD Capital)

## Certification Details
* **Certification Date:** 2026-06-16
* **Current Branch:** `css-evening-consolidation-2026-06-09`
* **Current Commit:** `3b9001a97f62588a782aca51dd7027d1646747b1`
* **Current Test Count:** 436 Tests

## Readiness Matrix

| Control Category | Status | Notes |
| :--- | :--- | :--- |
| **Governance** | CERTIFIED | Canonical rule sets enforced. |
| **RBAC** | CERTIFIED | Role-based isolation established. |
| **Startup Reconciliation** | CERTIFIED | Synchronous mismatch detection. |
| **Post-Trade Reconciliation** | CERTIFIED | Execution-time validation. |
| **Continuous Reconciliation** | CERTIFIED | Heartbeat divergence detection. |
| **Repair Workflow** | CERTIFIED | Off-ledger manual repair state flow. |
| **Slippage Protection** | CERTIFIED | `priceBound` bounds via tick data. |
| **Broker Health Monitoring** | CERTIFIED | Decorators trigger exponential backoff. |
| **Environment Sanitization** | CERTIFIED | Cross-contamination strictly blocked. |
| **Auto-Flatten Simulation** | PARTIALLY CERTIFIED | Simulation mode proven; lacks live capability. |
| **Margin Controls** | CERTIFIED | Pre-trade margin exhaustion checks. |
| **PnL Controls** | CERTIFIED | Max drawdown and stress tests active. |

## Risk Register

| Risk | Mitigation | Residual Risk |
| :--- | :--- | :--- |
| **Orphaned Live Positions** | Heartbeat locks session; operator manually flattens via off-ledger repair workflow. | Medium |
| **Slippage on Execution** | Explicit `priceBound` injected into payload. Orders exceeding bounds are rejected. | Low |
| **Environment Leakage** | Explicit `os.environ` validation blocks startup if practice credentials contaminate live flow. | Low |
| **Rate Limit Blackouts** | Backoff loop stalls execution; heartbeat pauses until broker health returns to GREEN. | Low |

## Pilot Constraints
* **Maximum Capital:** $1,000 USD
* **Maximum Open Positions:** 3
* **Maximum Daily Loss:** $20
* **Maximum Total Pilot Loss:** $50
* **Maximum Duration:** 5 Active Trading Days

## Abort Conditions
The Micro-Live Pilot must be aborted immediately if ANY of the following occur:
1. `GHOST_LOCAL_POSITION` detected (Local ledger assumes exposure not found on broker).
2. Rate-limit backoff escalates past maximum retries causing a persistent `RED` health state.
3. Actual slippage exceeds expected slippage by >2 pips on any executed order.
4. Capital drawdown exceeds $20 in a single day.
5. In-flight order registry becomes hung for >5 minutes.

## Evidence Requirements
During and immediately following the pilot, the operator must capture:
* `css_live_dashboard.log` (Full session transcripts).
* Screenshots of `=== SECURITY STATUS ===` upon boot.
* OANDA broker statement (PDF) covering the 5-day period.
* Export of the internal `TradeLedger` database table.
* Any `RepairRecord` logs if divergences occur.

## Final Certification Decision

> [!IMPORTANT]
> **READY WITH CONDITIONS**

**Rationale:** CSS is structurally hardened to fail-closed on any error condition. The lack of Live Auto-Flatten requires an alert, vigilant operator during all active trading hours. The platform cannot currently "self-heal" live capital, meaning an orphaned position requires immediate human intervention via the manual repair workflow. The Micro-Live pilot is authorized precisely to validate the heartbeat detection layer with live capital before fully automating the flatten process.
