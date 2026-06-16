# AI Governance Phase 6: Unified Governance Coordinator

## Purpose
The Unified Governance Coordinator is the core aggregation engine of the CSS AI Governance Layer. It ingests the outputs from all four underlying governance agents (Auditor, Certifier, Intelligence, Commander) and deterministically consolidates their findings into a single readiness assessment.

## Authority Boundaries
The Unified Governance Coordinator is strictly **read-only**:
- It cannot execute trades.
- It cannot interact with broker adapters.
- It cannot alter live execution configurations.
- It cannot write to the file system.
- It cannot override the findings of underlying agents.

## Participating Agents
The Coordinator expects strongly typed dataclass outputs from:
1. `GovernanceAuditorAgent` (`AuditSummary`)
2. `CertificationAgent` (`CertificationSummary`)
3. `RepositoryIntelligenceAgent` (`RoadmapSummary`)
4. `OperationsCommanderAgent` (`OperationsResult`)

## Aggregation & Scoring Model
The Coordinator starts with a default readiness score of `100`.
- **Low/Info findings**: -5 points
- **Medium/Warning findings**: -10 points
- **High/Error findings**: -25 points
- **Critical/P0/Fail-Closed findings**: Immediately drops score to 0 and forces the `governance_status` to `FAIL_CLOSED`.

If the score is > 0 but contains High findings, the status is `NOT_READY`.
If no Critical or High findings exist, the status is `READY`.

## Fail-Closed Behavior
If any of the four agent payloads are missing or of an invalid type, the Coordinator immediately defaults to `FAIL_CLOSED` and a score of `0`. Furthermore, if any individual agent reported a `FAIL_CLOSED` state, the Coordinator honors it and escalates the entire system state to `FAIL_CLOSED`.

## Test Evidence
The Coordinator is backed by an explicit test suite (`tests/test_unified_governance_coordinator.py`) proving:
- Valid inputs with no findings produce `READY` with a score of 100.
- Missing or invalid types trigger `FAIL_CLOSED`.
- High severity findings deduct 25 points and result in `NOT_READY`.
- Critical severity findings force a `FAIL_CLOSED` state and 0 score.
- The coordinator has zero execution or broker side-effects (validated by structural inspection).

## Future Integration Roadmap
In future phases, the Unified Governance Coordinator will expose its single `UnifiedGovernanceReport` payload to a dashboard or a CI/CD boundary, acting as the ultimate read-only truth layer for CSS readiness.
