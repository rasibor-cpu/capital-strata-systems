# Phase 176J — Executive Brief Readiness Orchestrator

**Branch:** `css-unified-consolidation-2026-07-13`

## Problem

Daily Executive Brief generation could run before required evidence was fresh,
producing immediate fail-closed FAILED briefs (`runtime_stale_or_unavailable`,
`broker_stale_or_unavailable`, `portfolio_stale_or_unavailable`). That is an
orchestration defect, not a reporting-content defect.

## Solution

Canonical readiness layer:

1. `ExecutiveBriefReadinessEvaluator` → overall `READY` | `WAITING` | `FAILED`
2. Per-gate status `READY` | `STALE` | `UNAVAILABLE` | `ERROR`
3. Freshness policy JSON (not scheduler hard-codes)
4. `ExecutiveBriefReadinessOrchestrator` wait/retry loop
5. Retry history under `morning_briefings/readiness/`
6. Version `manifest.json` + brief `readiness_audit` phrase
7. Mission Control / mobile Reports UI shows Waiting for Runtime/Portfolio/Broker/Market

Fail-closed validation is unchanged. Broker unavailable never becomes READY.
