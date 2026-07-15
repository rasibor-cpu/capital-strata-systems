# CSS Technical Debt Register

Phase: PCA-002

Audit date: 2026-07-15

Baseline: `0320e56c2a6b79679a9c9e34aff825e44cf03c47`

Scope: documentation-only debt register. PCA-002 did not remove code, redirect imports, change configuration, or modify runtime behavior.

## Debt Severity

| Severity | Meaning |
| --- | --- |
| P0 | Release blocker or safety contradiction. None confirmed by PCA-002. |
| P1 | High-value consolidation or operational proof needed to prevent operator ambiguity. |
| P2 | Important maintainability or scope clarity work. |
| P3 | Deferred cleanup or future roadmap hygiene. |

## Register

| ID | Severity | Area | Finding | Evidence | Risk | Recommended action | Safety constraint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PCA2-TD-001 | P1 | Runtime state | Multiple runtime snapshot/readiness producers can diverge. | `backend/runtime/runtime_certification_snapshot.py`, dashboard runtime contract, Mission Control normalizer, launcher builder | Dashboard, mobile, and Mission Control may display different state for one cycle. | Generate one canonical runtime-cycle snapshot and render it through adapters. | No execution authority changes. |
| PCA2-TD-002 | P1 | Broker readiness | Broker health/readiness/certification appears in several modules. | Live validation, connectivity certifier, continuous monitor, canonical broker state, dashboard summaries | Broker health can appear green in one surface and unavailable in another. | Treat canonical broker runtime state and scoped certificates as display authorities. | Keep `execution_allowed=false`. |
| PCA2-TD-003 | P1 | Broker environment loading | BR-001 introduced canonical profiles, but legacy/direct env reads may still exist. | `broker_environment_profiles.py`, credential loader, bootstrap, adapter diagnostics | Future code could reintroduce live/practice contamination. | Route broker consumers through profile-aware credential objects. | Do not modify credentials or `.env` files in consolidation. |
| PCA2-TD-004 | P1 | Account/balance/margin provenance | Balance, buying power, margin, and account status are represented through multiple snapshots. | Canonical broker state, margin adapters, dashboard account views | Authenticated/account/balance contradictions can confuse operators. | Publish one account snapshot with source, freshness, and failure stage. | Read-only account queries only. |
| PCA2-TD-005 | P1 | Active host proof | Repository tests prove contracts, but active Desktop listener proof is not current. | OP-001 operational proof notes no active listener was observable | Production readiness claims can overstate runtime availability. | Re-run controlled Desktop operational proof with host already running. | Do not stop/restart server unless explicitly authorized. |
| PCA2-TD-006 | P1 | Dashboard payload ownership | Dashboard, launcher, Mission Control, and OI payloads repeat status and safety fields. | `dashboard/runtime/frontend_contract.py`, `launcher/css_mobile_launcher.py`, Mission Control serializers, OI dashboard builders | Field drift across UI surfaces. | Define field ownership and adapter aliases. | Safety flags must remain hard-fail false/true as applicable. |
| PCA2-TD-007 | P1 | Certification scope | RC1, runtime, broker, OI, MC, and operational certificates have separate scopes. | `backend/certification/*`, `backend/runtime/*certification*`, OI certification, MC final certification | A certificate can be mistaken for broader readiness than it covers. | Add certification registry/index fields: scope, source, baseline, timestamp, safety posture. | Certification never authorizes trading. |
| PCA2-TD-008 | P2 | Portfolio read models | Portfolio, analytics, allocation, OI, and MC projections overlap. | `backend/portfolio/*`, `backend/analytics/*`, `backend/allocation/*`, OI portfolio modules | Different views can report different exposure or attribution. | Establish canonical portfolio display contract with contributor scopes. | Advisory/read-only only. |
| PCA2-TD-009 | P2 | Risk summaries | Core risk, app risk, OI risk, derivatives risk, and MC projections overlap. | `backend/risk/*`, `backend/app/risk/*`, `backend/options/options_income_risk_*`, `backend/derivatives/*` | Advisory risk displays can be confused with execution gate authority. | Preserve execution-gate ownership and label advisory projections. | Authoritative gates stay unchanged. |
| PCA2-TD-010 | P2 | Capital allocation | Multiple allocation/optimizer modules produce advisory capital outputs. | `backend/allocation/*`, `backend/analytics/capital_*`, `backend/portfolio/*`, OI allocator | Conflicting allocations can appear as actionable capital movement. | Normalize advisory capital recommendation schema. | No automatic capital movement. |
| PCA2-TD-011 | P2 | Audit/event schemas | Runtime, dashboard, OI, MC, and event bus records use related but separate schemas. | `backend/events/*`, dashboard evidence hashing, OI audit/event adapters, MC evidence graph | Institutional audit trace can be harder to reconcile. | Standardize audit event envelope and evidence hash metadata. | No mutation of runtime logs in audit-only phases. |
| PCA2-TD-012 | P2 | Freshness calculations | Freshness exists in runtime artifacts, broker market data, MC, and dashboard heartbeat. | Mission Control freshness, runtime artifact reader, broker market-data evidence | Surfaces may disagree on stale/fresh status. | Share thresholds and expose per-source freshness. | Fail closed when stale. |
| PCA2-TD-013 | P2 | Learning/advisory scoring | Learning, analytics, portfolio, and strategy modules each emit confidence-like outputs. | `backend/learning/*`, `backend/analytics/*`, `backend/portfolio/*` | Recommendation priority can drift by surface. | Standardize advisory recommendation metadata and source weighting. | No execution decisions changed automatically. |
| PCA2-TD-014 | P2 | Options Income host proof | OI is complete for paper scope but active host consumption of every panel remains unproven. | OI adapters, RC1-OI docs, Mission Control OI page | Operators may assume host-active status from adapter evidence. | Validate OI panels in active Desktop runtime. | Paper/advisory only. |
| PCA2-TD-015 | P2 | Mobile smoke drift | OP-001 recorded standalone mobile smoke display-string mismatch. | `docs/operations/CSS_CONTROLLED_OPERATIONAL_PROOF.md` | Smoke result can obscure otherwise passing mobile focused tests. | Align smoke contract with current rendered status labels. | Display-only remediation. |
| PCA2-TD-016 | P2 | Deployment command clarity | Multiple launch/test commands exist across docs and scripts. | Runbooks, launcher, dashboard web app docs | Operators can start a module that exits instead of hosting. | Keep canonical host command and port documented in one operator runbook. | Startup docs only unless approved. |
| PCA2-TD-017 | P3 | Treasury | Treasury/cash/liquidity workflow is partial. | Capital and portfolio modules, roadmap docs | Future work could duplicate capital controls. | Design treasury read model after runtime proof. | Read-only initial scope. |
| PCA2-TD-018 | P3 | Advanced derivatives | Options and shared derivatives exist, but broader derivatives products are partial. | `backend/options/*`, `backend/derivatives/*` | Product expansion before core proof adds complexity. | Defer swaps/advanced derivatives until platform state is canonical. | No live routing. |
| PCA2-TD-019 | P3 | Alternative data | No canonical integration found. | Roadmap evidence only | Vendor/data governance risk. | Create governance-first design before ingestion. | No data-license assumptions. |
| PCA2-TD-020 | P3 | Legacy docs | Some phase docs predate BR-001 and current MC integration. | Older governance/release docs | Readers may miss current profile separation. | Prefer PCA-002 and BR-001 docs for current broker profile posture. | Do not rewrite history without need. |

## Near-Term Debt Burn-Down Order

1. Active Desktop operational proof with one canonical runtime snapshot.
2. Broker readiness/certification display consolidation.
3. Account/balance/margin provenance consolidation.
4. Dashboard/mobile/Mission Control payload ownership.
5. Options Income active host proof.

## Non-Actions

This register does not authorize implementation. It does not increase limits, enable live trading, modify broker credentials, change profile files, or alter execution gates.
