# CSS Consolidation Decision Report

Date: 2026-07-14

Working branch: `css-unified-consolidation-2026-07-13`

Reviewed HEAD: `492c95c2c5d0a973e5b767dc768806202c8eab3e`

Source branch reviewed: `phase1-persistence-foundation`

Scope: final read-only architectural decision review. This report does not
modify source code, reconstruct modules, merge branches, cherry-pick commits,
activate persistence, wire replay logic, change brokers, change execution
logic, update Desktop, restart CSS, deploy CSS, or change live-trading behavior.

## Decision Summary

The consolidation branch has recovered the highest-value historical work:

- deterministic evidence hashing;
- append-only persistent execution journal;
- canonical runtime event normalization;
- runtime event retention, export, replay, archive, and evidence governance;
- final consolidation roadmap and candidate triage.

Remaining historical salvage is no longer a prerequisite for consolidation
safety. The remaining useful historical material is mostly optional evidence
helper/checklist tooling. It can support future certification packaging, but it
does not close the larger product gaps identified by repository evidence:
options income strategies, assignment/rolling/Wheel, live options/futures broker
integration, futures broker-live reconciliation, and final production
certification.

## Repository-Wide Value Assessment

Recommendations use only:

- `COMPLETE`
- `COMPLETE_STOP`
- `SALVAGE_ONE_UNIT`
- `SALVAGE_FEW_UNITS`
- `NO_FURTHER_SALVAGE`

| Subsystem | Current status | Remaining historical work | Estimated engineering value | Estimated regression risk | Additional salvage justified | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Runtime | `COMPLETE_PENDING_CERTIFICATION` | Event-bus shadow routing, operator persistence simulation surfaces, old dashboard separation commits. | Low | High | `NO_FURTHER_SALVAGE` | `docs/governance/CSS_FINAL_CONSOLIDATION_ROADMAP.md` lists runtime as complete pending certification; rejects `bb00c5c` shadow routing because it changes runtime delivery behavior. |
| Authentication | `COMPLETE_PENDING_CERTIFICATION` | Historical dashboard auth stores and live credential attestation surfaces. | Low to medium | Medium to high | `NO_FURTHER_SALVAGE` | Current repo has `backend/app/auth/*`, `backend/security/user_auth.py`, `dashboard/auth/css_sign_on.py`, and tests listed in the roadmap. Credential/auth changes require dedicated certification, not historical salvage. |
| Dashboard | `COMPLETE_PENDING_CERTIFICATION` | Micro-live readiness/checklist dashboard surfaces and old API/web wiring. | Medium | Medium to high | `NO_FURTHER_SALVAGE` | Roadmap identifies read-only dashboard routes and tests, while rejecting historical API/web wiring without separate approval. |
| Brokers | `PARTIAL` | IBKR scaffold, Coinbase live mode fixes, multi-broker live execution routing. | Low for consolidation; high risk if revived. | Critical | `NO_FURTHER_SALVAGE` | Roadmap marks brokers partial and permanently rejects `e596a96`; broker readiness tests and read-only validation already exist. |
| Options | `PARTIAL` | Historical dry-run options foundation. | Low | High | `COMPLETE_STOP` | Options matrix says current options execution is dry-run only and historical options foundation is superseded; missing work is new product roadmap work, not salvage. |
| Futures | `PARTIAL` | Historical dry-run futures foundation. | Low | High | `COMPLETE_STOP` | Futures matrix says current futures execution is dry-run/live-disabled; historical futures commits are superseded by current implementation. |
| Portfolio | `COMPLETE_PENDING_CERTIFICATION` | Older portfolio governance/risk foundation commits. | Low | Medium | `NO_FURTHER_SALVAGE` | Current portfolio modules/tests are extensive per roadmap; historical portfolio governance is superseded. |
| Analytics | `COMPLETE_PENDING_CERTIFICATION` | Broad institutional intelligence/orchestrator merge commits. | Low | Critical | `NO_FURTHER_SALVAGE` | Roadmap rejects broad orchestrator/intelligence merge commits as obsolete and high regression risk. |
| Risk | `COMPLETE_PENDING_CERTIFICATION` | Historical unified risk gate, portfolio governor, capital allocation governor. | Low | Medium to high | `COMPLETE_STOP` | Current `backend/app/risk/*`, `backend/risk/*`, and trade-gate tests exist; historical risk commits are superseded. |
| Governance | `COMPLETE_PENDING_CERTIFICATION` | Micro-live operations docs and companion roadmap docs. | Low | Low | `COMPLETE_STOP` | Salvage plan and roadmap identify these governance docs as already present. |
| Persistence | `PARTIAL` | Core SQLite persistence and runtime lifecycle hooks. | Low | Medium to high | `COMPLETE_STOP` | SQLite DB, migrations, repositories, services, and journal are present; runtime event persistence is intentionally disabled/governance-only. |
| Evidence | `PARTIAL` | Evidence verification, signature readiness, notarization readiness, post-pilot archive helper modules. | Medium | Low to medium | `SALVAGE_ONE_UNIT` | Roadmap says evidence hash foundation exists while verification/signature/notarization helpers are absent. Only one evidence-readiness unit has enough value to consider later. |
| Replay | `OBSERVER_ONLY` | Lifecycle replay viewer/table and replay UI consistency commits. | Low | Medium to high | `NO_FURTHER_SALVAGE` | Current replay is read-only/observer-only; roadmap says further replay wiring is not approved. |
| Reporting | `COMPLETE_PENDING_CERTIFICATION` | Post-pilot export/report packages. | Medium | Medium | `NO_FURTHER_SALVAGE` | Current reporting framework exists; post-pilot packages are optional evidence packaging, not reporting core. |
| Certification | `COMPLETE_PENDING_CERTIFICATION` | Evidence verification and micro-live checklist helpers. | Medium | Low to medium | `SALVAGE_ONE_UNIT` | Certification engines exist; optional evidence verification helper could improve package review, but production certification can proceed without more historical recovery. |

## Remaining Candidate Ranking

Actions use exactly:

- `IMPLEMENT`
- `IMPLEMENT_IF_TIME`
- `ARCHIVE_ONLY`
- `REJECT`

| Rank | Commit(s) | Functionality | Engineering value | Architectural cleanliness | Maintenance value | Regression risk | Estimated implementation effort | Recommended action |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `51a3735`, `51389af`, `f3d4b94` | Evidence verification readiness, manual verification checklist, checklist print/export surface. | Medium | High if reconstructed as helper/test/governance only. | Medium | Low to medium | Medium | `IMPLEMENT_IF_TIME` |
| 2 | `2aef8f6`, `86d5495`, `37876df` | Post-pilot reconciliation evidence workflow, evidence archive export package, archive manifest hashing. | Medium | Medium if kept read-only and local. | Medium | Medium | Medium | `IMPLEMENT_IF_TIME` |
| 3 | `38acdad`, `05e2072`, `e1407d7` | Signed evidence packet readiness and notarization readiness metadata. | Low to medium | Medium; risk of implying cryptographic/legal capability if overclaimed. | Medium | Medium | Medium | `ARCHIVE_ONLY` |
| 4 | `a64f2d9`, `ce17be2`, `8b0b20a`, `d71ed7c`, `39135c5`, `7d6c5ba`, `760de5a` | Micro-live evidence package and non-executing readiness/checklist artifacts. | Low to medium | Medium; overlaps current live-readiness/certification framework. | Low | Medium to high | Medium to high | `ARCHIVE_ONLY` |
| 5 | `bf4577a` | Phase 54 pilot safety controls regression test. | Low | Medium; current APIs may differ. | Low | Low | Low to medium | `ARCHIVE_ONLY` |
| 6 | `72864d3` through `8515942` | Core SQLite persistence and repositories. | Low | Low; duplicated. | Low | Low | Low | `ARCHIVE_ONLY` |
| 7 | `8f71b21`, `6789459`, `97ebffb` | Options/futures dry-run foundations. | Low | Low; superseded. | Low | High | Medium | `ARCHIVE_ONLY` |
| 8 | `e6ab6cd`, `a0ac8da`, `51535bf`, `0a9c86a`, `8b87b7c`, `08e6823` | Broker bootstrap/live-mode/readiness changes. | Low for consolidation. | Low; current broker authority is newer. | Low | High | High | `REJECT` |
| 9 | `e596a96` | Institutional multi-broker live execution routing. | Negative for this consolidation. | Low; conflicts with current authority controls. | Negative | Critical | High | `REJECT` |
| 10 | `bb00c5c`, `01a9d73`, `58ae6a8`, `bbdc520`, `caf254f`, `7f262fb`, `0fae9de` | Runtime producer shadow routing, persistence-aware orchestration, broad merges/orchestrator rewrites. | Negative for this consolidation. | Low; obsolete and too broad. | Negative | Critical | High | `REJECT` |

## Opportunity Cost Analysis

### 1. If historical salvage stops today, what capabilities are actually missing?

The missing capabilities are not primarily historical-recovery capabilities.
They are product roadmap or certification capabilities:

- Options income completion: covered calls and cash-secured puts are placeholders,
  Wheel is not present, assignment is not present, and options rolling is not an
  options lifecycle implementation. Evidence: `docs/architecture/CSS_OPTIONS_COMPLETION_MATRIX.md`.
- Options live broker integration and real options order placement are not
  implemented. Evidence: options matrix says dry-run only and broker integration
  placeholder.
- Futures live execution, broker-live margin/reconciliation, fill ingestion,
  dedicated futures execution controls, and full broker-statement PnL
  reconciliation remain incomplete. Evidence:
  `docs/architecture/CSS_FUTURES_COMPLETION_MATRIX.md`.
- Final production certification after consolidation remains incomplete.
  Evidence: `docs/governance/CSS_FINAL_CONSOLIDATION_ROADMAP.md` classifies
  certification as complete pending certification.
- Optional evidence package helpers are absent: verification readiness,
  signature/notarization readiness, and post-pilot archive helper modules.
  Evidence: roadmap evidence subsystem classification.

### 2. Are any missing capabilities required for production certification, broker safety, governance, audit, options, futures, or portfolio management?

Production certification:

- Required: broad finite regression, final certification evidence, final diff
  review, and certification package generation.
- Not strictly required: more historical salvage. The branch already contains
  evidence hashing, persistent journal, runtime event normalization, governance
  policy, and certification engines.

Broker safety:

- Required: preserve broker-state authority, read-only validation, credential
  hygiene, fail-closed live controls, and broker regression tests.
- Not required: historical live-routing or live-mode salvage. Those are rejected
  because they increase risk.

Governance and audit:

- Required: current governance docs, audit/journal/evidence hash surfaces, and
  final certification evidence.
- Optional: evidence verification helper/checklist modules may improve review
  ergonomics, but governance can proceed without them.

Options:

- Required for the options roadmap: covered calls, cash-secured puts, Wheel,
  assignment, rolling, and live broker integration if those are still business
  goals.
- Not required from historical salvage: the historical options foundation is
  already superseded.

Futures:

- Required for futures roadmap: live broker adapter, broker-live
  margin/reconciliation, fill ingestion, and full PnL reconciliation.
- Not required from historical salvage: the historical dry-run futures foundation
  is already superseded.

Portfolio management:

- Required: broad regression and certification of current portfolio/analytics
  stack.
- Not required: historical portfolio risk foundation salvage, because current
  portfolio modules and tests are already extensive per the roadmap.

### 3. Which missing capabilities are merely nice to have?

- Evidence verification checklist helpers.
- Post-pilot archive export and manifest helper modules.
- Signature/notarization readiness metadata.
- Micro-live evidence package surfaces.
- Phase 54 pilot safety compatibility tests if current APIs no longer match.
- Historical dashboard print/export niceties.

These are useful for operator review and certification packaging, but they are
not prerequisites for broker safety, options income completion, futures
completion, or production certification kickoff.

### 4. Which historical work should never be brought back?

- `e596a96`: institutional multi-broker live execution routing.
- `bb00c5c`: shadow-routing runtime producers through the historical event bus.
- `01a9d73`, `58ae6a8`, `bbdc520`, `caf254f`, `7f262fb`, `0fae9de`: broad
  orchestrator, merge, and integration rewrites.
- Historical broker adapter, credential loading, live mode inheritance, or
  execution routing changes outside a dedicated broker authority milestone.
- Historical API/web wiring bundled with evidence commits unless separately
  approved and reconstructed against current architecture.

Repository evidence: these are rejected or marked superseded in
`docs/governance/CSS_FINAL_CONSOLIDATION_ROADMAP.md` and
`docs/governance/PHASE1_PERSISTENCE_FOUNDATION_SALVAGE_PLAN.md` because they
conflict with current architecture or carry high regression risk.

## Final Recommendation

Recommendation: Stop historical recovery and begin the remaining CSS roadmap (Options Income completion, certification, etc.).

Rationale:

- The highest-value historical recoveries are already complete and validated:
  evidence hashing, persistent execution journal, runtime event normalization,
  and evidence governance.
- Remaining historical work is mostly optional evidence packaging or obsolete
  runtime/broker/orchestrator integration.
- The current branch is already ready for broader finite regression as the
  consolidation candidate, according to the final roadmap.
- The blocking work for production value is not more historical salvage. It is
  final regression/certification and the forward roadmap: options income
  completion, options/futures live-readiness decisions, and production
  certification evidence.
- Continuing full salvage would spend engineering effort on artifacts that do
  not close the most important remaining product gaps.

Consolidation decision: historical recovery should be considered complete for
this branch. Future work should proceed through the main CSS roadmap, with any
remaining evidence helpers treated as optional backlog rather than consolidation
blockers.
