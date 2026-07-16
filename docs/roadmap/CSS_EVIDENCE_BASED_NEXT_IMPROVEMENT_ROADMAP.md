# CSS Evidence Based Next Improvement Roadmap

Phase: PCA-001

Baseline SHA: 502fb70587b0597873a7a2531589cc6d75261220

## Roadmap Gap Classification

| Item | Classification | Evidence-Based Reason |
|---|---|---|
| Options Income canonical scope | complete | OI-002 through OI-010 modules and tests are present and passing |
| Options Income enterprise host activation | partial | RC1-OI integration exists, but host runtime activation evidence is limited |
| Institutional portfolio optimization | partial | Phase157C exists with tests, but broad production host activation/certification is limited |
| FX forwards | not started | No authoritative implementation evidence found |
| FX swaps | not started | No authoritative implementation evidence found |
| Cross-currency swaps | not started | No authoritative implementation evidence found |
| Interest-rate swaps | not started | No authoritative implementation evidence found |
| Multi-currency hedging | partial | FX and capital/risk building blocks exist, but no complete hedging subsystem evidence |
| Cash and liquidity management | partial | Treasury/liquidity modules exist, but maturity and activation are limited |
| Advanced derivatives strategies | deferred | Core options/derivatives services exist, advanced spread families are not in canonical delivered scope |
| Statistical arbitrage | partial | Analytics/intelligence infrastructure exists, but no certified platform-level stat-arb subsystem |
| Cross-asset strategies | partial | Cross-asset and committee surfaces exist, but not fully production-activated |
| Macro regime strategies | partial | Regime intelligence is mature, but strategy activation remains advisory-first |
| Alternative data | partial | Intelligence infrastructure exists; direct alternative-data platform evidence is limited |
| Production deployment | partial | Controlled release and desktop operational proof exist, not unrestricted production rollout |
| Live broker execution | blocked | Policy and code intentionally keep execution disabled |
| Secure broker onboarding | partial | Credential/profile governance exists, but operator onboarding is not fully institutionalized |
| Institutional reporting | partial | Reporting framework is broad, but consolidated institutional reporting program remains incomplete |
| Mobile operations | partial | Mobile host is active and certified in controlled scope, but large-host complexity and production breadth remain |

## Ranked Improvement Candidates

| Rank | Initiative | Profitability Impact | Risk Reduction | Operational Value | Capital Efficiency | Effort | Integration Complexity | Debt Reduction | Dependency Readiness | Time To Value | Safety Implication |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Canonical host activation for Options Income | 8 | 7 | 9 | 8 | 5 | 6 | 7 | 9 | 8 | Safe if existing paper-only guards preserved |
| 2 | Broker/canonical state consolidation | 5 | 9 | 8 | 6 | 6 | 6 | 9 | 9 | 7 | Improves safety and reduces drift |
| 3 | Runtime artifact ownership and freshness hardening | 4 | 8 | 8 | 5 | 5 | 5 | 8 | 8 | 8 | Strongly safety-positive |
| 4 | Deployment and endurance evidence automation | 3 | 7 | 8 | 4 | 4 | 4 | 6 | 8 | 8 | Safety-positive |
| 5 | Treasury/liquidity institutional completion | 7 | 6 | 6 | 8 | 8 | 7 | 5 | 4 | 4 | Neutral if kept advisory |

## Primary Recommendation

Canonical host activation for Options Income.

Reason:

- It has the highest marginal value because the engine is already paper-only complete, enterprise integrated, and certified at subsystem level.
- The largest remaining gap is not algorithmic capability but platform activation and visibility through canonical runtime and host surfaces.
- This delivers immediate operational value without weakening existing safety constraints.

## Fallback Recommendation

Broker and canonical-state consolidation.

Reason:

- It reduces the largest architectural divergence risk.
- It improves reliability of Mission Control, dashboard, readiness, and certification outputs simultaneously.
- It lowers the cost and risk of all later production-hardening work.

## Explicit Non-Recommendations

1. Do not prioritize live execution enablement; current dependencies and policy posture are not ready.
2. Do not prioritize advanced treasury derivatives before host/state consolidation and Options Income activation are complete.
3. Do not treat IBKR placeholder support as production expansion readiness.
