# MI-EXT-001 R2 — External Events Recovery

Canonical base: `css-v1.0.1-maintenance` @ `e0676ce896b2eae682946e3619994d1dc0300da6`.

Historical reference only: RC-LIVE commit `3c7a6b61`. Not merged. Not cherry-picked wholesale.

## Recovered capability

Fixture/offline external-event pipeline with provenance, freshness/TTL, dedup,
classification, advisory impact, and a TAI/ranking diagnostic overlay.

Every output is `advisory_only=true`, `execution_allowed=false`,
`direct_execution_influence=false`, `live_network_ingestion=false`.

## Not recovered

RC-LIVE live-authority leases, AntiBleed policy/ExecutionGate wiring, OANDA
controlled network certification, FX capital governor, qualification/registry
claims, and DIP/Trade DNA decision-integration as an execution path.

## Integration seam

`AutonomousOpportunityIntelligenceEngine.analyze()` attaches
`external_event_intelligence` beside TAI. Ranking copies the overlay for
diagnostics and does not add event scores into `ranking_v2.weighted_score`.
Mission Control `opportunity_ranking` exposes the overlay as read-only
observability. Unified Trade Gate remains the execution authority.

## Validation (this environment)

- compile: PASS
- MI-EXT 47 passed / 0 failed
- TAI/AOI/ranking 37 passed / 0 failed
- regime/orchestrator/MC/UTG/weighting 47 passed / 0 failed / 1 warning
- targeted total 131 passed / 0 failed / 0 skipped / 1 warning
- `git diff --check`: PASS
