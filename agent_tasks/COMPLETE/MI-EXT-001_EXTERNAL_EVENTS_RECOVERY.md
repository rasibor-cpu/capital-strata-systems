---
id: MI-EXT-001
status: COMPLETE
closed_at_utc: 2026-08-19T17:25:29Z
merged_pr: 59
merge_commit: f3c59ee4326261957e16500cf0519aad687c3865
lifecycle_reconciled_utc: 2026-08-19T18:59:40Z
priority: 125
risk: HIGH
owner: Cursor Cloud Agent MI-EXT-001 R2
base_branch: css-v1.0.1-maintenance
starting_head: e0676ce896b2eae682946e3619994d1dc0300da6
claimed_branch: css-mi-ext-001-recovery-r2
claimed_starting_head: e0676ce896b2eae682946e3619994d1dc0300da6
claimed_at_utc: 2026-08-19T17:15:00Z
review_ready_at_utc: 2026-08-19T17:55:00Z
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
pr_authority: DRAFT_TO_MAINTENANCE
live_trading_authority: NONE
draft_pr: 59
historical_reference_commit: 3c7a6b61de2f7784e794b9f186a440d0f50392b2
---

# MI-EXT-001 — External Events Recovery R2

## Objective

Recover advisory-only external-event intelligence onto current canonical
maintenance, integrating as diagnostics for TAI-001/TAI-002 ranking without
granting execution authority.

## Authority

- commit/push only on `css-mi-ext-001-recovery-r2`
- draft PR targeting `css-v1.0.1-maintenance` permitted
- merge not permitted
- live trading / broker credentials / execution-gate mutation: NONE
- RC-LIVE candidate must not be merged or cherry-picked wholesale

## Integration seam

External events attach as `external_event_intelligence` on
`AutonomousOpportunityIntelligenceEngine.analyze()`. Ranking does **not** add
event scores into `ranking_v2.weighted_score`. Mission Control exposes the
overlay beside TAI diagnostics. Unified Trade Gate remains the execution
authority.

## Validation

- `python3 -m py_compile` on changed Python files — PASS
- MI-EXT provenance (14) + hardening (11) + recovery (22): **47 passed / 0 failed**
- TAI-001 (11) + TAI-002 (14) + AOI (2) + ranking (10): **37 passed / 0 failed**
- market-regime engine (3) + regime intelligence (4) + intelligence orchestrator (8): **15 passed / 0 failed**
- Mission Control mc001 (12) + mc007a (8): **20 passed / 0 failed / 1 warning** (Starlette httpx deprecation in TestClient)
- Unified Trade Gate (5) + regime-aware weighting (7): **12 passed / 0 failed**
- Targeted total: **131 passed / 0 failed / 0 skipped / 1 warning**
- `git diff --check` — PASS
- Broader launcher-bound suites `test_trade_tab_opportunity_ranking.py` and `test_phase155ab_opportunity_intelligence.py` could not be collected in this environment (`ModuleNotFoundError: dotenv`). They import live-environment/broker loaders outside MI-EXT scope; required MC observability coverage is in mc001/mc007a.

## Safety

- advisory_only=true, execution_allowed=false, live_network_ingestion=false
- enabled catalogue sources remain FIXTURE_ONLY
- stale/future/conflict/TIER_4 evidence cannot raise rank
- favorable MI-EXT + TAI still BLOCK when Unified Trade Gate denies
- no changes to Unified Trade Gate, AntiBleedGuard, Capital Governor, Margin Gate,
  RBAC, kill switches, live TTL/leases, OANDA, FX governor, or live/paper defaults
