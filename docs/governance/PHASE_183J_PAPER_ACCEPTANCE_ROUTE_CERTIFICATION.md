# Phase 183J — Paper Acceptance Route Certification

**Repository:** `capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Baseline (pre-fix):** `500e8b523f3f426103a4bb4aec2b8a67d7026c55`  
**Status:** DEFECT REMEDIATED

## Problem

RC-003R could not obtain any accepted paper order. All mobile paper tickets failed with:

`ORCHESTRATOR_GATE_REJECTED` / `rejected: probability below threshold`

## Root cause

Classification: **implementation defect** (not an intentional production threshold).

`dashboard/mobile/mobile_app.py` injected hard-coded paper market-data defaults:

- `probability = 0.51`
- `confidence = 0.51`
- `validation_source = MOBILE_PAPER_TEST_DEFAULTS`

`CSSUnifiedTradeGate` rejects when `probability < ENGINE_MODE_PROBABILITY_THRESHOLD[mode]`:

| Mode | Threshold |
| --- | ---: |
| SAFE | 0.65 |
| CONSERVATIVE | 0.60 |
| BALANCED | 0.58 |
| AGGRESSIVE | 0.55 |
| EXPANSION | 0.52 |

`0.51` is below **every** documented mode threshold, so the real orchestrator path can never approve a mobile paper ticket that uses these defaults. Unit tests masked this by mocking the orchestrator.

Production strategy / live thresholds were not wrong; the paper fallback was inconsistent with the gate it feeds.

## Remediation (minimum)

1. Align mobile paper fallback probability (and confidence) to the selected ticket `engine_mode` threshold from `ENGINE_MODE_PROBABILITY_THRESHOLD` (default `0.58`). Explicitly set `cost = 0.0` so the EV/cost check is well-formed.

2. Supply finite paper-only ExecutionGate microstructure inputs (`expected_move_bps`, fee/spread/slippage, regime persistence, vol/regime state). Live continues to pass `None` and remain fail-closed on missing anti-bleed inputs.

Does **not**:

- lower global probability thresholds
- bypass orchestrator / risk / execution gates
- change live-trading behavior
- disable firewall / quarantine

## Acceptance path note

RC-003R correctly used the mobile paper ticket → orchestrator → `CSSUnifiedTradeGate` path. There is no separate certified “ignore probability” paper route for that surface. OI-010 / Options Income certification paths are product-specific and were not the RC-003R route.

## Follow-on

Re-run RC-003R paper order + P&L sections after this commit.
