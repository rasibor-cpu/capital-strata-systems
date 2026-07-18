# PHASE 173D — Executive Intelligence Platform Final Architecture Freeze

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Phase type:** Architecture only — FINAL before implementation  
**Status:** DESIGN COMPLETE — Architecture Freeze v1.0 companion issued  
**Date:** 2026-07-18  
**Upstream:**  
- `PHASE_173A_EXECUTIVE_MORNING_BRIEFING_ARCHITECTURE.md`  
- `PHASE_173B_EXECUTIVE_INTELLIGENCE_DATA_LAYER.md`  
- `PHASE_173C_EXECUTIVE_INTELLIGENCE_ARCHIVE.md`  
**Companion freeze:** `CSS_EXECUTIVE_INTELLIGENCE_ARCHITECTURE_FREEZE_V1.md`  

---

## Executive Summary

Phase 173D consolidates 173A–173C into one **canonical enterprise architecture**
for the CSS Executive Intelligence Platform (EIP):

| Layer | Role |
|---|---|
| **Product** | Morning Intelligence Briefing as primary morning landing |
| **Data** | Five-panel `ExecutiveMorningBrief` + dated immutable archive |
| **Memory** | Executive Intelligence Archive (identity, lineage, compare, trends, replay) |
| **Ontology** | Shared enterprise vocabulary for markets, regimes, opportunities, etc. |
| **Governance** | Advisory-only, fail-closed, secret-free, indefinite retention |

This phase does **not** implement code. It freezes the model, resolves
conflicts among 173A–173C, defines ontology/KPIs, sketches a future knowledge
graph, extends historical intelligence and lineage, specifies the executive
experience, and sequences implementation as Phases **174–179**.

### Safety locks (platform-wide, immutable)

| Flag | Locked value |
|---|---|
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `live_trading_blocked` | `true` |
| `broker_execution_armed` | `false` |

### Explicit non-delivery

No production code · no tests · no runtime artifacts · no commits · no pushes.

---

# SECTION 1 — Architecture Consolidation

## 1.1 Source roles

| Phase | Contribution | Status after 173D |
|---|---|---|
| **173A** | Morning product intent, 13 section catalog, MC/mobile landing vision | **Absorbed** — sections map to 5 panels; product UX retained |
| **173B** | `ExecutiveMorningBrief`, five panels, dated versioned FS archive, basic APIs | **Canonical data model + archive** |
| **173C** | EIA identity/lineage/compare/trends/replay/search | **Canonical historical memory plane** |
| **173D** | Consolidation, ontology, KPIs, freeze, roadmap 174–179 | **Authoritative platform architecture** |

## 1.2 Duplicated concepts (merged)

| Duplicate | Canonical resolution |
|---|---|
| MIB vs ExecutiveMorningBrief | **One product name:** Morning Intelligence Briefing (MIB). **One payload:** `ExecutiveMorningBrief` |
| 13 sections vs 5 panels | **5 panels + envelope** are canonical; 13 sections are panel subtopics / UI outline only |
| `css.morning_intelligence_briefing.v1` vs `css.executive_morning_brief.v1` | **Canonical contract:** `css.executive_morning_brief.v1` |
| `artifacts/briefings/` vs `artifacts/runtime_reports/morning_briefings/` | **Canonical root:** `artifacts/runtime_reports/morning_briefings/` |
| Retention ≥90d (173A) vs indefinite (173B/C) | **Indefinite** unless governance authorizes deletion |
| MC APIs `/morning-briefing` vs `/morning-briefings` vs `/eia/*` | **Unified API surface** (see §7 / Freeze) |
| Freshness `MISSING` vs `UNAVAILABLE` | **Canonical freshness:** `FRESH` \| `AGING` \| `STALE` \| `UNAVAILABLE` |
| Date-only identity vs UUID `report_id` | **Both:** `report_date` for browse; `report_id` for bookmarks/replay/audit |

## 1.3 Conflicting terminology (resolved)

| Conflict | Resolution |
|---|---|
| “Overnight” = process lifecycle (172A) vs market rollup | **Disambiguate:** `overnight_runtime` (172A) vs `overnight_market` (MIB Market panel) |
| Recommendation verbs vs MC “no BUY/SELL/EXECUTE” | Executive recommendation **types** are advisory postures; they **do not** authorize orders. `Enter`/`Close` mean “advisory posture toward entry/exit,” never broker instructions |
| Executive regime labels vs engine `ALL_REGIMES` | **Two layers:** Engine gate remains canonical for trading filters. Executive ontology regimes are **presentation/aggregation labels** with an explicit mapping table (§2) |
| GREEN/AMBER/RED vs Healthy/Degraded runtime vocabulary | Status traffic lights for UI; runtime enum for operational state — both allowed, mapped (§2) |
| `children` vs `derived_reports` | Canonical lineage field: **`children`** (alias `derived_reports` deprecated in docs) |

## 1.4 Inconsistent data contracts (normalized)

| Topic | Canonical decision |
|---|---|
| Brief schema | `schema_version = "css.executive_morning_brief.v1"` |
| Archive control plane | `archive_version = "css.executive_intelligence_archive.v1"` |
| Platform freeze id | `css.executive_intelligence_platform.v1` |
| Required identity | 173C `EiaReportIdentity` fields **plus** 173B envelope fields on every FINAL |
| FINAL gate | Market panel must be FRESH/AGING or FINAL blocked (173B v1 rule) |
| PDF | Optional reserved filename; **not** required for v1 acceptance |
| SQLite | Optional search/trend index only; **never** source of truth |

## 1.5 Simplification opportunities

1. Single assembler produces one brief; EIA indexes it — no second “MIB document.”  
2. One MC landing route consuming latest FINAL.  
3. Compare + Executive Changes share one diff engine.  
4. Search docs generated at FINAL time, not a parallel report store.  
5. Postpone Knowledge Graph and PDF to post-179.

## 1.6 Canonical model (one picture)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Mission Control / Mobile  (Executive Experience)                      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ GET-only · advisory-only
┌───────────────────────────────▼──────────────────────────────────────┐
│ Executive Intelligence Platform APIs                                  │
│ /mission-control/api/morning-briefings/*                              │
│ /mission-control/api/eia/*                                            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ Brief         │    │ Dated Archive    │    │ EIA Control Plane   │
│ Assembler     │───▶│ morning_briefings│◀──▶│ identity/lineage/   │
│ (5 panels)    │    │ YYYY/MM/DD/vNNN  │    │ trends/search/audit │
└───────┬───────┘    └──────────────────┘    └─────────────────────┘
        │ reads only
        ▼
 Existing CSS producers (159A, 155C, regime gate, CAIE, committees, learning…)
```

**Canonical payload:** `ExecutiveMorningBrief`  
**Canonical memory:** Executive Intelligence Archive over immutable FINALs  
**Canonical product:** Morning Intelligence Briefing landing page  

---

# SECTION 2 — CSS Executive Ontology

Ontology terms are **enterprise vocabulary** for executive surfaces. They do not
replace engine/broker authority enums unless an explicit mapping says so.

## 2.1 Markets

| Term | Meaning |
|---|---|
| `FX` | Foreign exchange spot/forward/NDF advisory universe |
| `Crypto` | Digital asset venues/instruments (e.g. Coinbase lineage) |
| `Futures` | Exchange-traded futures |
| `Options` | Optionality / income option strategies |
| `Equities` | Cash equities / equity-like beta |
| `Fixed Income` | Rates/credit instruments |
| `Commodities` | Commodity futures/spot proxies |

A brief may reference multiple markets; each opportunity carries `market` tags.

## 2.2 Market regimes (executive)

| Executive label | Meaning |
|---|---|
| `Risk-On` | Risk appetite elevated; broader participation favored |
| `Risk-Off` | Defensive posture; risk reduction favored |
| `Trending` | Directional persistence dominates |
| `Mean Reversion` | Reversion-to-mean dynamics dominate |
| `Volatile` | Elevated realized/implied volatility regime |
| `Quiet` | Low volatility / compressed ranges |
| `Liquidity Stress` | Liquidity impaired; spreads/impact elevated |
| `Event Driven` | Discrete catalysts dominate path |
| `Transitional` | Unstable between regimes; elevated uncertainty |

### Mapping to engine canonical regimes (non-destructive)

Engine (`engine/regime/regime_state.py`) remains authority for gate logic:

| Engine label | Typical executive mapping |
|---|---|
| `TREND_UP` / `TREND_DOWN` | `Trending` (+ Risk-On/Off contextual overlay when available) |
| `RANGE` | `Mean Reversion` or `Quiet` (vol-conditioned) |
| `HIGH_VOLATILITY` | `Volatile` (may co-label `Liquidity Stress`) |
| `LOW_VOLATILITY` | `Quiet` |

Executive labels may be multi-tag. **Gate decisions always use engine enums.**

## 2.3 Opportunity

Canonical opportunity fields:

| Field | Meaning |
|---|---|
| `confidence` | Belief quality in [0,1] with band (§2.8) |
| `expected_edge` | Expected advisory edge (normalized units defined by producer) |
| `expected_duration` | Expected holding/relevance horizon |
| `catalyst` | Why now (event/regime/signal) |
| `expiry` | When the opportunity thesis expires |
| `capital_required` | Advisory capital need (not an order size instruction) |
| `strategy_class` | Strategy family/class tag |

Always paired with `execution_action = NO_EXECUTION` in archived trading panels.

## 2.4 Recommendations (canonical types)

| Type | Meaning (advisory posture only) |
|---|---|
| `Monitor` | Watch actively; no posture change |
| `Observe` | Passive awareness; lower urgency than Monitor |
| `Prepare` | Ready playbooks/limits review; still no execution |
| `Enter` | Advisory posture favors opening exposure **if** later armed elsewhere |
| `Scale In` | Advisory posture favors increasing an existing thesis gradually |
| `Scale Out` | Advisory posture favors reducing gradually |
| `Reduce Risk` | Risk reduction posture |
| `Increase Exposure` | Risk-on posture within policy (still non-execution here) |
| `Hedge` | Hedging posture recommended for review |
| `Avoid` | Do not pursue |
| `Close` | Advisory posture favors exiting a thesis |
| `Review` | Human/committee review required |

**Hard rule:** These types never call brokers and never set `execution_allowed=true`.

## 2.5 Learning

| Term | Meaning |
|---|---|
| `Observation` | Recorded fact from runtime/market/portfolio |
| `Inference` | Derived conclusion from observations |
| `Hypothesis` | Testable claim not yet validated |
| `Validated Learning` | Hypothesis confirmed by evidence policy |
| `Rejected Hypothesis` | Hypothesis invalidated; retained for memory |

## 2.6 Runtime

| Term | Meaning |
|---|---|
| `Healthy` | Heartbeat/artifacts within policy; no critical faults |
| `Recovering` | Returning to healthy after degradation |
| `Degraded` | Impaired but operating |
| `Stale` | Freshness beyond STALE threshold (e.g. heartbeat >120s) |
| `Failed` | Runtime evidence failed closed / unavailable |

UI traffic lights map: Healthy→GREEN, Recovering/Degraded→AMBER, Stale/Failed→RED.

## 2.7 Broker

| Term | Meaning |
|---|---|
| `Healthy` | Operational status OK (155C sanitized) |
| `Latent` | Responding slowly / elevated latency |
| `Degraded` | Partial capability / warnings |
| `Offline` | Unreachable / not ready |
| `Advisory Only` | Read-only / intentionally non-armed posture |

## 2.8 Risk levels

`Critical` · `High` · `Medium` · `Low` · `Informational`

## 2.9 Confidence bands

| Band | Range | Meaning |
|---|---|---|
| Exceptional | 95–100 | Extremely strong evidence |
| Very High | 90–94 | Strong, well-supported |
| High | 80–89 | Good evidence |
| Moderate | 70–79 | Usable with caution |
| Low | 60–69 | Weak; prefer Monitor/Review |
| Very Low | <60 | Insufficient for assertive posture |

Scores stored as 0–1 floats; bands applied for display.

---

# SECTION 3 — Executive KPIs

All KPIs are advisory metrics on the brief envelope / trend board. Missing inputs
→ `UNAVAILABLE` (never synthesized).

Refresh default: **at morning cutover** + live mirror while viewing (~MC 5s hint)
unless noted.

### 3.1 Runtime Health

| | |
|---|---|
| **Definition** | Aggregate operational fitness of CSS runtime |
| **Formula** | Score from freshness coverage × heartbeat policy × critical alert penalty (exact weights in implementation; fail-closed if supervisor missing) |
| **Inputs** | Supervisor state, artifact freshness, runtime health aggregator, alerts |
| **Refresh** | Heartbeat ~10s upstream; KPI snapshot at brief generation |
| **Producer** | Runtime health aggregator + supervisor |
| **Consumer** | MIB Operational Health; MC KPI board; EIA trends |

### 3.2 Market Readiness

| | |
|---|---|
| **Definition** | Whether market/regime evidence is adequate for morning decision posture |
| **Formula** | Function of overnight market freshness + regime evidence quality |
| **Inputs** | Overnight market summary, regime gate/intel |
| **Refresh** | Cutover |
| **Producer** | Market panel assembler (overnight producer + regime) |
| **Consumer** | Market Intelligence panel; FINAL gate |

### 3.3 Opportunity Density

| | |
|---|---|
| **Definition** | Quantity/quality concentration of advisory opportunities |
| **Formula** | e.g. count(top-N) × mean(opportunity confidence) / normalization |
| **Inputs** | Ranked opportunities (CAIE/OI) |
| **Refresh** | Cutover / cycle freeze |
| **Producer** | Trading Intelligence panel |
| **Consumer** | MIB; trends; compare |

### 3.4 Decision Quality

| | |
|---|---|
| **Definition** | Quality of advisory decision posture (confidence × committee coherence × warning load) |
| **Formula** | Composite of decision confidence, veto absence, warning severity |
| **Inputs** | Confidence frameworks, committee consensus, operational warnings |
| **Refresh** | Cutover |
| **Producer** | Executive Decision panel |
| **Consumer** | Landing hero; longitudinal accuracy later |

### 3.5 Learning Velocity

| | |
|---|---|
| **Definition** | Rate of validated learning progress vs prior window |
| **Formula** | Δ(validated learnings + reliability metrics) / window days |
| **Inputs** | Learning panel, prior FINALs |
| **Refresh** | Cutover; trend windows 7/30/90 |
| **Producer** | Learning panel + EIA trajectories |
| **Consumer** | Learning panel; Trend Explorer |

### 3.6 Capital Efficiency

| | |
|---|---|
| **Definition** | Advisory efficiency of capital posture vs opportunity set |
| **Formula** | Producer-defined efficiency score from allocation/portfolio fields when present |
| **Inputs** | Portfolio/capital posture, selected opportunities |
| **Refresh** | Cutover |
| **Producer** | Trading Intelligence / CAIE shadow |
| **Consumer** | KPI board; compare category Capital efficiency |

### 3.7 Risk Stability

| | |
|---|---|
| **Definition** | Stability of risk posture overnight/over window |
| **Formula** | Inverse of risk-level volatility + veto frequency penalty |
| **Inputs** | Risk health, committee vetoes, risk events |
| **Refresh** | Cutover; trends |
| **Producer** | Risk committee / Executive Decision |
| **Consumer** | KPI board; Risk compare |

### 3.8 Broker Reliability

| | |
|---|---|
| **Definition** | Multi-venue operational reliability |
| **Formula** | Mean venue health score − offline/degraded penalties |
| **Inputs** | 155C broker operational status (sanitized) |
| **Refresh** | Per refresh cycle + cutover snapshot |
| **Producer** | Broker operational status |
| **Consumer** | Operational Health; trends |

### 3.9 Strategy Strength

| | |
|---|---|
| **Definition** | Strength/leadership of active strategy classes |
| **Formula** | From learning/strategy leadership metrics when present |
| **Inputs** | Learning summary, strategy tags on opportunities |
| **Refresh** | Cutover |
| **Producer** | Learning / opportunity ranking |
| **Consumer** | Trends; Knowledge Graph later |

### 3.10 Market Confidence

| | |
|---|---|
| **Definition** | Confidence in market/regime interpretation |
| **Formula** | Regime evidence quality × intel coverage freshness factor |
| **Inputs** | Regime producers, overnight market |
| **Refresh** | Cutover |
| **Producer** | Market Intelligence panel |
| **Consumer** | KPI board; confidence trends |

### 3.11 Recommendation Quality

| | |
|---|---|
| **Definition** | Coherence and evidence strength of advisory recommendations |
| **Formula** | Citation completeness × confidence band × dedupe coherence |
| **Inputs** | Recommended actions, provenance, confidence |
| **Refresh** | Cutover |
| **Producer** | Executive recommendations merger |
| **Consumer** | Landing; longitudinal accuracy when outcomes exist |

**Note:** Existing MC board fields (`uptime`, `runtime_health`, `broker_health`,
`portfolio_health`, `risk_health`, `market_health`, `alert_count`,
`trade_quality`/`execution_quality`, `system_readiness`, `rc1_readiness`)
remain supported and map into the above family (aliases allowed in Freeze).

---

# SECTION 4 — Executive Knowledge Graph (Future)

## 4.1 Purpose

`ExecutiveKnowledgeGraph` (EKG) is a **future** query layer over EIA FINALs and
lineage — architecture only in 173D; **not** in 174–179 critical path.

## 4.2 Entities

`Market` · `Asset` · `Strategy` · `Broker` · `Report` · `Recommendation` ·
`RiskEvent` · `Learning` · `Committee`

## 4.3 Relationships (examples)

| Edge | Meaning |
|---|---|
| Report–CONTAINS→Recommendation | Actions in a FINAL |
| Recommendation–ABOUT→Asset/Market | Targeting |
| Strategy–PERFORMS_IN→Regime | Historical performance joins |
| Report–OBSERVED→RiskEvent | Risk annotations |
| Learning–VALIDATES→Hypothesis | Learning ontology |
| Report–SUPERSEDES→Report | Version lineage |
| Broker–STATUS_ON→Report | Broker snapshot membership |

## 4.4 Example questions

- “What strategy performed best during Risk-Off regimes?”  
- “Show all historical EURUSD recommendations.”  

Answered by graph queries over extracted nodes — never by mutating trading state.

## 4.5 Postponement

EKG implementation recommended **after Phase 179**, once search docs + lineage
indexes are stable.

---

# SECTION 5 — Historical Intelligence

Derived exclusively from archived FINAL `ExecutiveMorningBrief` records (+
optional outcome joins later).

| Capability | Derivation |
|---|---|
| **Historical trends** | `EiaTrendSeries` over KPI/confidence/regime metrics (173C) |
| **Seasonality** | Calendar overlays on trend points (dow/month effects) — derived |
| **Market memory** | Regime occupancy + overnight market summaries across dates |
| **Learning progression** | Learning panel trajectories + validated/rejected counts |
| **Strategy evolution** | Strategy leadership/tenure extracted from Trading/Learning panels |
| **Broker evolution** | Broker reliability series per venue |
| **Confidence evolution** | Decision/market confidence bands over windows |

Rules: recomputable; no synthesis of missing days (coverage gaps explicit);
advisory-only.

---

# SECTION 6 — Report Lineage (Extended)

Canonical lineage links on every indexed report:

| Link | Meaning |
|---|---|
| `previous` | Prior FINAL same briefing_type by date |
| `next` | Next FINAL by date |
| `parent` | Logical parent report |
| `children` | Derived children (compare packs, replay packs, narratives) |
| `superseded` / `superseded_by` | Version replacement chain |
| `replay_origin` | Original FINAL for a replay pack |
| `linked_market_events` | Annotation ids/tags from market/regime events |
| `linked_recommendations` | Stable recommendation fragment ids within brief |
| `linked_learning` | Learning observation/inference ids |

Lineage index remains rebuildable from identity index + dated folders.

---

# SECTION 7 — Executive Experience

## 7.1 Mission Control

| Surface | Role |
|---|---|
| **Landing Page** | Latest FINAL MIB (primary morning home) |
| **Morning Brief** | Five-panel full brief |
| **Timeline** | Year/month/week/day executive calendar |
| **Compare** | Baseline diffs across categories |
| **Replay** | Historical reconstruction watermark |
| **Search** | Multi-dimension EIA search |
| **Bookmarks / Favorites / Pinned** | `report_id` collections |
| **Trend Explorer** | Windowed KPI/ontology trends |
| **Historical Replay** | Deep replay view (same as Replay; named for IA clarity) |

Persistent advisory-only banner; freshness/status/integrity badges; version
selector.

## 7.2 Mobile

Recent · Historical list · Trends sparklines · Replay summary · Search ·
Bookmarks · Offline FINAL cache. Compact five-panel digest; no execution
controls.

## 7.3 Canonical API surface (frozen names)

```text
# Brief archive (173B core)
GET /mission-control/api/morning-briefings
GET /mission-control/api/morning-briefings/latest
GET /mission-control/api/morning-briefings/{report_date}
GET /mission-control/api/morning-briefings/{report_date}/versions
GET /mission-control/api/morning-briefings/compare?from=&to=

# EIA extensions (173C)
GET /mission-control/api/eia/compare
GET /mission-control/api/eia/trends
GET /mission-control/api/eia/calendar
GET /mission-control/api/eia/timeline/{report_date}
GET /mission-control/api/eia/replay/{report_id}
GET /mission-control/api/eia/search
GET /mission-control/api/eia/changes
```

Launcher mirrors under `/api/v1/...` allowed as read-only facades.

---

# SECTION 8 — Implementation Roadmap (174–179)

Effort: **S** <1 week · **M** 1–2 weeks · **L** 2–4 weeks (engineering-days
order-of-magnitude; adjust to team capacity).

### Phase 174 — Brief Assembler + Immutable Archive Store

| | |
|---|---|
| **Purpose** | Implement `ExecutiveMorningBrief` assembler, sanitizer, validation, versioned FS archive, manifest, latest/current pointers, basic MC/mobile GET latest+by-date |
| **Dependencies** | 173A–173D designs; existing producers |
| **Risk** | Medium — FINAL gate / secret scan correctness |
| **Effort** | L |
| **Validation** | Unit/integration: immutability, no silent overwrite, fail-closed, schema validation |
| **Acceptance** | FINAL written under canonical path; GET latest works; safety locks present; secrets absent |

### Phase 175 — Overnight Market Producer + Panel Completeness

| | |
|---|---|
| **Purpose** | Productize overnight market summary; complete Market panel; enforce market FINAL policy |
| **Dependencies** | 174 |
| **Risk** | Medium — intel adapter variability |
| **Effort** | M–L |
| **Validation** | Unavailable market blocks FINAL; no synthesized prints |
| **Acceptance** | Market panel FRESH/AGING on happy path; honest UNAVAILABLE otherwise |

### Phase 176 — EIA Identity, Lineage, Compare, Changes

| | |
|---|---|
| **Purpose** | `report_id` identity index, lineage graph, comparison engine, executive changes, MC browser/calendar |
| **Dependencies** | 174 (175 preferred) |
| **Risk** | Medium — calendar/business-day policy |
| **Effort** | L |
| **Validation** | Compare baselines; lineage previous/next; missing-date detection |
| **Acceptance** | Identity+lineage+compare+changes APIs meet Freeze contracts |

### Phase 177 — Trends + Search + Longitudinal Learning Tracks

| | |
|---|---|
| **Purpose** | Trend series/board, search_doc + search API, learning trajectories |
| **Dependencies** | 176 |
| **Risk** | Medium — search quality; optional SQLite |
| **Effort** | L |
| **Validation** | Window coverage gaps explicit; FTS optional |
| **Acceptance** | 7/30/90/365 trends; search dimensions v1; learning tracks readable |

### Phase 178 — Replay + Integrity Verifier + MC Trend/Replay UX

| | |
|---|---|
| **Purpose** | Replay packs, hash integrity verifier, Trend Explorer + Replay views |
| **Dependencies** | 176, 177 |
| **Risk** | Medium — degraded deep replay if artifacts rotated |
| **Effort** | M–L |
| **Validation** | Hash mismatch refuses authoritative replay; watermark present |
| **Acceptance** | Replay by id/date; integrity audit log events |

### Phase 179 — Mobile Polish + Bookmarks/Pins + Hardening

| | |
|---|---|
| **Purpose** | Mobile historical/replay/search/offline cache; bookmarks/favorites/pins; performance/RBAC hardening |
| **Dependencies** | 174–178 |
| **Risk** | Low–Medium |
| **Effort** | M |
| **Validation** | Offline cache advisory-only; no secrets; RBAC on bookmarks if server-side |
| **Acceptance** | Mobile parity for compact EIA; pins work; platform ready for ops use |

**Post-179 (not scheduled here):** Knowledge Graph, PDF exporter, midday/close
briefing types, outcome-linked recommendation accuracy.

---

# SECTION 9 — Architecture Freeze v1.0

See companion document:

**`docs/governance/CSS_EXECUTIVE_INTELLIGENCE_ARCHITECTURE_FREEZE_V1.md`**

That document is the binding list of stable decisions for implementation unless
explicitly superseded by governance.

---

# SECTION 10 — Enterprise Review

## 10.1 Remaining gaps

1. Overnight market producer not yet built  
2. Committee history persistence still weak overnight without brief snapshots  
3. Outcome linkage for recommendation accuracy incomplete  
4. Operator timezone + holiday calendar policy not pinned in code  
5. PDF exporter absent  
6. EKG not started (intentional)  

## 10.2 Future expansion points

Midday/close/weekly/monthly briefing types · EKG · AI narrative RAG over FINALs ·
seasonality packs · multi-tenant RBAC bookmark stores · PDF/email distribution  

## 10.3 Technical debt (watch)

- Parallel freshness vocabularies in older modules (`MISSING` vs `UNAVAILABLE`)  
- Fragmented confidence APIs  
- In-memory committee history  
- 173A path references in older notes (superseded)  
- Naive `save_json` overwrite helpers unfit for FINAL publish  

## 10.4 Recommended postponements

EKG · PDF · SQLite-as-primary · live-delta “replay” confusion · automatic weight
mutation from learning tracks · midday briefs until morning EIA is stable  

## 10.5 Architectural risks

| Risk | Mitigation |
|---|---|
| Silent overwrite | Version dirs + atomic publish + tests in 174 |
| Secret leakage | Sanitizer hard gate |
| False market certainty | Block FINAL on market UNAVAILABLE |
| Replay false authority | Watermark + no live re-gate |
| Ontology vs engine regime drift | Explicit mapping; gate uses engine enums |
| Scope creep into execution | Safety locks + API GET-only |

## 10.6 Implementation priorities

1. **174** archive+assembler (foundation)  
2. **175** market honesty  
3. **176** memory/compare  
4. **177** trends/search  
5. **178** replay/integrity  
6. **179** mobile/UX hardening  

---

## Governance Statement

Phase 173D freezes the CSS Executive Intelligence Platform architecture by
consolidating 173A–173C, defining ontology and KPIs, specifying experience and
roadmap 174–179, and issuing Architecture Freeze v1.0.

**Deliverables:**

- `docs/governance/PHASE_173D_EXECUTIVE_INTELLIGENCE_PLATFORM_ARCHITECTURE.md`  
- `docs/governance/CSS_EXECUTIVE_INTELLIGENCE_ARCHITECTURE_FREEZE_V1.md`  

**Not delivered:** production code, tests, runtime artifacts, commits, pushes.
