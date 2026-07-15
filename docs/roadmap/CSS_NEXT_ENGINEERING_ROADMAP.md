# CSS Next Engineering Roadmap

Phase: PCA-002

Audit date: 2026-07-15

Baseline: `0320e56c2a6b79679a9c9e34aff825e44cf03c47`

This roadmap ranks next initiatives by profitability potential, operational value, risk reduction, implementation effort, dependency readiness, and safety posture. It is advisory and does not authorize implementation.

## Ranking Criteria

| Criterion | Meaning |
| --- | --- |
| Profitability potential | Expected contribution to future alpha, income, capital efficiency, or pilot readiness. |
| Operational value | Improvement to operator clarity, runtime consistency, supportability, or release confidence. |
| Risk reduction | Reduction in safety, broker, runtime, audit, or state-drift risk. |
| Effort | Relative engineering effort. Lower is better. |
| Dependency readiness | Whether the required platform foundations already exist. |
| Safety | Ability to preserve advisory-only, paper-only, or read-only posture. |

## Top Five Recommended Initiatives

| Rank | Initiative | Profitability potential | Operational value | Risk reduction | Effort | Dependency readiness | Safety posture | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Controlled active Desktop operational proof after BR-001 | Medium | Very high | Very high | Medium | High | Read-only | Proves the existing platform works as one runtime system before adding more capabilities. |
| 2 | Canonical runtime snapshot consolidation | Medium | High | High | Medium | High | Read-only | Prevents dashboard, mobile, launcher, Mission Control, broker, risk, and certification views from drifting. |
| 3 | Broker readiness and account/balance provenance consolidation | Medium | High | Very high | Medium | High | Read-only | Uses BR-001 profile separation and canonical broker state to eliminate ambiguous broker health/account states. |
| 4 | Options Income active host and operational panel proof | Medium-high | High | Medium | Medium | High | Paper/advisory only | Converts completed OI adapter evidence into active operator visibility proof without live execution. |
| 5 | Portfolio, capital, risk, and accounting read-model consolidation | Medium-high | Medium-high | High | Medium-high | Medium | Advisory/read-only | Improves capital/risk clarity and reduces conflicting financial displays before pilot planning. |

## Primary Recommendation

Execute the controlled active Desktop operational proof first.

Minimum scope:

- Start the canonical CSS Desktop host through the documented launcher path.
- Confirm the active listener and health endpoint.
- Verify dashboard, mobile, launcher, and Mission Control consume one canonical runtime snapshot.
- Verify BR-001 broker environment profile metadata is present and redacted.
- Verify broker readiness, account, balance, market-data, risk, capital, audit, certification, and Options Income views agree on source and freshness.
- Verify all safety fields remain:
  - `execution_allowed=false`
  - `live_trading_blocked=true`
  - `broker_execution_armed=false`
  - `advisory_only=true`

This recommendation has the highest operational value because the repository already contains broad feature work. The next bottleneck is proving active runtime consistency, not adding another subsystem.

## Secondary Recommendation

If an active Desktop session is not immediately available, perform canonical snapshot consolidation in tests and documentation first:

- Define the canonical producer for runtime health, broker readiness, certification, freshness, safety, account, and balance fields.
- Assert dashboard, mobile, launcher, and Mission Control consumers render that producer without recomputing incompatible health.
- Add drift-prevention tests for safety flags and source provenance.

## Deferred Initiatives

The following should wait until active runtime and canonical-state proof are complete:

- Live pilot planning beyond read-only readiness.
- Treasury/cash-liquidity workflow implementation.
- FX forwards, FX swaps, cross-currency swaps, and interest-rate swaps.
- Advanced derivatives product expansion beyond existing Options Income scope.
- Alternative data ingestion.
- New strategy engines or automated optimization authority.

## Safety Requirements for Future Phases

Every future phase should declare one of these scopes:

- Documentation-only.
- Evidence-only audit.
- Read-only validation.
- Paper-only simulation.
- Advisory-only intelligence.
- Certification-only.
- Live execution capable.

Any live-execution-capable phase must be separately approved and must preserve authoritative R7, RBAC, NO-GO, execution firewall, broker startup gates, broker environment profiles, credential diagnostics, manual approval controls, and audit requirements.

## Roadmap Outcome

CSS should continue toward production readiness through proof and consolidation before capability expansion. The platform is strong enough that the best next work is making current state undeniable, consistent, and operator-visible.
