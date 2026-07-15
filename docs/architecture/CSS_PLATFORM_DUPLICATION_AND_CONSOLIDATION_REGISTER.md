# CSS Platform Duplication and Consolidation Register

Phase: PCA-001

Baseline: `584c6a28c38d792312c0edaf07533ca933d24266`

This register identifies duplicate or overlapping implementations that may cause state drift. PCA-001 did not remove or modify production code.

| Area | Modules involved | Canonical candidate | Legacy or overlapping implementation | Risk of divergence | Recommended consolidation | Urgency | Migration complexity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Broker readiness and certification | `backend/runtime/live_connectivity_certifier.py`, `live_broker_validation.py`, `broker_readiness_framework.py`, `broker_operational_status.py`, `canonical_broker_runtime_state.py`, `canonical_broker_state_*` | Canonical broker runtime state plus Live Connectivity Certifier output | Secondary health/readiness builders and dashboard-specific summaries | High | Require dashboards/runtime/API to consume canonical certification state and expose provenance. | P1 | Medium |
| Broker market-data evidence | `broker_market_data_evidence.py`, Coinbase/OANDA read-only validation modules, adapter quote methods | Broker market-data evidence module or certifier evidence section | Broker-specific validation payload mapping | Medium | Standardize quote evidence fields by broker and symbol. | P1 | Medium |
| Account/balance/margin snapshots | `canonical_account_snapshot.py`, margin adapters, broker readiness payloads, dashboard margin API | Canonical account snapshot with provenance | Margin-specific dashboard calls and broker-specific summaries | High | Use canonical snapshot for balance, buying power, margin, and account freshness. | P1 | Medium |
| Portfolio construction | `backend/portfolio/*`, `backend/analytics/autonomous_portfolio_manager.py`, OI portfolio modules | Domain-specific portfolio state contracts with enterprise adapter boundaries | Parallel allocation/intelligence engines | Medium | Define canonical read models and isolate specialized engines as advisory contributors. | P2 | High |
| Capital allocation | `backend/allocation/*`, `backend/portfolio/capital_rotation_engine.py`, OI allocator/constraints, live pilot governor | Typed capital policy/configuration model and runtime capital snapshot | Strategy-specific allocation calculations | Medium | Centralize limits and publish derived advisory allocations. | P1 | Medium |
| Risk budgeting and limits | `backend/risk/*`, `engine/risk/*`, OI risk budget/limits, Mission Control projections | Existing authoritative risk gates for execution; OI risk for paper-only | Dashboard and OI risk summaries | Medium | Keep execution risk gates separate from advisory risk projections with explicit scope. | P1 | Medium |
| Greeks aggregation | `backend/trading/greeks_engine.py`, `backend/options/options_greeks_aggregator.py`, dashboard Greeks helpers | Shared derivatives/Greeks contract for read models | Dashboard-specific aggregation and OI-specific aggregators | Medium | Reuse shared derivatives services for portfolio-level views. | P2 | Medium |
| Stress testing | Core risk stress modules, OI stress testing, derivatives stress service | Shared derivatives stress service for derivatives; core risk stress for whole portfolio | OI-specific stress report builders | Medium | Preserve domain calculations but normalize outputs through shared service. | P2 | Medium |
| Dashboard payloads | `dashboard/runtime/frontend_contract.py`, OI dashboard payloads, Mission Control serializers, mobile payloads | Runtime frontend contract plus Mission Control state contract | Feature-specific payload builders with overlapping status fields | Medium | Define payload ownership and field aliases. | P1 | Medium |
| Alerts | Monitoring alert repository, OI alerts, Mission Control alert projections | Monitoring alert repository for operational alerts; OI alerts as advisory source | Feature-local alert builders | Medium | Use alert adapter pattern with canonical severity/status. | P2 | Low-medium |
| Explainability | Portfolio explainability, OI explainability, Mission Control explanation projection | Canonical evidence/audit explanation contract | Separate narrative payloads | Medium | Normalize explanations to source, inputs, rules, outputs, and confidence. | P2 | Medium |
| Certification | Runtime certifier, broker certifiers, OI certification, Mission Control final certification, RC1 docs | Scope-specific certificates with canonical runtime certification index | Independent phase certificates | Medium | Publish a certification registry with scope, timestamp, commit, and safety flags. | P1 | Medium |
| Replay validation | OI replay validator, runtime validation/replay artifacts | Runtime validation for platform; OI replay for OI paper certification | Per-subsystem replay logic | Low-medium | Keep domain replay tests but share hash/provenance helpers. | P3 | Low |
| Audit reporting | OI audit adapter/report, app audit journal, event bus, runtime evidence hashing | Enterprise audit/event contract | Subsystem-specific audit records | Medium | Normalize record schema and attach subsystem scope. | P2 | Medium |
| Runtime snapshot generation | Runtime artifact publisher, certification snapshot, Mission Control normalizer, dashboard hydration | Runtime certification snapshot as authoritative source for readiness | Dashboard-specific and Mission Control-specific derived snapshots | High | Generate once per cycle and have consumers render it. | P1 | Medium |
| Freshness logic | Runtime artifact freshness, Mission Control freshness, broker market-data freshness | Runtime freshness service with consumer-specific display adapters | Per-surface freshness calculation | Medium | Share freshness thresholds and source-provenance fields. | P1 | Low-medium |
| State hashing | Mission Control hash, runtime hash/evidence hashing, OI replay hash | Runtime state hash plus evidence hash library | Feature-local hash generation | Medium | Include hash type, source scope, and inputs in every hash payload. | P2 | Medium |
| Feature flags | Governance/feature flag modules, Mission Control feature flag console, runtime configs | Existing governance feature flag authority | Dashboard visibility models | Medium | Keep Mission Control read-only and document authority source. | P2 | Low |
| Configuration models | Runtime environment loader, live/paper config, broker credentials, order limits | Typed configuration models with explicit mode precedence | Environment variables and compatibility aliases | High | Continue mode-specific loading tests and forbid live import of test-only variables. | P1 | Medium |

## Consolidation Principles

1. Do not remove legacy code until a canonical producer and all consumers are proven.
2. Preserve execution firewall, R7, RBAC, NO-GO, and broker startup gates as authoritative.
3. Treat advisory and paper models as contributors, not execution authorities.
4. Prefer a single runtime-cycle snapshot over dashboard-triggered recomputation.
5. Carry provenance, scope, timestamp, source, and safety flags in every normalized payload.

## Priority Consolidation Backlog

| Priority | Recommendation | Reason |
| --- | --- | --- |
| P1 | Canonical broker certification state reuse | Prevents broker health/readiness contradictions. |
| P1 | Canonical runtime snapshot consumed by dashboard, mobile, and Mission Control | Prevents UI state divergence. |
| P1 | Account/balance/margin provenance consolidation | Prevents authenticated/account/balance inconsistencies. |
| P1 | Configuration and environment loading precedence documentation/tests | Prevents live/practice contamination. |
| P2 | Portfolio/capital/risk projection ownership | Reduces duplicate financial state calculations. |
| P2 | Audit/evidence/explainability schema normalization | Improves institutional traceability. |
| P2 | Options Income active host proof | Separates implementation completion from operational availability. |

## Non-Actions in PCA-001

PCA-001 did not delete code, redirect imports, change runtime behavior, clean artifacts, alter credentials, modify limits, or change execution authority.
