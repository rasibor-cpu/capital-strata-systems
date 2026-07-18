# PHASE 173B — Canonical Executive Intelligence Data Layer and Dated Morning Briefing Archive

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Phase type:** Architecture only  
**Status:** DESIGN COMPLETE — no production code, no tests, no runtime artifacts, no commits, no pushes  
**Date:** 2026-07-18  
**Upstream:** `docs/governance/PHASE_173A_EXECUTIVE_MORNING_BRIEFING_ARCHITECTURE.md`  
**Contract family:** `css.executive_morning_brief.v1`  

---

## Executive Summary

Phase 173B designs the **canonical Executive Intelligence Data Layer** that powers
every CSS executive briefing, starting with the Morning Intelligence Briefing
(MIB) product defined in Phase 173A.

The layer collapses overnight executive intelligence into one durable model —
**`ExecutiveMorningBrief`** — organized as **five panels**:

1. Executive Decision  
2. Operational Health  
3. Market Intelligence  
4. Trading Intelligence  
5. Learning  

Every completed morning briefing is stored in a **date-indexed, versioned,
immutable archive** so any report can be retrieved later by `YYYY-MM-DD`.

### Design verdict (storage)

**Recommend filesystem-primary archive under `artifacts/`**, with a dated
hierarchy and a JSON manifest index. Do **not** introduce a database as source
of truth. Optionally add a thin SQLite query index only if archive browsing
becomes hot — payloads remain JSON/Markdown on disk.

### Safety locks (immutable)

| Flag | Locked value |
|---|---|
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `live_trading_blocked` | `true` |
| `broker_execution_armed` | `false` |

No report may grant execution authority. No credentials, secrets, tokens, or
protected broker fields may be stored in reports.

### Explicit non-delivery (this phase)

- No production code  
- No tests  
- No runtime artifacts  
- No database files  
- No commits  
- No pushes  

---

## Design Principles

1. **One canonical model** — `ExecutiveMorningBrief` is the only morning
   executive payload Mission Control and mobile consume for this product.
2. **Aggregate, do not re-decide** — reuse existing CSS producers; never
   re-implement regime gate, broker authority, or execution paths.
3. **Fail closed** — stale, missing, malformed, or inconsistent evidence yields
   `FAILED` / unavailable sections; never synthesize market, broker, portfolio,
   or runtime facts.
4. **Date is the primary key** — canonical report date is `YYYY-MM-DD`
   (operator reporting timezone, stored alongside UTC window bounds).
5. **Immutability after FINAL** — finalized reports are never silently
   overwritten; regenerations create new versions.
6. **Provenance over copies** — reference source artifacts by path + hash;
   do not indiscriminately duplicate large runtime payloads.
7. **Advisory-only language** — Mission Control recommendation language policy
   applies (no BUY/SELL/EXECUTE directives).
8. **Smallest maintainable store** — filesystem JSON + MD (+ optional PDF later)
   with a manifest index, matching existing CSS `artifacts/` conventions.
9. **Extensible briefing family** — morning is first; midday/close/weekly/
   monthly share the archive spine later.
10. **173A compatibility** — five panels are the canonical product shape; the
    thirteen 173A sections map into these panels (see § Mapping).

---

## Relationship to Phase 173A

| 173A concept | 173B refinement |
|---|---|
| `css.morning_intelligence_briefing.v1` | Superseded as product contract by `css.executive_morning_brief.v1` (same advisory intent; five-panel packaging) |
| 13 landing sections | Mapped into 5 panels + envelope KPIs/meta |
| Proposed `artifacts/briefings/archive/YYYY-MM-DD/` | Upgraded to versioned `artifacts/runtime_reports/morning_briefings/YYYY/MM/YYYY-MM-DD/vNNN/` |
| Latest pointer file | Retained via manifest `latest_report_date` + `current` symlink/pointer file |
| Retention ≥90 days | Strengthened to **indefinite** unless future governance authorizes deletion |

173A remains the product/UX architecture. 173B is the **data layer + archive**.

---

## Mapping: 173A Sections → Five Panels

| Five-panel (173B) | 173A sections absorbed |
|---|---|
| **Executive Decision** | Executive Summary, Confidence Analysis, Risk Committee Summary, Recommended Actions |
| **Operational Health** | Runtime Health, Broker Health |
| **Market Intelligence** | Overnight Market Summary, Market Regime Analysis |
| **Trading Intelligence** | Opportunity Ranking, Portfolio Summary |
| **Learning** | AI Insights, Learning Summary |
| **Envelope (not a panel)** | Executive KPIs, safety locks, freshness, provenance, validation |

---

## Canonical Objects (Minimum Set)

### 1. `ExecutiveMorningBrief`

Top-level morning report document (`schema_version = "css.executive_morning_brief.v1"`).

### 2. `MorningBriefArchiveRecord`

Filesystem/index record describing one stored report instance (date + version +
paths + lifecycle status).

### 3. `MorningBriefVersion`

Version envelope for a single `report_date` regeneration (`v001`, `v002`, …)
including who/what/when/reason metadata.

### 4. `MorningBriefManifest`

Archive index for fast retrieval (`manifest.json` at archive root).

### 5. `MorningBriefProvenance`

Source references: producer module, artifact path, content hash, generated_at,
freshness label, optional `decision_hash` / `state_hash`.

### 6. `MorningBriefValidationResult`

Validation outcome: pass/fail, checks run, blockers, section availability map,
whether finalization is allowed.

---

## ExecutiveMorningBrief Canonical Contract

### Envelope fields (required)

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `css.executive_morning_brief.v1` |
| `report_date` | string | `YYYY-MM-DD` canonical date key |
| `generated_at_utc` | string | ISO-8601 UTC |
| `reporting_window_start_utc` | string | Overnight window start |
| `reporting_window_end_utc` | string | Overnight window end / cutover |
| `runtime_id` | string \| null | From canonical runtime snapshot |
| `supervisor_id` | string \| null | From supervisor state |
| `state_hash` | string \| null | Runtime/state hash used for consistency |
| `decision_hash` | string \| null | When decision intelligence available |
| `data_freshness_status` | enum | `FRESH` \| `AGING` \| `STALE` \| `UNAVAILABLE` |
| `report_status` | enum | `DRAFT` \| `VALIDATING` \| `FINAL` \| `FAILED` \| `SUPERSEDED` |
| `version` | string | `v001`, `v002`, … |
| `is_current_for_date` | bool | Newest validated current for that date |
| `advisory_only` | bool | Locked `true` |
| `execution_allowed` | bool | Locked `false` |
| `live_trading_blocked` | bool | Locked `true` |
| `broker_execution_armed` | bool | Locked `false` |
| `overall_status` | enum | `GREEN` \| `AMBER` \| `RED` \| `UNAVAILABLE` |
| `executive_kpis` | object | See KPI board below |
| `panels` | object | Five panels |
| `provenance` | `MorningBriefProvenance[]` | Source evidence list |
| `validation` | `MorningBriefValidationResult` | Required before FINAL |
| `narratives` | object | Optional bounded AI/text narratives (extensible) |
| `diff_vs_previous` | object \| null | Optional vs prior business-day current FINAL |

### Executive KPI board (envelope)

Aligned with Mission Control `build_executive_kpi_board()` vocabulary:

| KPI | Source family |
|---|---|
| `uptime` | Runtime / supervisor |
| `runtime_health` | Runtime health aggregator |
| `broker_health` | Broker operational status (155C) |
| `portfolio_health` | Portfolio summary / intelligence |
| `risk_health` | Risk / committee posture |
| `market_health` | Market intelligence / overnight + regime |
| `alert_count` | Alerts / ops |
| `trade_quality` / `execution_quality` | Trading quality signals (advisory) |
| `system_readiness` | Certification / readiness |
| `rc1_readiness` | RC1 readiness signals when present |

Missing KPI inputs → `UNAVAILABLE` (never invented).

---

## Five-Panel Field Specification

For each panel: required fields, producers, consumers, aggregation, freshness,
confidence, KPIs, advisory rules, APIs, storage, MC, mobile, AI extensibility,
and **exist vs new**.

Legend for producers: **EXISTING** = present in CSS today; **NEW** = required
for 173C+ implementation.

---

### Panel 1 — Executive Decision

**Purpose**  
CIO-facing overnight decision posture: status, confidence, committee outcome,
top risks/opportunities headline, ordered advisory actions.

**Required fields**

| Field | Notes |
|---|---|
| `panel_id` | `executive_decision` |
| `panel_status` | `GREEN` \| `AMBER` \| `RED` \| `UNAVAILABLE` |
| `freshness` | Panel freshness label |
| `confidence` | `0..1` or null + `confidence_status` |
| `overall_decision_status` | Aggregated decision posture |
| `market_regime_headline` | Short regime label (from Market panel provenance) |
| `decision_confidence` | From confidence producers |
| `committee_consensus` | IIC / risk consensus summary |
| `committee_vetoes` | List of veto markers if any |
| `top_opportunities_headline` | Top 1–3 ids/titles only |
| `top_risks` | Ordered risk bullets |
| `recommended_actions` | Advisory actions (no execution verbs) |
| `operational_warnings` | Cross-cutting warnings |
| `decision_intelligence` | Compact explainability pointers |
| `unavailable_fields` | Explicit list when fail-closed |

**Existing producers (EXISTING)**  
- `backend/reporting/executive_decision_brief.py`  
- `backend/reporting/executive_recommendations.py`  
- `backend/reporting/executive_summary_formatter.py`  
- `backend/analytics/decision_confidence_framework.py`  
- `backend/portfolio/confidence_calibration_engine.py`  
- `backend/portfolio/portfolio_risk_committee.py`  
- `backend/investment_committee/*` (Phase 167)  
- `backend/intelligence/briefings.py` (`MORNING` stub)  
- `dashboard/runtime/frontend_contract.py` → `daily_executive_summary`

**Existing consumers (EXISTING)**  
- Session Command Centre (web/mobile)  
- Mission Control executive / recommendation / decision panels  
- Phase 159A tests and formatters  

**Aggregation rules**  
1. Prefer Phase 159A brief fields when validation-pass.  
2. Committee consensus cannot upgrade posture above Operational Health / Broker
   fail-closed ceiling.  
3. `recommended_actions` dedupe across executive + risk committee sources.  
4. If confidence history sparse → `confidence_status = DATA_UNAVAILABLE`.  

**Freshness requirements**  
Panel freshness = worst of decision, confidence, and committee source freshness.
STALE committee-only history may still render with `AGING` if labeled; STALE
runtime/broker evidence forces panel `UNAVAILABLE` or degrades overall status.

**Confidence calculations**  
- Primary: Decision Confidence Framework score when present.  
- Secondary: calibration engine when history sufficient.  
- Panel confidence = min(primary, secondary) when both present; else available
  one; else null + unavailable.

**Executive KPIs contributed**  
`risk_health` (partial), readiness signals affecting `system_readiness`.

**Advisory-only requirements**  
Locked safety flags mirrored; actions must not imply order placement.

**API contracts**  
- Existing: `/api/v1/session-command-centre`; MC `/decision`, `/recommendation`  
- Future: embedded in `GET .../morning-briefings/{date}` panel slice  

**Storage contracts**  
Stored inside `executive_morning_brief.json` → `panels.executive_decision`.

**Mission Control integration**  
Hero block on morning landing + historical viewer.

**Mobile integration**  
Status chip, confidence, top action, top risk.

**Future AI narratives**  
Bounded “why this posture” paragraph with citations to provenance hashes only.

**NEW required**  
- Panel assembler mapping 159A + 167 → five-panel shape  
- Deduping action merger  

---

### Panel 2 — Operational Health

**Purpose**  
Prove overnight runtime and broker operational posture.

**Required fields**

| Field | Notes |
|---|---|
| `panel_id` | `operational_health` |
| `panel_status` | severity |
| `freshness` | label |
| `runtime_health` | Aggregated runtime status |
| `heartbeat_age_seconds` | If known |
| `supervisor_id` | Echo |
| `artifact_freshness` | Map of key artifacts → freshness |
| `session_continuity` | Continuity/validation summary |
| `broker_operational_status` | Canonical 155C summary (sanitized) |
| `broker_venues` | Per-venue status chips (no secrets) |
| `alert_summary` | Counts by severity |
| `overnight_incidents` | Timeline stubs if available |
| `unavailable_fields` | explicit |

**Existing producers (EXISTING)**  
- `backend/runtime/css_runtime_supervisor.py`  
- `backend/runtime/runtime_artifact_freshness.py`  
- `backend/monitoring/runtime_health_aggregator.py`  
- `backend/runtime/runtime_artifact_publisher.py`  
- `backend/runtime/broker_operational_status.py` (155C)  
- Broker readiness / credential diagnostics (sanitized outputs only)  
- Launcher health feeds  

**Existing consumers (EXISTING)**  
- MC `/health`, `/runtime`, `/heartbeat`, `/brokers`  
- Mobile Operational Health  
- 159A `runtime_health` / `broker_health`  

**Aggregation rules**  
1. Runtime STALE (>120s heartbeat policy) caps panel at RED/UNAVAILABLE.  
2. Any broker `FAIL_CLOSED` / not-ready degrades panel independently.  
3. Never copy credential diagnostics secrets into the brief.  

**Freshness requirements**  
Must reference canonical supervisor path
(`runtime/supervisor/css_runtime_supervisor_state.json`) and publisher
artifacts under `artifacts/`.

**Confidence calculations**  
Operational confidence derived from freshness coverage ratio
(fresh artifacts / required artifacts), not market confidence.

**Executive KPIs contributed**  
`uptime`, `runtime_health`, `broker_health`, `alert_count`.

**Advisory-only requirements**  
No restart/arm controls in panel payload.

**API contracts**  
Existing runtime/broker APIs; future panel embed in morning-briefings APIs.

**Storage**  
Panel only + provenance pointers to supervisor/artifacts (hashes).

**Mission Control / Mobile**  
Health strip + venue chips; deep-link to MC ops/broker consoles.

**Future AI**  
Overnight outage narrative from heartbeat gap timeline.

**NEW required**  
- Overnight incident timeline rollup (optional v1 can be empty with
  `UNAVAILABLE`)  
- Sanitizer ensuring no secret fields enter archive  

---

### Panel 3 — Market Intelligence

**Purpose**  
Overnight market summary + regime analysis for the morning open.

**Required fields**

| Field | Notes |
|---|---|
| `panel_id` | `market_intelligence` |
| `panel_status` | severity |
| `freshness` | label |
| `overnight_market_summary` | Structured summary object |
| `liquidity` / `volatility` / `spread` | When available |
| `regime_current` | Canonical regime label |
| `regime_transitions` | Overnight transition list |
| `regime_implications` | Advisory strategy notes only |
| `intel_highlights` | News/macro highlights (cited) |
| `unavailable_fields` | explicit |

**Existing producers (EXISTING)**  
- Regime: `engine/regime/regime_gate.py`, adapters, portfolio regime
  intelligence, regime learning/weighting modules  
- Partial market: launcher `market_summary`, `intel/*` adapters  
- MC market intelligence → `market_health`  

**Existing consumers (EXISTING)**  
- Opportunity intelligence, IIC context, MC market panels, 159A regime field  

**Aggregation rules**  
1. Regime from canonical gate only (no parallel gate).  
2. Overnight market rollup is fail-closed if intel/market evidence missing.  
3. Do not invent overnight moves.  

**Freshness requirements**  
Regime as-of timestamp within reporting window; intel envelopes labeled by age.

**Confidence calculations**  
Market confidence = blend of regime evidence quality + intel coverage; sparse
intel → lower confidence, not fabricated summary.

**Executive KPIs contributed**  
`market_health`.

**Advisory-only requirements**  
No trade directives from market narrative.

**API contracts**  
- Existing regime APIs  
- **NEW:** overnight market summary producer API (also proposed in 173A)  

**Storage**  
Panel embed; optional twin
`overnight_market_summary.json` inside the dated version folder.

**Mission Control / Mobile**  
Overnight blurb + regime chip; MC full panel.

**Future AI**  
Cited cross-asset overnight narrative.

**NEW required (major gap)**  
- **Overnight Market Summary producer** (productized rollup)  
- Overnight regime transition timeline packager  

---

### Panel 4 — Trading Intelligence

**Purpose**  
Morning book and opportunity posture — rankings and portfolio summary —
explicitly non-execution.

**Required fields**

| Field | Notes |
|---|---|
| `panel_id` | `trading_intelligence` |
| `panel_status` | severity |
| `freshness` | label |
| `ranked_opportunities` | Top N advisory opportunities |
| `selected_opportunities` | Shadow selections if any |
| `execution_action` | Locked `NO_EXECUTION` |
| `portfolio_summary` | Exposure/cash/equity/health fields |
| `portfolio_health` | Status |
| `concentration_flags` | When present |
| `capital_posture` | Available/allocated/reserved when present |
| `unavailable_fields` | explicit |

**Existing producers (EXISTING)**  
- CAIE: opportunity proposal/scoring/optimizer/shadow/runtime bridge  
- OI / trading ranking engines  
- IIC opportunity ranking  
- Portfolio: frontend `portfolio_summary`, runtime portfolio state builders,
  portfolio intelligence / decision orchestrator  

**Existing consumers (EXISTING)**  
- MC opportunity ranking / portfolio command (MC-007A)  
- 159A top opportunities  
- Mobile opportunities / PnL cards  

**Aggregation rules**  
1. Opportunities are advisory/shadow only; `execution_action=NO_EXECUTION`.  
2. Portfolio fields copied from validated runtime portfolio artifacts.  
3. Rank freeze at generation time for archive compare.  

**Freshness requirements**  
Portfolio artifacts must not be STALE for FINAL; opportunities may be AGING
with label if ranking engines lack overnight cycles.

**Confidence calculations**  
Trading confidence = min(opportunity confidence, portfolio evidence confidence).

**Executive KPIs contributed**  
`portfolio_health`, `trade_quality` / `execution_quality` when available.

**Advisory-only requirements**  
Forbid order-intent fields in archived JSON.

**API contracts**  
Existing OI/CAIE/portfolio APIs; panel embed in morning-briefings.

**Storage**  
Panel embed; provenance to `artifacts/runtime_portfolio_state.json` etc.

**Mission Control / Mobile**  
Rank table (MC) / top 3 (mobile); portfolio health strip.

**Future AI**  
Opportunity drift vs prior report version/date.

**NEW required**  
- Morning rank-freeze serializer into brief  
- Diff helpers for compare API  

---

### Panel 5 — Learning

**Purpose**  
What CSS learned recently/overnight and bounded AI insights.

**Required fields**

| Field | Notes |
|---|---|
| `panel_id` | `learning` |
| `panel_status` | severity |
| `freshness` | label |
| `learning_summary` | trade_count, optimality_rate, top_strategy, missed opportunities, etc. |
| `factor_or_regime_deltas` | Compact learning deltas |
| `ai_insights` | Bounded insight list with `citations[]` |
| `insight_policy` | `citation_required=true` |
| `unavailable_fields` | explicit |

**Existing producers (EXISTING)**  
- `backend/analytics/autonomous_learning_controller.py`  
- `backend/learning/*` (Phase 139A set)  
- Explainability / intelligence narrative helpers  
- Frontend `_ai_market_narrative` / intelligence cards  
- MC explanation projection  

**Existing consumers (EXISTING)**  
- Mobile Learning & Optimization  
- MC performance attribution  
- Learning GET APIs  

**Aggregation rules**  
1. Learning deltas prefer prior FINAL brief as baseline when present.  
2. AI insights without citations are dropped (fail closed for that insight).  
3. No unconstrained chat payload in v1.  

**Freshness requirements**  
Learning may be AGING without blocking FINAL if labeled; fabricated insights
never allowed.

**Confidence calculations**  
Learning confidence from sample size / reliability modules; insights inherit
citation completeness score.

**Executive KPIs contributed**  
Indirect via quality metrics; does not invent readiness.

**Advisory-only requirements**  
Insights cannot authorize trades or change weights.

**API contracts**  
Existing learning APIs; **NEW** bounded morning AI insights assembler.

**Storage**  
Panel embed only (no raw model chain-of-thought dumps).

**Mission Control / Mobile**  
Learning delta + 1–3 insights (mobile).

**Future AI**  
RAG over prior FINAL briefs only; midday/close narrative layers.

**NEW required**  
- Citation-enforcing AI insights assembler  
- Prior-brief delta calculator  

---

## Existing Producer Mapping (Summary Matrix)

| Capability | Status | Primary paths |
|---|---|---|
| Executive decision aggregation | EXISTING | `executive_decision_brief.py`, recommendations, formatter |
| Morning text stub | EXISTING | `briefings.py` (`MORNING`) |
| Runtime health / freshness | EXISTING | supervisor, freshness manager, health aggregator |
| Broker operational status | EXISTING | `broker_operational_status.py` (155C) |
| Regime gate / regime intel | EXISTING | `regime_gate.py`, portfolio/learning regime modules |
| Opportunities / CAIE / OI | EXISTING | allocation + analytics + trading ranking |
| Portfolio summary / runtime portfolio | EXISTING | frontend contract + portfolio builders + artifacts |
| Committees / votes | EXISTING | portfolio risk committee + Phase 167 IIC |
| Confidence frameworks | EXISTING | decision confidence + calibration (+ others) |
| Learning summaries | EXISTING | autonomous learning + `backend/learning/*` |
| Executive KPIs (MC) | EXISTING | `system_metrics.build_executive_kpi_board` |
| Explainability | EXISTING | explainability engines / MC explanation |
| Reporting FS archive (event-id) | EXISTING | `report_archive.py`, `report_history.py` |
| Dated morning archive | **NEW** | not implemented |
| Five-panel `ExecutiveMorningBrief` assembler | **NEW** | not implemented |
| Overnight market rollup producer | **NEW** | gap (launcher stubs + intel only) |
| Versioned immutable brief store | **NEW** | not implemented |
| Morning brief manifest index | **NEW** | not implemented (unlike flat `report_history.json`) |
| PDF generator | **NEW / DEFER** | no in-repo PDF generator found |
| Compare / missing-dates services | **NEW** | not implemented |

---

## Missing Producer / Gap Analysis

| Gap | Impact | Proposed owner (future) |
|---|---|---|
| `ExecutiveMorningBriefAssembler` | Blocks all panels packaging | 173C |
| `MorningBriefArchiveStore` | Blocks durable date retrieval | 173C |
| Overnight Market Summary producer | Market panel weak | 173C/173E |
| Secret sanitizer for broker fields | Security gate for FINAL | 173C |
| Version/immutability controller | Prevents silent overwrite | 173C |
| Manifest writer (atomic) | Fast retrieval | 173C |
| Compare/diff engine | MC/mobile “what changed” | 173C/173F |
| PDF export | Optional; MD+JSON sufficient for v1 | Later |
| SQLite index | Optional acceleration only | Later if needed |

---

## Aggregation and Scoring Rules

### Overall status

```text
overall_status = worst(Operational Health, Broker subset, Risk/Committee severity)
AMBER allowed when non-critical sections UNAVAILABLE but core health FRESH
RED if runtime STALE or broker fail-closed or risk veto critical
UNAVAILABLE if validation cannot establish core evidence set
```

### Panel confidence (generic)

```text
if required sources missing -> confidence = null, confidence_status = DATA_UNAVAILABLE
else confidence = clamp(0..1, weighted_mean(source_confidences) * freshness_factor)
freshness_factor: FRESH=1.0, AGING=0.85, STALE=0.0 (forces unavailable)
```

### Finalization gate

FINAL allowed only when:

1. `validation.status == PASS`  
2. Safety locks present and correct  
3. Secret scan pass  
4. Core evidence set present: runtime freshness known, broker status known
   (even if RED), portfolio summary known or explicitly UNAVAILABLE labeled,
   schema_version valid  
5. Overnight market may be UNAVAILABLE without blocking FINAL **only if**
   explicitly labeled and overall status degraded accordingly (policy flag
   `allow_final_with_market_unavailable=true` default **false** for v1 —
   recommend **require market panel either FRESH/AGING or explicit
   operator-approved waiver field in DRAFT**, else fail closed)

**v1 recommendation:** Market panel UNAVAILABLE blocks FINAL (fail closed),
matching “never synthesize market data.”

---

## Freshness and Fail-Closed Behavior

| Label | Meaning | Archive implication |
|---|---|---|
| `FRESH` | Within policy window | Eligible for FINAL |
| `AGING` | Acceptable but aging | Eligible with badges |
| `STALE` | Beyond threshold (e.g. heartbeat >120s) | Blocks FINAL for core panels |
| `UNAVAILABLE` | Missing/unreadable | Section labeled; may fail validation |

Rules:

1. Never synthesize unavailable market/broker/portfolio/runtime data.  
2. Failed generations store under `FAILED` lifecycle with validation errors.  
3. Do not finalize unless validation passes.  
4. Mission Control/mobile must show freshness/status badges from envelope.

---

## Dated Archive Architecture

### Recommended canonical root

**Proposed canonical storage path:**

```text
artifacts/runtime_reports/morning_briefings/
```

**Rationale vs alternatives**

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| `runtime_reports/morning_briefings/` (repo root) | Matches user sketch; some ops docs use `runtime_reports/` | Splits product artifacts away from dominant `artifacts/` root; gitignore/ops inconsistency risk | Acceptable alternate |
| `artifacts/briefings/` (173A) | Already proposed | Lacks YYYY/MM nesting + version folders; weaker ops naming | Superseded |
| `artifacts/reports/` (existing event archive) | Existing reporter | Flat `report_{event_id}` — poor date browse UX | Reuse patterns, not location |
| SQLite as SoT | Queryable | Not how CSS stores executive artifacts; mutable-DB risk for “immutable” reports | Reject as SoT |
| **`artifacts/runtime_reports/morning_briefings/`** | Under `artifacts/` (gitignored product surface), explicit `runtime_reports` name, date-browse hierarchy | Slightly longer paths | **Recommended** |

### Folder / file naming standards

```text
artifacts/runtime_reports/morning_briefings/
  manifest.json
  latest.json                          # pointer to current latest FINAL (or UNAVAILABLE)
  YYYY/
    MM/
      YYYY-MM-DD/
        current.json                   # pointer to current version for that date
        v001/
          executive_morning_brief.json # required
          executive_morning_brief.md   # required for FINAL
          executive_morning_brief.pdf  # optional (deferred until PDF exporter exists)
          manifest.json                # version-local manifest
          validation.json              # MorningBriefValidationResult
          provenance.json              # optional expanded provenance
        v002/
          ...
        failed/
          YYYYMMDDThhmmssZ_FAILED/
            executive_morning_brief.json  # partial/fail-closed draft
            validation.json
            manifest.json
```

**Canonical date key:** `YYYY-MM-DD` (directory name and `report_date` field).

**Version key:** `v` + zero-padded integer `v001`, `v002`, …

**Pointer files** (`latest.json`, `current.json`) contain only references:

```json
{
  "report_date": "2026-07-18",
  "version": "v002",
  "report_status": "FINAL",
  "path": "2026/07/2026-07-18/v002/executive_morning_brief.json",
  "state_hash": "...",
  "generated_at_utc": "...",
  "advisory_only": true
}
```

### Record metadata (every archive record)

Required on every stored attempt (FINAL and FAILED):

- `report_date`  
- `generated_at_utc`  
- `reporting_window_start_utc`  
- `reporting_window_end_utc`  
- `runtime_id`  
- `supervisor_id`  
- `state_hash`  
- `schema_version`  
- `data_freshness_status`  
- `report_status`  
- `advisory_only`  
- `source_provenance`  
- `validation_status`  

Plus version metadata:

- `version`  
- `created_by` (module/service id)  
- `created_reason` (`scheduled_cutover` \| `manual_regen` \| `repair` \| …)  
- `supersedes_version` (nullable)  
- `is_current_for_date`  

---

## Report Lifecycle and Versioning

### Lifecycle states

| State | Meaning | Mutable? |
|---|---|---|
| `DRAFT` | Generation in progress / not validated | Yes (working area only) |
| `VALIDATING` | Validation running | Yes |
| `FINAL` | Validation passed; published current or historical | **Immutable** |
| `FAILED` | Validation or generation failed | Immutable failure record |
| `SUPERSEDED` | Was FINAL current; replaced by newer FINAL for same date | Immutable |

### State transitions

```text
DRAFT → VALIDATING → FINAL
DRAFT → VALIDATING → FAILED
FINAL → SUPERSEDED   (only when a newer FINAL for same report_date becomes current)
```

No transition from `FAILED` to `FINAL` in place — always new version attempt.

### Versioning behavior (same date regeneration)

1. **Never silently overwrite** a `FINAL` directory.  
2. Create `vNNN+1/` with full new payload.  
3. Preserve prior `vNNN/` untouched.  
4. On validation PASS: mark new version `FINAL` + `is_current_for_date=true`;
   prior current becomes `SUPERSEDED` (status field update **only via new
   sidecar status file or manifest index**, not by rewriting finalized JSON
   body — see immutability rule below).  
5. Retain who/what/when/reason on the new version manifest.  

**Immutability clarification:** The `executive_morning_brief.json` bytes of a
FINAL version are never modified. Supersession is recorded in:

- version-local `manifest.json` written once at finalization, and  
- root `manifest.json` / `current.json` pointers updated atomically.

If a FINAL brief’s envelope needs `report_status=SUPERSEDED` visible inside
JSON, store that in the **index/pointer layer**, not by mutating the finalized
payload (preferred). Alternate acceptable approach: write a tiny immutable
`status.json` sibling at supersession time without touching the brief JSON.

### Concurrent generation

Use temp directories + `os.replace` atomic publish (CSS precedent in several
repositories). Lock file optional: `YYYY-MM-DD/.lock` during VALIDATING.

---

## Manifest / Index Contract

Root file:

`artifacts/runtime_reports/morning_briefings/manifest.json`

Minimum fields:

| Field | Type | Purpose |
|---|---|---|
| `archive_schema_version` | string | e.g. `css.morning_brief_manifest.v1` |
| `archive_last_updated_at` | string | ISO UTC |
| `available_dates` | string[] | Sorted `YYYY-MM-DD` with ≥1 FINAL or FAILED |
| `latest_report_date` | string \| null | Latest date with current FINAL |
| `report_count` | int | Count of current FINAL dates |
| `failed_attempt_count` | int | Optional ops metric |
| `missing_expected_dates` | string[] | Expected business days without FINAL |
| `current_version_by_date` | object | map `YYYY-MM-DD → version` |
| `status_by_date` | object | map date → `FINAL`/`FAILED`/mixed |
| `paths_by_date` | object | map date → relative path to current brief |
| `expected_calendar_policy` | object | business-day rules used for missing detection |

Version-local `manifest.json` includes paths to json/md/pdf, hashes of files,
validation status, and version metadata.

**Indexing expectation:** Manifest is the primary index. No DB required.
Optional future SQLite table mirroring manifest rows for range queries.

---

## Retrieval API Contracts (Conceptual)

All GET-only. Advisory-only. No execution side effects.

| API | Behavior |
|---|---|
| `GET /mission-control/api/morning-briefings` | List summaries (date, status, version, freshness, overall_status). Query: `from`, `to`, `include_failed` |
| `GET /mission-control/api/morning-briefings/latest` | Current latest FINAL pointer payload (or fail-closed empty) |
| `GET /mission-control/api/morning-briefings/{report_date}` | Current version for date (`YYYY-MM-DD`) |
| `GET /mission-control/api/morning-briefings/{report_date}/versions` | All versions + statuses for date |
| `GET /mission-control/api/morning-briefings/compare?from=YYYY-MM-DD&to=YYYY-MM-DD` | Structural diff of two current FINALs |

Additional recommended (non-breaking):

| API | Behavior |
|---|---|
| `GET /mission-control/api/morning-briefings/{report_date}/v/{version}` | Exact version fetch |
| `GET /api/v1/morning-briefings/...` | Launcher/mobile-facing mirrors of the same contracts |

Error model:

- Unknown date → 404 with `DATA UNAVAILABLE`  
- Only FAILED exists → 409 or 200 with `report_status=FAILED` (prefer **200 +
  explicit status** for MC badges)  
- Malformed date → 400  

---

## Mission Control Historical-Report Experience

Required UX capabilities:

1. **Current morning briefing landing page** (default = latest FINAL)  
2. **Historical report browser** (list from manifest)  
3. **Calendar / date selector** (`YYYY-MM-DD`)  
4. **Latest report shortcut**  
5. **Previous / next report navigation** (by available FINAL dates)  
6. **Compare reports** (from/to)  
7. **Freshness / status badge** (`FINAL`/`FAILED`/`STALE`/etc.)  
8. **Version selector** per date  
9. **Persistent advisory-only banner** and locked safety flags  

MC projections must include standard metadata: `source`, `provenance`,
`generated_at`, `freshness`, `runtime_id`, `state_hash`, safety locks.

---

## Mobile Historical-Report Experience

1. **Latest report** compact five-panel digest  
2. **Report-by-date retrieval**  
3. **Compact historical list** (date + overall_status + freshness)  
4. **Key executive changes since prior report** (`diff_vs_previous` summary)  
5. **Offline cached access** to previously opened FINAL reports (device-local
   cache of JSON only; no secret material; cache clearly stamped advisory-only)

Mobile does not expose version surgery — read current + optional version list.

---

## Retention, Security, and Governance

| Rule | Policy |
|---|---|
| Retention | Indefinite unless explicit future governance authorizes archival/deletion |
| Secrets | Forbidden: credentials, tokens, private keys, protected broker fields |
| Provenance | Reference source artifacts by path + hash; do not dump raw broker payloads |
| Immutability | FINAL payloads immutable |
| Authority | Advisory-only forever; cannot grant execution |
| PDF | Optional export; must apply same sanitizer |
| Access | Subject to existing RBAC / Mission Control governance |

Secret scan is a **hard FINAL gate**.

---

## Failure and Recovery Behavior

1. If required evidence is stale/missing/malformed/inconsistent → fail closed.  
2. Persist FAILED attempt under `failed/YYYYMMDDThhmmssZ_FAILED/`.  
3. Update root manifest `missing_expected_dates` / failure counters.  
4. Do not invent section data; label `UNAVAILABLE`.  
5. Do not finalize.  
6. Recovery = new version attempt after evidence restored (`created_reason=repair`).  
7. Latest pointer unchanged on FAILED (remains prior good FINAL if any).  

---

## Recommended Storage Option (Decision)

### Comparison

| Approach | Fit to CSS | Maintainability | Immutability | Query |
|---|---|---|---|---|
| Filesystem JSON/MD/PDF archive + manifest | Excellent (matches `artifacts/`, dated pilots, reporting FS) | High | Excellent with version dirs + atomic replace | Good via manifest |
| SQLite index + FS payloads | Good secondary | Medium | Good if payloads FS | Excellent |
| Existing `artifacts/reports` event store alone | Weak date UX | High reuse | Medium | Weak |
| SQLite-only payloads | Poor fit | Medium | Weaker optics | Excellent |

### Recommendation

**Primary:** Filesystem JSON + Markdown archive under  
`artifacts/runtime_reports/morning_briefings/`  
with root `manifest.json` and per-date version folders.

**Secondary (optional later):** SQLite mirror index for date-range queries only.

**PDF:** Deferred until an exporter exists; schema reserves the filename.

**Atomic writes:** temp dir + `os.replace`; do not use naive overwrite helpers
for FINAL publish.

This is the **smallest maintainable solution** compatible with current CSS
architecture.

---

## Implementation Sequence for Future Phase 173C

1. Freeze `css.executive_morning_brief.v1` schema module (types only).  
2. Implement secret sanitizer + validation gate.  
3. Implement `MorningBriefArchiveStore` (write DRAFT/FAILED/FINAL, pointers,
   manifest).  
4. Implement `ExecutiveMorningBriefAssembler` wiring EXISTING producers into
   five panels.  
5. Implement overnight market summary **minimal** producer (or hard-fail market
   panel honestly).  
6. Expose Mission Control GET APIs (list/latest/date/versions/compare).  
7. Wire MC morning landing + historical browser (read-only).  
8. Wire mobile latest + history + diff summary.  
9. Add tests for immutability, no silent overwrite, fail-closed, sanitizer.  
10. Evidence pack + governance certification note.

173C remains the first implementation phase; 173B stays design-only.

---

## Acceptance Criteria (for a future implementation phase)

- [ ] `ExecutiveMorningBrief` validates against `css.executive_morning_brief.v1`  
- [ ] Five panels present with explicit unavailable labeling when needed  
- [ ] Reports stored under canonical dated hierarchy by `YYYY-MM-DD`  
- [ ] Required metadata fields present on every record  
- [ ] FINAL reports immutable; regeneration creates new version  
- [ ] Manifest supports list, latest, missing dates, current version map  
- [ ] Retrieval APIs match contracts  
- [ ] MC historical UX capabilities available  
- [ ] Mobile latest/history/diff/offline-cache behavior available  
- [ ] No secrets in stored reports  
- [ ] Fail-closed FAILED artifacts retained separately  
- [ ] Advisory-only locks present on all outputs  
- [ ] No production execution authority changes  

---

## Known Limitations

1. **No PDF generator in-repo today** — PDF path is reserved, not required for v1.  
2. **Overnight Market Summary is a real producer gap** — Market panel will be
   weak until implemented.  
3. **Committee history largely in-memory (Phase 167)** — overnight committee
   auditability may be incomplete until snapshots are persisted into briefs.  
4. **173A latest path differs** — consumers must adopt 173B paths; treat 173A
   paths as superseded proposals.  
5. **Business-day calendar for `missing_expected_dates`** needs an explicit
   policy (weekends/holidays) — default proposal: Mon–Fri operator calendar,
   configurable later.  
6. **Timezone for `report_date`** must be pinned (proposal: operator-configured
   reporting TZ; store UTC window bounds always).  
7. **Compare API** needs a stable field-diff schema; v1 may support only
   KPI + status + top-N opportunity id diffs.  
8. **Offline mobile cache** is best-effort and device-local — not a substitute
   for server archive.  

---

## Open Questions

1. Confirm operator timezone source of truth for `report_date`.  
2. Confirm whether market panel UNAVAILABLE must block FINAL (recommended: yes).  
3. Confirm holiday calendar source for missing-date detection.  
4. Confirm whether `SUPERSEDED` status is index-only or also sibling `status.json`.  
5. Confirm PDF priority vs MD-only for first production cut.  
6. Confirm whether midday/close briefs share the same root with `briefing_type`
   discrimination in v1 or wait for a later phase.

---

## Governance Statement

Phase 173B is architecture-only. It defines the canonical Executive
Intelligence Data Layer, the `ExecutiveMorningBrief` five-panel contract, and
the durable dated morning briefing archive — including lifecycle, versioning,
manifest, APIs, MC/mobile historical experience, retention, and fail-closed
behavior.

**Deliverable:**

- `docs/governance/PHASE_173B_EXECUTIVE_INTELLIGENCE_DATA_LAYER.md`

**Not delivered:** production code, tests, runtime artifacts, databases,
commits, pushes.
