# CSS Evidence-Based Next Improvement Roadmap

Phase: PCA-001

Baseline: `584c6a28c38d792312c0edaf07533ca933d24266`

This roadmap ranks improvements by repository evidence, expected operational value, risk reduction, implementation effort, dependency readiness, and safety implications. It does not authorize implementation.

## Roadmap Classification

| Capability | Classification | Evidence | Gap |
| --- | --- | --- | --- |
| RC1 platform core | Complete pending certification | RC1 docs, runtime modules, dashboard/runtime tests | Needs current Desktop operational proof. |
| Options Income OI-002 through OI-010 | Complete paper-only | OI modules/tests/docs | Live broker integration and optional advanced strategies remain out of scope. |
| Options Income enterprise integration | Complete advisory/paper | EI-001/RC1-OI adapters, tests, docs | Continuous host consumption should be proven. |
| Mission Control MC-001 through MC-007C | Complete certified | Mission Control modules, host registration, final certification | Current Desktop operational validation remains separate. |
| Broker readiness/canonical state | Complete advisory-only | Phase 153-166 runtime modules/tests/docs | Current live read-only evidence and canonical reuse remain important. |
| Runtime/dashboard/mobile activation | Complete pending certification | Launcher/web/mobile code and tests | Current active host proof required. |
| Institutional portfolio optimization | Partial | Portfolio/intelligence engines | Production authority and canonical optimization scope not complete. |
| Treasury/cash-liquidity | Partial | Capital and portfolio pieces | No canonical treasury workflow. |
| FX forwards | Not started | No canonical implementation found | Requires product model, risk, broker/data, and accounting design. |
| FX swaps | Not started | No canonical implementation found | Requires treasury and derivatives foundation. |
| Cross-currency swaps | Not started | No canonical implementation found | Requires institutional derivatives foundation. |
| Interest-rate swaps | Not started | No canonical implementation found | Requires curve, valuation, collateral, and risk models. |
| Multi-currency hedging | Partial | Some portfolio/currency concepts | No complete hedging workflow. |
| Advanced derivatives | Partial | Options and shared derivatives services | Broader derivatives products incomplete. |
| Alternative data | Not started | No canonical integration found | Requires governance and data licensing controls. |
| Production deployment | Complete pending certification | Runbooks, launcher, release docs | Active runtime validation needed. |
| Live broker execution | Blocked | Execution safety gates | Intentionally disabled until separate approved live phase. |

## Top Improvement Candidates

| Rank | Initiative | Expected profitability impact | Risk reduction | Operational value | Capital efficiency | Effort | Integration complexity | Technical debt reduction | Dependency readiness | Time to production value | Safety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read-only Desktop operational proof and host activation certification | Medium | High | Very high | Medium | Medium | Medium | Medium | High | Short | Preserves advisory-only execution block. |
| 2 | Broker canonical state and read-only certification reconciliation | Medium | High | High | Medium | Medium | Medium | High | High | Short-medium | Preserves firewall and no-order rules. |
| 3 | Runtime/dashboard/Mission Control snapshot consolidation | Medium | Medium-high | High | Medium | Medium | Medium | High | High | Short-medium | Reduces operator ambiguity without trading. |
| 4 | Options Income active host proof and operational panels | Medium | Medium | High | Medium-high | Medium | Medium | Medium | High | Short | Paper/advisory only. |
| 5 | Portfolio/capital/risk/derivatives consolidation | Medium-high | Medium | Medium-high | High | Medium-high | High | High | Medium | Medium | Read-only/advisory if scoped correctly. |
| 6 | Treasury/cash-liquidity foundation design | Medium-high | Medium | Medium | High | High | High | Medium | Medium-low | Medium-long | Must remain read-only initially. |
| 7 | Alternative data governance and ingestion design | Medium | Medium | Medium | Medium | High | High | Low-medium | Low | Long | Requires data/vendor governance. |
| 8 | Advanced derivatives product foundation | High | Medium | Medium | High | High | High | Medium | Medium-low | Long | Should follow treasury and runtime proof. |

## Primary Recommendation

Perform a controlled read-only Desktop operational proof that verifies the actual host surfaces and canonical state flow in one runtime session.

Minimum scope:

- Start the canonical CSS host on Desktop without changing configuration.
- Verify dashboard, mobile launcher, and Mission Control use the same runtime snapshot.
- Verify broker certification state is consumed canonically.
- Verify account, broker, market-data, risk, capital, audit, and certification fields fail closed when unavailable.
- Verify Options Income paper/advisory panels are either host-active or explicitly marked adapter-only.
- Verify all safety flags remain:
  - `execution_allowed=false`
  - `live_trading_blocked=true`
  - `broker_execution_armed=false`
  - `advisory_only=true`

Rationale: The repository already has broad features. The highest marginal value is proving that the active operational surface is consistent, not creating another subsystem.

## Fallback Recommendation

If Desktop runtime validation is not immediately available, consolidate canonical runtime certification state in documentation and tests first.

Minimum scope:

- Define the canonical producer for broker readiness, runtime health, certification, freshness, and safety flags.
- Assert dashboard, mobile, Mission Control, and launcher consumers use the canonical producer.
- Add regression tests for drift prevention without changing live authority.

Rationale: This reduces the largest remaining risk: contradictory runtime/dashboard/broker readiness outputs.

## Deferred Recommendations

These initiatives should wait until the primary or fallback recommendation is complete:

- Treasury cash/liquidity management implementation.
- FX forwards, FX swaps, cross-currency swaps, and interest-rate swaps.
- Alternative data ingestion.
- Advanced options income strategies beyond covered calls and cash-secured puts.
- Any live execution pilot.

## Safety Criteria for Any Future Phase

Every future phase must explicitly state whether it is:

- Documentation-only.
- Read-only runtime validation.
- Paper-only simulation.
- Advisory-only intelligence.
- Certification-only.
- Live execution capable.

Any phase that changes live execution capability must preserve authoritative R7, RBAC, NO-GO, execution firewall, broker startup gates, credential diagnostics, live broker validation, and manual approval controls.
