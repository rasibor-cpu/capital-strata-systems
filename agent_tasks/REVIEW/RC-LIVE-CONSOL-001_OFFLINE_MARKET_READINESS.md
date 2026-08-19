---
id: RC-LIVE-CONSOL-001
status: REVIEW
priority: 130
risk: LOW
owner: Cursor Cloud Agent RC-LIVE-CONSOL-001
base_branch: css-v1.0.1-maintenance
starting_head: f3c59ee4326261957e16500cf0519aad687c3865
claimed_branch: css-rclive-offline-market-readiness-consolidated
claimed_starting_head: f3c59ee4326261957e16500cf0519aad687c3865
claimed_at_utc: 2026-08-19T17:30:00Z
review_ready_at_utc: 2026-08-19T18:20:00Z
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
pr_authority: DRAFT_TO_MAINTENANCE
live_trading_authority: NONE
draft_pr: 60
historical_reference_commits: 15b83a32, f0efcba3, 840c56f5
---

# RC-LIVE-CONSOL-001 — Offline Market Contracts, Deterministic Providers & Read-Only Broker Certification

## Objective

Consolidate still-valuable low-risk portions of RC-LIVE Phases 185A, 186A, and
187A onto current canonical maintenance as one recovery: versioned market/FX
contracts, deterministic offline providers, and an offline OANDA read-only
certification framework.

## Authority

- commit/push only on `css-rclive-offline-market-readiness-consolidated`
- draft PR targeting `css-v1.0.1-maintenance` permitted
- merge not permitted
- live trading / broker credentials / execution-gate mutation: NONE
- RC-LIVE candidate must not be merged or cherry-picked wholesale

## Integration seam

New package `backend/app/market/` is data/intelligence/certification
infrastructure only. Default providers remain `NOT_AVAILABLE`. Fixture providers
are `OFFLINE_CERTIFICATION_ONLY`. Live network construction fails closed.
Not wired into ExecutionGate, AntiBleedGuard, Unified Trade Gate, capital
sizing, or live authority.

The historical AntiBleed-shaped return type (`LiveMicrostructureInputs` from
`backend.app.risk.live_microstructure_provider`) is **not recovered**. The
composite holds four diagnostic numbers in
`OfflineCertificationQuoteFacts` — a passive, non-authoritative value object
that cannot evaluate risk or authorize execution.

## Validation

- `python3 -m py_compile` on changed Python files — PASS
- Phase 185A: 13 passed / 0 failed
- Phase 186A: 15 passed / 0 failed
- Phase 187A: 22 passed / 0 failed
- RC-LIVE-CONSOL-001 isolation: 11 passed / 0 failed
- MI-EXT + TAI-001 + TAI-002 + AOI + ranking: 84 passed / 0 failed
- `test_phase154a_broker_readiness_framework.py`: 3 passed / 0 failed
- Clean targeted total: **148 passed / 0 failed / 0 skipped**
- `git diff --check` — PASS
- Blocked by missing `dotenv` (live-environment dependency, not this change):
  `test_phase166a_canonical_broker_readiness.py` (collection ERROR);
  `test_oanda_live_firewall.py` (30 failed constructing `OandaAdapter`)

## Safety

- advisory_only=true, execution_allowed=false, live_network_ingestion=false
- AST firewall over `backend/app/market` rejects order/credential/gate imports
- ExecutionGate, AntiBleedGuard, UTG, live TTL/leases, OANDA live adapters untouched
