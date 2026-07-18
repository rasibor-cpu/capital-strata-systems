# PHASE 173A — Executive Morning Intelligence Briefing (MIB) Architecture

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Phase type:** Architecture only  
**Status:** DESIGN COMPLETE — no production code, no tests, no commits, no pushes  
**Date:** 2026-07-18  

---

## 1. Purpose

Design an enterprise **Morning Intelligence Briefing (MIB)** that becomes the
primary CSS landing surface every morning. The MIB summarizes everything CSS
observed overnight into a single, fail-closed, advisory-only executive package.

Phase 173A defines architecture only. It does **not** implement producers,
APIs, UI, storage writers, Mission Control pages, or mobile screens.

### Safety locks (immutable for this phase and for any future MIB implementation)

| Flag | Locked value |
|---|---|
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `live_trading_blocked` | `true` |
| `broker_execution_armed` | `false` |

The MIB **never** places orders, arms brokers, mutates risk limits, changes
strategy weights, restarts runtime services, or grants trading authority.

---

## 2. Product Definition

### 2.1 What the MIB is

The MIB is the **primary morning landing page** for CSS operators and
executives. It is a read-only institutional briefing that:

1. Aggregates overnight observations from existing CSS producers.
2. Presents a fixed twelve-plus-one section layout (sections 1–13 below).
3. Surfaces GREEN / AMBER / RED posture with fail-closed fallbacks.
4. Feeds Mission Control and mobile as first-class consumers of the same
   canonical briefing contract.

### 2.2 What the MIB is not

- Not a new trading decision engine.
- Not a replacement for Phase 159A Executive Decision Brief (159A remains a
  reusable aggregation substrate; MIB is the morning-specific product surface).
- Not an overnight **process lifecycle** controller (that is Phase 172A).
- Not a broker execution path.

### 2.3 Relationship to existing surfaces

| Existing surface | Relationship to MIB |
|---|---|
| Phase 159A Executive Decision Brief | Upstream aggregation pattern and many field families reused |
| `BriefingGenerator` type `MORNING` | Existing narrative stub; becomes one input, not the product |
| Session Command Centre `daily_executive_summary` | Partial executive text; absorbed into MIB Executive Summary |
| Mission Control Executive Overview / KPIs | Primary desktop consumer of MIB projections |
| Mobile Command Centre | Primary mobile consumer of a compact MIB payload |

---

## 3. Canonical Architecture

### 3.1 Layering

```text
┌─────────────────────────────────────────────────────────────────┐
│  Presentation                                                    │
│  Mission Control MIB page · Mobile MIB card · Optional MD/email  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ consumes
┌───────────────────────────────▼─────────────────────────────────┐
│  MIB Contract                                                    │
│  css.morning_intelligence_briefing.v1                            │
│  (single briefing document + section envelopes + safety locks)   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ assembled by
┌───────────────────────────────▼─────────────────────────────────┐
│  MIB Assembler (future implementation — out of scope for 173A)   │
│  Read-only fan-in · freshness tagging · fail-closed section fill │
└───────────────────────────────┬─────────────────────────────────┘
                                │ reads
┌───────────────────────────────▼─────────────────────────────────┐
│  Existing CSS Producers                                          │
│  Runtime · Regime · CAIE/OI · Broker 155C · Committees ·         │
│  Portfolio · Confidence · Learning · Reporting · Intel adapters  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Proposed contract identity

| Field | Value |
|---|---|
| Contract id | `css.morning_intelligence_briefing.v1` |
| Artifact (proposed) | `artifacts/briefings/morning_intelligence_briefing_latest.json` |
| Dated archive (proposed) | `artifacts/briefings/archive/YYYY-MM-DD/mib.json` |
| Markdown twin (proposed) | `artifacts/briefings/archive/YYYY-MM-DD/mib.md` |
| Assembly mode | Advisory aggregation only — no recalculation of gate/broker authority |

### 3.3 Overnight observation window

| Term | Definition |
|---|---|
| **Overnight window** | From prior session close / last operator sign-off through current morning briefing cutover |
| **Cutover** | Configurable local morning time (default proposal: operator timezone 06:00–08:00) |
| **Coverage** | Runtime heartbeats, market/intel envelopes, regime transitions, opportunity rankings, broker readiness, committee votes, portfolio snapshots, learning deltas, alerts |

Phase 172A overnight **runtime lifecycle** remains separate. MIB consumes
lifecycle/health evidence; it does not own process start/stop.

### 3.4 Fail-closed rules

When a section cannot be proven fresh and authoritative:

1. Section status = `UNAVAILABLE` or `FAIL_CLOSED`.
2. Section payload uses explicit `DATA UNAVAILABLE` markers.
3. Executive Summary and Recommended Actions must not invent GREEN readiness.
4. Overall MIB posture degrades to the worst non-unavailable section severity
   among Runtime Health, Broker Health, and Risk Committee.

Freshness labels reuse Mission Control vocabulary: `FRESH` / `AGING` /
`STALE` / `UNAVAILABLE`.

---

## 4. Section Specifications

For every section below:

- **Purpose** — why the section exists on the morning landing page  
- **Required data sources** — conceptual inputs  
- **Existing CSS producers** — current modules (paths)  
- **Existing CSS consumers** — current readers/surfaces  
- **Required APIs** — existing plus proposed MIB APIs  
- **Storage** — current and proposed  
- **Refresh frequency** — producer cadence vs MIB assembly cadence  
- **Mission Control integration** — how MC should surface the section  
- **Mobile integration** — how mobile should surface the section  
- **Future AI enhancements** — post-173A opportunities (non-binding)

---

### 4.1 Executive Summary

**Purpose**  
Give the CIO/operator a 30-second overnight posture: overall status, regime,
confidence, top opportunity, top risk, and whether CSS is advisory-ready.

**Required data sources**  
- Aggregated overnight status from all MIB sections  
- Phase 159A brief fields: `overall_status`, `market_regime`,
  `decision_confidence`, `broker_health`, `runtime_health`,
  `top_opportunities`, `top_risks`, `recommended_actions`  
- Session Command Centre `daily_executive_summary`  
- `BriefingGenerator` `MORNING` narrative

**Existing CSS producers**  
- `backend/reporting/executive_decision_brief.py`  
- `backend/reporting/executive_recommendations.py`  
- `backend/reporting/executive_summary_formatter.py`  
- `backend/intelligence/briefings.py` (`MORNING`)  
- `backend/intelligence/intelligence_service.py`  
- `dashboard/runtime/frontend_contract.py` → `session_command_centre()`

**Existing CSS consumers**  
- Web Session Command Centre (`dashboard/web/web_app.py`)  
- Mobile Command Centre (`dashboard/mobile/mobile_app.py`)  
- Mission Control executive dashboard / overview pages  
- Tests under `tests/test_phase159a_executive_decision_brief.py`

**Required APIs**  
- Existing: `/api/v1/session-command-centre`  
- Existing: Mission Control `/mission-control/api/state` (executive projections)  
- Proposed: `GET /api/v1/morning-intelligence-briefing`  
- Proposed: `GET /api/v1/morning-intelligence-briefing/executive-summary`

**Storage**  
- Current: `artifacts/reports/` via reporting archive helpers  
- Proposed: top-level fields inside `morning_intelligence_briefing_latest.json`

**Refresh frequency**  
- Upstream producers: on request / cycle  
- MIB assembly: once at morning cutover + on-demand refresh; Executive Summary
  regenerates whenever any critical section refreshes

**Mission Control integration**  
- Primary hero block on a new **Morning Briefing** landing page  
- Reuse Institutional Executive Dashboard patterns from MC-007A  
- Offline banner when runtime hash / freshness fails (MC-003/004 rules)

**Mobile integration**  
- First card in morning Command Centre  
- Compact fields: status chip, regime, confidence, one opportunity, one risk

**Future AI enhancements**  
- LLM narrative grounded only in cited MIB section hashes  
- Multi-day “what changed overnight” contrast vs prior MIB archive  
- Spoken audio briefing export for operators

---

### 4.2 Runtime Health

**Purpose**  
Confirm CSS was alive, coherent, and fresh overnight — supervisor heartbeat,
artifact freshness, session continuity, and alert burden.

**Required data sources**  
- Supervisor state and heartbeat age  
- Runtime artifact freshness labels  
- Session validation / continuity  
- Runtime performance and alert counts

**Existing CSS producers**  
- `backend/runtime/css_runtime_supervisor.py`  
- `backend/runtime/runtime_artifact_freshness.py`  
- `backend/monitoring/runtime_health_aggregator.py`  
- `backend/runtime/runtime_artifact_publisher.py`  
- Launcher / dashboard publish path (`scripts/css_live_dashboard.py`,
  `launcher/css_mobile_launcher.py`)

**Existing CSS consumers**  
- Mission Control `health`, `system_metrics`, runtime/heartbeat APIs  
- Phase 159A `runtime_health`  
- Certification / readiness validators  
- Mobile Operational Health (Phase 134A lineage)

**Required APIs**  
- Existing: `/api/runtime-health`, `/api/runtime-performance`,
  `/api/session-validation`, `/api/runtime-health-trend`,
  `/api/runtime-artifact-freshness`, `/api/runtime-session-continuity`  
- Existing MC: `/mission-control/api/health`, `/runtime`, `/heartbeat`,
  `/runtime-source`  
- Proposed: MIB section embed via `/api/v1/morning-intelligence-briefing`

**Storage**  
- Canonical: `runtime/supervisor/css_runtime_supervisor_state.json`  
- Related: `artifacts/validation*`, cycle artifacts under `artifacts/`  
- Note Phase 171A/171B supervisor path isolation for publisher races

**Refresh frequency**  
- Heartbeat: ~10s  
- Freshness STALE threshold: >120s without heartbeat  
- MIB section: snapshot at cutover + live refresh while page open (MC ~5s UI hint)

**Mission Control integration**  
- Runtime Health strip on MIB page  
- Link-through to MC Operations / runtime source panels

**Mobile integration**  
- Operational Health summary chip (FRESH/AGING/STALE)  
- Deep-link to existing mobile health section

**Future AI enhancements**  
- Overnight anomaly narrative (“heartbeat gaps between 02:14–02:31”)  
- Predictive STALE risk before cutover  
- Correlation of runtime degradation with broker or market events

---

### 4.3 Overnight Market Summary

**Purpose**  
Summarize what markets did overnight: liquidity, volatility, spreads, news/
macro envelopes, and notable external intel — the largest current product gap.

**Required data sources**  
- Market summary envelopes (liquidity/volatility/spread/regime stubs)  
- External intel adapters (news, macro, volatility, COT/GDELT/FRED/VIX where present)  
- Session market section from frontend contract / launcher

**Existing CSS producers**  
- Launcher-built `market_summary` in `launcher/css_mobile_launcher.py`  
- `intel/` collectors and adapters (GDELT, FRED, VIX, news, COT lineage)  
- Frontend contract market / opportunities market context  
- Opportunity intelligence engines consuming `market_summary`

**Existing CSS consumers**  
- Opportunity intelligence (`backend/analytics/opportunity_intelligence_engine.py`)  
- IIC portfolio context builders  
- Mission Control `market_intelligence` → KPI `market_health`

**Required APIs**  
- Existing: implicit via `/api/v1/frontend-state` market sections  
- Existing MC: market intelligence via `/mission-control/api/state`  
- Proposed: `GET /api/v1/overnight-market-summary` (new producer boundary)  
- Proposed: MIB section embed

**Storage**  
- Current: ad hoc `intel/` outputs; no dedicated overnight rollup store  
- Proposed: `artifacts/briefings/overnight_market_summary_latest.json`  
  plus dated archive under `artifacts/briefings/archive/`

**Refresh frequency**  
- Intel adapters: adapter-specific  
- Overnight rollup: once at cutover spanning the overnight window; optional
  hourly shadow snapshots for forensics

**Mission Control integration**  
- Dedicated Overnight Market panel on MIB page  
- Feeds `market_health` KPI with overnight provenance tags

**Mobile integration**  
- Two-line overnight market blurb + severity chip  
- Expandable detail only on demand (bandwidth-aware)

**Future AI enhancements**  
- Cross-asset overnight narrative with source citations  
- Event clustering (central bank, geopolitics, liquidity shocks)  
- “What matters for CSS books” filtering by open exposure

---

### 4.4 Market Regime Analysis

**Purpose**  
State the overnight and current regime classification, transitions, and
strategy implications — without re-implementing the canonical gate.

**Required data sources**  
- Canonical regime gate output  
- Portfolio market-regime intelligence  
- Regime history / learning mappings  
- Regime-aware allocation and weighting advisory outputs

**Existing CSS producers**  
- `engine/regime/regime_gate.py` (canonical)  
- `engine/adapters/regime_gate_adapter.py`  
- `backend/portfolio/market_regime_intelligence.py`  
- `backend/portfolio/regime_aware_allocation.py`  
- `backend/learning/regime_learning.py`  
- `backend/learning/regime_strategy_mapper.py`  
- `backend/market_intelligence/regime_aware_weighting_engine.py`  
- Intelligence/analytics regime detectors and history repository

**Existing CSS consumers**  
- Engine loop and portfolio decision orchestrator  
- Phase 159A `market_regime`  
- Mission Control market/KPI panels  
- Mobile learning / portfolio regime cards

**Required APIs**  
- Existing: `/api/market-regime-intelligence`, `/api/regime-aware-allocation`,
  `/api/regime-aware-weighting`, `/api/regime-learning`  
- Proposed: MIB section embed only (no second gate)

**Storage**  
- Regime history repository (analytics)  
- Decision packages under `artifacts/portfolio/`  
- MIB snapshot copies regime fields by value with provenance

**Refresh frequency**  
- Per engine cycle for live regime  
- Overnight analysis: transition timeline across overnight window at cutover

**Mission Control integration**  
- Regime timeline widget on MIB page  
- Consistency with MC market intelligence projections

**Mobile integration**  
- Regime chip + last transition timestamp  
- Optional “why” one-liner from explainability

**Future AI enhancements**  
- Regime transition early-warning scores  
- Counterfactual “if still Risk-Off” strategy notes  
- Natural-language regime brief grounded in gate evidence

---

### 4.5 Opportunity Ranking

**Purpose**  
Show what CSS would prioritize this morning under advisory-only capital
competition — ranked opportunities with explicit `NO_EXECUTION` semantics.

**Required data sources**  
- CAIE proposals / scores / shadow selections  
- Opportunity intelligence rankings  
- Trading opportunity ranking engines  
- IIC opportunity ranking inputs

**Existing CSS producers**  
- `backend/allocation/opportunity_proposal.py`  
- `backend/allocation/caie_scoring_engine.py`  
- `backend/allocation/caie_portfolio_optimizer.py`  
- `backend/allocation/caie_shadow_adapter.py`  
- `backend/runtime/caie_runtime_bridge.py`  
- `backend/analytics/opportunity_intelligence_engine.py`  
- `backend/trading/opportunity_ranking_engine.py`  
- `backend/investment_committee/opportunity_ranking.py`  
- Frontend opportunities scoring in `frontend_contract.py`

**Existing CSS consumers**  
- Mission Control `opportunity_ranking` (MC-007A) / Strategy War Room  
- Capital allocation intelligence APIs  
- Phase 159A `top_opportunities`  
- Mobile opportunities / Command Centre posture

**Required APIs**  
- Existing: `/api/v1/opportunity-intelligence` (`css.opportunity_intelligence.v1`)  
- Existing: `/api/v1/opportunities`  
- Existing: `/api/v1/capital-allocation-intelligence`  
- Proposed: MIB top-N embed (`ranked_opportunities`, `selected_opportunities`)

**Storage**  
- Current: primarily advisory/shadow in-memory or cycle artifacts  
- Proposed: freeze morning top-N into MIB archive for day-over-day compare

**Refresh frequency**  
- CAIE bridge: after trade-gate completed cycles  
- OI APIs: on request  
- MIB: cutover snapshot + optional mid-morning refresh (labeled as refresh, not overnight)

**Mission Control integration**  
- Ranked table on MIB page with provenance and freshness  
- Deep-link to Strategy War Room / opportunity ranking projection

**Mobile integration**  
- Top 3 opportunities only  
- Score + one-line thesis; no execution controls

**Future AI enhancements**  
- Overnight opportunity drift (“rose 4 ranks since 22:00”)  
- Conflict detection vs open portfolio exposures  
- Thesis compression with explainability links

---

### 4.6 Confidence Analysis

**Purpose**  
Explain how much the institution should trust overnight recommendations and
decision posture — calibration, sparsity, and confidence drivers.

**Required data sources**  
- Decision confidence framework outputs  
- Confidence calibration / learning  
- Validation confidence  
- Broker performance confidence where relevant

**Existing CSS producers**  
- `backend/analytics/decision_confidence_framework.py`  
- `backend/portfolio/confidence_calibration_engine.py`  
- `backend/intelligence/confidence_engine.py`  
- `backend/intelligence/global_intelligence/confidence_engine.py`  
- `backend/validation/validation_confidence_engine.py`  
- `backend/analytics/broker_performance_confidence.py`

**Existing CSS consumers**  
- Phase 159A `decision_confidence`  
- Mission Control decision / recommendation panels  
- Learning calibration APIs / mobile Learning section

**Required APIs**  
- Existing: `/api/confidence-calibration`,
  `/api/confidence-calibration-learning`  
- Note: decision confidence is largely in-process for 159A today  
- Proposed: `GET /api/v1/decision-confidence` (normalize fragmented producers)  
- Proposed: MIB section embed

**Storage**  
- Calibration history sparse → fail-closed `DATA UNAVAILABLE`  
- MIB stores computed confidence envelope with evidence pointers

**Refresh frequency**  
- On request / when recommendation history updates  
- MIB: cutover + when Executive Summary refreshes

**Mission Control integration**  
- Confidence gauge + driver breakdown on MIB  
- Align with MC-006 decision intelligence confidence fields

**Mobile integration**  
- Single confidence percentage + traffic light  
- “Low sample” badge when history sparse

**Future AI enhancements**  
- Confidence decomposition narrative  
- Drift alerts vs last 7 mornings  
- Automatic “do not escalate” advice when confidence below policy floor

---

### 4.7 Broker Health

**Purpose**  
Prove overnight broker operational posture using the canonical 155C model —
connectivity, credentials, readiness, parity — without arming execution.

**Required data sources**  
- Canonical broker operational status  
- Credential diagnostics  
- Read-only live validation (Coinbase/OANDA lineage)  
- Broker readiness / parity snapshots

**Existing CSS producers**  
- `backend/runtime/broker_operational_status.py` (canonical 155C)  
- Broker credential diagnostics / readiness modules  
- Options broker health helpers  
- Launcher `broker_summary` / `broker_operational_status` blocks

**Existing CSS consumers**  
- Frontend contract `broker_operational_status`  
- Mission Control broker telemetry (`/mission-control/api/brokers`)  
- Phase 159A `broker_health` / details  
- IIC context; mobile broker mode displays

**Required APIs**  
- Existing: `/api/v1/broker-readiness`, broker read-only / diagnostics /
  parity / Coinbase & OANDA validation routes,
  `/runtime-certification-snapshot`  
- Existing MC: `/mission-control/api/brokers`  
- Proposed: MIB section embed only

**Storage**  
- Account/session artifacts (`artifacts/css_account_state_*.json`, etc.)  
- Certification snapshots carried in broker summary payloads  
- MIB freezes morning broker posture for audit

**Refresh frequency**  
- Per account refresh / cycle publish  
- MIB: cutover snapshot + live refresh while viewing

**Mission Control integration**  
- Broker health grid on MIB (per venue)  
- Link to MC-005/007B broker consoles

**Mobile integration**  
- Per-broker status chips  
- Block any language that implies execution armed

**Future AI enhancements**  
- Overnight outage timelines per broker  
- Credential expiry forecasting  
- Cross-broker parity anomaly explanations

---

### 4.8 Risk Committee Summary

**Purpose**  
Present overnight / morning institutional risk posture: committee votes,
vetoes, consensus, and required actions — advisory only.

**Required data sources**  
- Portfolio risk committee package  
- Phase 167 multi-committee votes / consensus / veto hierarchy  
- Investment committee engine outputs  
- Required actions / risk veto markers

**Existing CSS producers**  
- `backend/portfolio/portfolio_risk_committee.py`  
- `backend/investment_committee/committee_members.py`  
- `backend/investment_committee/voting_engine.py`  
- `backend/investment_committee/committee_consensus.py`  
- `backend/investment_committee/committee_history.py`  
- `backend/intelligence/investment_committee_engine.py`  
- MC projections: `risk_committee`, `committee_projection`

**Existing CSS consumers**  
- Portfolio decision orchestrator / explainability  
- Mission Control risk / investment / capital / execution committee panels  
- Dashboard `/api/portfolio-risk-committee`  
- Mobile risk cards in Command Centre

**Required APIs**  
- Existing: `/api/portfolio-risk-committee`  
- Existing: `/api/v1/institutional-investment-committee`  
- Existing: `/api/v1/institutional-investment-committee/votes`  
- Proposed: MIB section embed with overnight vote delta

**Storage**  
- Committee history currently largely in-memory (Phase 167)  
- Portfolio decisions under `artifacts/portfolio/`  
- Proposed: persist morning committee snapshot into MIB archive
  (addresses overnight auditability gap)

**Refresh frequency**  
- On advisory package build  
- MIB: cutover freeze + optional live recompute labeled separately

**Mission Control integration**  
- Committee vote matrix on MIB  
- Deep-link to MC committee views (MC-007A)

**Mobile integration**  
- Consensus chip + veto flag  
- Top required action only

**Future AI enhancements**  
- Overnight dissent summarization  
- Veto risk prediction before session open  
- Natural-language committee minutes from structured votes

---

### 4.9 Portfolio Summary

**Purpose**  
Show morning book posture: capital, exposure, diversification, concentration,
portfolio health — grounded in runtime portfolio artifacts.

**Required data sources**  
- Frontend `portfolio_summary` contract fields  
- Runtime portfolio state / advisory snapshot  
- Portfolio intelligence / decision orchestrator outputs  
- Optimizer / construction advisory (157 lineage) where available

**Existing CSS producers**  
- `dashboard/runtime/frontend_contract.py` → `portfolio_summary()`  
- `backend/portfolio/portfolio_intelligence_engine.py`  
- `backend/portfolio/portfolio_decision_orchestrator.py`  
- `backend/portfolio/runtime_portfolio_state_builder.py`  
- `backend/portfolio/runtime_advisory_snapshot.py`  
- MC `portfolio_projection.py`

**Existing CSS consumers**  
- Desktop web panels; mobile PnL/positions  
- Mission Control portfolio command  
- Reporting engines

**Required APIs**  
- Existing: `/api/v1/frontend-state` → `portfolio_summary`  
- Existing: `/api/portfolio-intelligence`, `/api/portfolio-decision`,
  `/api/runtime-portfolio-state`, `/api/runtime-advisory-snapshot`,
  `/api/adaptive-portfolio`, `/api/capital-rotation`  
- Proposed: MIB section embed

**Storage**  
- `artifacts/runtime_portfolio_state.json`  
- `artifacts/portfolio_snapshot.json`  
- `artifacts/portfolio_decision.json`  
- `artifacts/portfolio/`  
- MIB copies morning portfolio envelope with artifact hashes

**Refresh frequency**  
- Every trading-cycle publish + on GET  
- MIB: cutover + live refresh

**Mission Control integration**  
- Portfolio health strip on MIB  
- Link to portfolio command / performance panels

**Mobile integration**  
- Equity / cash / exposure / health only  
- Suppress dense optimizer tables on small screens

**Future AI enhancements**  
- Overnight PnL attribution narrative  
- Concentration risk plain-language warnings  
- “What changed vs yesterday’s MIB portfolio freeze”

---

### 4.10 Recommended Actions

**Purpose**  
Provide an ordered, advisory-only morning action list for operators — never
BUY/SELL/EXECUTE directives in Mission Control language policy terms.

**Required data sources**  
- `executive_recommendations.generate_recommended_actions()`  
- Risk committee `required_actions`  
- Validation / readiness recommended actions  
- MC recommendation projection (forbids execution verbs)

**Existing CSS producers**  
- `backend/reporting/executive_recommendations.py`  
- MC `recommendation_projection.py`  
- Validation modules exposing `recommended_actions`  
- Risk committee required actions

**Existing CSS consumers**  
- Phase 159A recommended actions  
- Mission Control `/mission-control/api/recommendation`  
- Certification / readiness reports  
- Mobile Command Centre intelligence cards

**Required APIs**  
- Existing: embedded in brief / committee / validation payloads  
- Existing MC: `/mission-control/api/recommendation`  
- Existing: `/api/explainability` for rationale  
- Proposed: MIB `recommended_actions[]` with priority + provenance

**Storage**  
- Optional report archive / decision record POST paths  
- MIB archive is the morning system of record for action lists

**Refresh frequency**  
- Derived on brief/state build  
- MIB: cutover + when critical health/risk sections change

**Mission Control integration**  
- Action checklist panel (advisory; no execution controls)  
- Align with MC-006 language policy

**Mobile integration**  
- Top 3 actions with severity  
- Tap-through to explanation only

**Future AI enhancements**  
- Action deduplication across committees  
- Operator playbook linking  
- Completion tracking against next evening brief (still non-execution)

---

### 4.11 AI Insights

**Purpose**  
Surface explainable overnight insights and narratives that help executives
understand *why* the book and gates look as they do — without a free-form
unbounded LLM authority path.

**Required data sources**  
- AI market narrative from frontend contract  
- Intelligence service + briefing generator  
- Explainability engine outputs / evidence graphs  
- Intel pipeline highlights  
- Optional AI opportunity scorer signals

**Existing CSS producers**  
- `frontend_contract._ai_market_narrative()` and intelligence cards  
- `backend/intelligence/intelligence_service.py`  
- `backend/intelligence/briefings.py`  
- `backend/intelligence/ai_opportunity_scorer.py`  
- Explainability stack (`explainability_engine`, intelligence explainability)  
- MC `explanation_projection.py`  
- `intel/` adapters

**Existing CSS consumers**  
- Session Command Centre intelligence summary/cards  
- Mission Control decision explanation / evidence  
- Dashboard intelligence report surfaces  
- Mobile Command Centre intelligence cards

**Required APIs**  
- Existing: `/api/v1/session-command-centre` narrative fields  
- Existing: `/api/explainability`  
- Existing MC: `/mission-control/api/explanation`  
- Proposed: `GET /api/v1/morning-ai-insights` (bounded, citation-required)  
- Proposed: MIB section embed

**Storage**  
- `intel/` adapter outputs; report artifacts if archived  
- Proposed: insights bundle inside MIB with `citations[]` and `model_policy`

**Refresh frequency**  
- On frontend payload build  
- MIB: cutover narrative freeze + optional live refresh labeled as live

**Mission Control integration**  
- Insights panel with mandatory citation chips  
- Fail-closed if explainability hash missing

**Mobile integration**  
- 1–3 insight bullets max  
- No unconstrained chat surface in v1

**Future AI enhancements**  
- Grounded RAG over overnight MIB archives only  
- Counterfactual “what would change confidence” notes  
- Multimodal chart callouts (still advisory)

---

### 4.12 Learning Summary

**Purpose**  
Show what CSS learned overnight / recently: trade counts, optimality,
strategy leaders, missed opportunities, factor/regime learning deltas.

**Required data sources**  
- Autonomous learning controller `learning_summary`  
- Phase 139A learning modules (factor performance, attribution, reliability,
  regime learning, adaptive weights, confidence calibration learning,
  engine health learning)  
- Continuous / closed-loop learning engines

**Existing CSS producers**  
- `backend/analytics/autonomous_learning_controller.py`  
- `backend/learning/*` (Phase 139A set)  
- `continuous_learning_feedback.py` / `closed_loop_learning_engine.py`
  (learning lineage)

**Existing CSS consumers**  
- Mobile Learning & Optimization section  
- Mission Control performance attribution / institutional reporting  
- Learning GET APIs listed below

**Required APIs**  
- Existing: `/api/factor-performance`, `/api/factor-attribution`,
  `/api/rolling-reliability`, `/api/regime-learning`,
  `/api/adaptive-weight-recommendations`,
  `/api/confidence-calibration-learning`, `/api/engine-health-learning`  
- Proposed: MIB learning envelope embed

**Storage**  
- Advisory history / completed-trade learning records (read-oriented)  
- MIB stores morning learning delta snapshot

**Refresh frequency**  
- On request from history  
- MIB: cutover learning delta vs prior MIB archive

**Mission Control integration**  
- Learning delta panel on MIB  
- Link to MC performance attribution projection

**Mobile integration**  
- Existing Learning & Optimization section becomes MIB deep-link target  
- Show overnight delta headline on home card

**Future AI enhancements**  
- “What we should unlearn” suggestions  
- Regime-conditioned learning quality scores  
- Automatic experiment proposals (still non-execution)

---

### 4.13 Executive KPIs

**Purpose**  
Provide the institutional KPI board for the morning: uptime, health family,
alerts, trade/execution quality, system/RC1 readiness — one glance.

**Required data sources**  
- MC `build_executive_kpi_board()` inputs: platform/runtime/broker/portfolio/
  risk/market/alerts/trading/certification

**Existing CSS producers**  
- `dashboard/mission_control/system_metrics.py` → `build_executive_kpi_board()`  
- Wiring in `dashboard/mission_control/contracts.py` (`executive_kpis`)

**Existing CSS consumers**  
- Mission Control Executive Overview  
- Institutional executive dashboard  
- Source consistency checks across MC projections

**Required APIs**  
- Existing: via `/mission-control/api/state` → `executive_kpis`  
- Proposed: MIB includes `executive_kpis` mirror with same hash provenance  
- Optional later: `GET /api/v1/executive-kpis` for non-MC clients

**Storage**  
- Derived; no dedicated KPI file today  
- MIB archive freezes morning KPI board for audit

**Refresh frequency**  
- MC UI refresh hint ~5s; tied to runtime/heartbeat snapshot hash  
- MIB: cutover freeze + live mirror while page open

**Mission Control integration**  
- KPI board remains authoritative in MC-005; MIB embeds the same board  
- Hash alignment required with runtime/heartbeat (MC source consistency)

**Mobile integration**  
- Reduced KPI set: runtime, broker, portfolio, risk, alerts  
- Full board remains desktop/MC

**Future AI enhancements**  
- KPI anomaly storytelling  
- Morning vs 7-day baseline sparklines with plain-language deltas  
- Readiness forecast toward RC1 / live gates (advisory)

---

## 5. Cross-Cutting Integration Design

### 5.1 Proposed MIB assembler responsibilities (future phase)

1. Resolve overnight window timestamps.  
2. Read existing producers / APIs / artifacts (no authority mutation).  
3. Build `css.morning_intelligence_briefing.v1` with 13 section envelopes.  
4. Attach freshness, provenance, runtime hash, decision hash when available.  
5. Apply fail-closed rules and safety locks.  
6. Persist latest + dated archive JSON/MD.  
7. Serve Mission Control and mobile from the same contract.

### 5.2 Proposed APIs (implementation later)

| Method | Path | Role |
|---|---|---|
| GET | `/api/v1/morning-intelligence-briefing` | Full MIB contract |
| GET | `/api/v1/morning-intelligence-briefing/executive-summary` | Section 1 only |
| GET | `/api/v1/overnight-market-summary` | Section 3 producer boundary |
| GET | `/api/v1/morning-ai-insights` | Section 11 bounded insights |
| GET | `/mission-control/api/morning-briefing` | MC projection wrapper |

All routes remain GET-only for v1. No POST that arms trading.

### 5.3 Mission Control

- New primary landing route: **Morning Intelligence Briefing**  
- Reuses MC-003/004 runtime snapshot + freshness  
- Reuses MC-005 KPI board and broker telemetry  
- Reuses MC-006 recommendation / explanation language policy  
- Reuses MC-007A opportunity / committee / executive projections  
- Source consistency: MIB hash must align with runtime/heartbeat when online

### 5.4 Mobile

- Phase 127 lineage remains the host (`dashboard/mobile/*`,
  `launcher/css_mobile_launcher.py`)  
- Morning home = compact MIB (sections 1, 2, 4, 5, 7, 10, 13 first)  
- Dense sections (3, 6, 8, 9, 11, 12) progressive disclosure  
- Emergency stop / controls remain outside MIB advisory content

### 5.5 Storage layout (proposed)

```text
artifacts/briefings/
  morning_intelligence_briefing_latest.json
  overnight_market_summary_latest.json
  archive/
    YYYY-MM-DD/
      mib.json
      mib.md
      overnight_market_summary.json
```

Retention policy (proposal): keep daily archives ≥ 90 days; latest always
overwritten atomically.

### 5.6 Refresh policy (summary)

| Layer | Cadence |
|---|---|
| Supervisor heartbeat | ~10s |
| Artifact STALE threshold | >120s |
| Trading-cycle publishes | per cycle |
| MIB cutover assembly | once each morning window |
| MIB live page refresh | reuse MC ~5s hint while viewing |
| Overnight market rollup | cutover (+ optional hourly shadow) |

---

## 6. Gap Analysis (Architecture)

| Section | Existing coverage | Gap |
|---|---|---|
| Executive Summary | Strong (159A + Command Centre + MORNING stub) | Need morning-specific product contract |
| Runtime Health | Strong | Need overnight timeline rollup |
| Overnight Market Summary | Weak | Needs new rollup producer + storage |
| Market Regime | Strong | Need overnight transition timeline packaging |
| Opportunity Ranking | Strong | Need morning freeze for day-over-day compare |
| Confidence Analysis | Strong but fragmented | Normalize API surface |
| Broker Health | Strong (155C) | Morning freeze + outage timeline |
| Risk Committee | Strong (167) | Persist overnight committee snapshots |
| Portfolio Summary | Strong | Morning hash-linked freeze |
| Recommended Actions | Strong | Deduplicated morning action list |
| AI Insights | Partial | Bounded citation-required insights contract |
| Learning Summary | Strong | Overnight delta vs prior MIB |
| Executive KPIs | Strong in MC | Mirror into MIB + mobile subset |

---

## 7. Non-Goals (Phase 173A)

- No production code changes  
- No tests  
- No commits or pushes  
- No new execution authority  
- No replacement of canonical regime gate or broker operational status  
- No overnight process orchestration (owned by Phase 172A)  
- No email/SMS delivery implementation (architecture allows future exporters)

---

## 8. Recommended Follow-On Phases (non-binding)

| Phase idea | Intent |
|---|---|
| 173B | MIB contract + assembler + artifact persistence (still advisory) |
| 173C | Mission Control Morning Briefing landing page |
| 173D | Mobile morning compact MIB |
| 173E | Overnight Market Summary producer + intel fan-in |
| 173F | AI Insights bounded citation layer |

Exact numbering is reserved for governance approval.

---

## 9. Governance Statement

Phase 173A is architecture-only documentation. It defines the enterprise
Morning Intelligence Briefing as the primary morning landing experience and
maps each required section to existing CSS producers, consumers, APIs,
storage, refresh expectations, Mission Control, mobile, and future AI work.

**Deliverable for this phase:**

- `docs/governance/PHASE_173A_EXECUTIVE_MORNING_BRIEFING_ARCHITECTURE.md`

**Explicitly not delivered:**

- Production code  
- Tests  
- Commits  
- Pushes  

---

## 10. Traceability Index

| Concern | Primary references |
|---|---|
| Executive aggregation | `PHASE_159A_EXECUTIVE_DECISION_BRIEF.md` |
| Runtime / freshness | `PHASE_134A_*`, `PHASE_MC_003_*`, `PHASE_MC_004_*`, `PHASE_171A/B_*` |
| Overnight lifecycle (distinct) | `PHASE_172A_CANONICAL_RUNTIME_LIFECYCLE.md` |
| Broker health | `PHASE_155C_*`, `PHASE_155D_*` |
| Opportunities / CAIE | `PHASE_155A/B/C/D_*`, `PHASE_MC_007A_*` |
| Committees | `PHASE_167_*` |
| Learning | `PHASE_139A_*` |
| Explainability | `PHASE_132_EXPLAINABILITY.md` |
| Mobile | `PHASE_127_*` |
| Mission Control stack | `docs/architecture/CSS_MISSION_CONTROL_ARCHITECTURE.md` |
| Frontend contract | `dashboard/runtime/frontend_contract.py`, `docs/frontend_contracts/frontend_contract_v1.md` |
