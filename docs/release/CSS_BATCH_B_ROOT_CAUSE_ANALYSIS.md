# Batch B — Consolidated Root Cause Analysis

**Programme:** Release Gate 2  
**Batch:** B — Engineering Integrity (AR-005 … AR-010)  
**Date:** 2026-07-21  
**Status:** Implementation basis for Batch B

## Shared theme

Operator-facing and certification surfaces overstate readiness/execution capability when evidence is missing or when validation-only foundations emit “accepted/ready” semantics. The shared corrective principle is **fail-closed honesty**: missing evidence cannot PASS; validation cannot look like execution; unsupported or incomplete persistence cannot silently succeed.

## Per-item root causes

| AR | Finding | Root cause | Shared cluster |
| --- | --- | --- | --- |
| AR-005 | Phase 153i formatted summary omits Authority Reason | `STARTUP_SUMMARY_FIELDS` omits `"Authority Reason"` even though `build_live_startup_summary` sets it | Operator honesty |
| AR-006 | Multiple trading shells imply a complete engine | `CSSTradingEngine` is an unscored scan/print shell; no singular documented paper authority | Execution honesty |
| AR-007 | Unified pipeline returns `status=accepted` | Validation foundation emits execution-like acceptance without dispatch/journal | Execution honesty |
| AR-008 | Equities close can diverge from canonical outcomes | Lifecycle excludes `EQUITIES`; default `TradeRuntimeService` swallows lifecycle errors then closes DB | Lifecycle integrity |
| AR-009 | Empty health checkers score 100 | `HealthMonitor.calculate_health_score([])` treats absence as perfect health | Health fail-open |
| AR-010 | Missing telemetry scores ~90 PASS | `HealthValidator` defaults missing/empty evidence to 90+ (PASS band) | Health fail-open |

## Dependencies inside Batch B

```text
AR-005  (independent)
AR-009 ─┐
AR-010 ─┴─ health fail-closed cluster (independent of execution)
AR-006 ─┐
AR-007 ─┴─ execution honesty cluster (AR-006 documents authority; AR-007 renames validation semantics)
AR-008 ── lifecycle integrity (independent; supports honest paper close records)
```

No item in Batch B is blocked by AR-011/AR-028 for *implementation*. Those remain downstream consumers of the health fail-closed fixes.

## Smallest coherent implementation

1. **AR-005:** Add `"Authority Reason"` to `STARTUP_SUMMARY_FIELDS`.
2. **AR-006 + AR-007:** Mark `CSSTradingEngine` non-authoritative; declare `CanonicalExecutionIntegration` + validation-only `UnifiedExecutionPipeline` as the paper path; change pipeline status from `accepted` → `validated_not_executed` with non-execution reason.
3. **AR-008:** Add `EQUITIES` to canonical lifecycle; default strict persistence (never swallow lifecycle errors before DB close).
4. **AR-009 + AR-010:** Empty/missing health evidence scores `0.0` (FAIL), never PASS-band defaults.

## Safety constraints preserved

- Live mode remains rejected by unified pipeline.
- Startup summary keeps `execution_allowed=false` / `live_trading_blocked=true`.
- No new broker dispatch or live trading capability is introduced.
