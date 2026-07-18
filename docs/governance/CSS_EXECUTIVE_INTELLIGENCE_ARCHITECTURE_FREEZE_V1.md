# CSS Executive Intelligence Architecture Freeze v1.0

**Document id:** `CSS_EXECUTIVE_INTELLIGENCE_ARCHITECTURE_FREEZE_V1`  
**Freeze version:** `1.0`  
**Platform contract:** `css.executive_intelligence_platform.v1`  
**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Effective date:** 2026-07-18  
**Status:** FROZEN — binding for implementation Phases 174–179 unless superseded by explicit governance  
**Authority docs:**  
- `PHASE_173A_EXECUTIVE_MORNING_BRIEFING_ARCHITECTURE.md` (product intent)  
- `PHASE_173B_EXECUTIVE_INTELLIGENCE_DATA_LAYER.md` (data/archive)  
- `PHASE_173C_EXECUTIVE_INTELLIGENCE_ARCHIVE.md` (historical memory)  
- `PHASE_173D_EXECUTIVE_INTELLIGENCE_PLATFORM_ARCHITECTURE.md` (consolidation)  

---

## 1. Freeze Purpose

This document lists every architectural decision that **must remain stable**
during Executive Intelligence Platform implementation. Changes require a
governance supersession note referencing a new freeze version (e.g. v1.1).

This freeze does **not** implement software.

---

## 2. Canonical Safety Locks (NON-NEGOTIABLE)

| Flag | Value |
|---|---|
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `live_trading_blocked` | `true` |
| `broker_execution_armed` | `false` |

Rules:

1. No Executive Intelligence API may arm brokers or place orders.  
2. Recommendation types never become broker instructions.  
3. Replay never re-gates against live markets to claim historical truth.  
4. Learning tracks never silently mutate production strategy weights.

---

## 3. Canonical Terminology

| Term | Canonical meaning |
|---|---|
| **EIP** | Executive Intelligence Platform |
| **MIB** | Morning Intelligence Briefing — primary morning landing product |
| **ExecutiveMorningBrief** | Canonical morning payload object |
| **EIA** | Executive Intelligence Archive — historical memory control plane |
| **Panel** | One of five brief panels |
| **FINAL** | Immutable validated report version |
| **report_id** | UUID identity of a specific versioned report artifact |
| **report_date** | `YYYY-MM-DD` browse key |
| **Engine regime** | Gate authority enums in `engine/regime` |
| **Executive regime** | Presentation ontology labels (mapped, non-authoritative for gates) |

Superseded terms (do not use in new code/docs):

- `css.morning_intelligence_briefing.v1` as active contract id  
- `artifacts/briefings/` as archive root  
- `derived_reports` as primary field name (use `children`)  
- Retention “90 days” as platform policy  

---

## 4. Canonical Ontology (Frozen Enumerations)

### Markets
`FX` · `Crypto` · `Futures` · `Options` · `Equities` · `Fixed Income` · `Commodities`

### Executive market regimes
`Risk-On` · `Risk-Off` · `Trending` · `Mean Reversion` · `Volatile` · `Quiet` ·
`Liquidity Stress` · `Event Driven` · `Transitional`

### Opportunity required conceptual fields
`confidence` · `expected_edge` · `expected_duration` · `catalyst` · `expiry` ·
`capital_required` · `strategy_class`

### Recommendation types
`Monitor` · `Observe` · `Prepare` · `Enter` · `Scale In` · `Scale Out` ·
`Reduce Risk` · `Increase Exposure` · `Hedge` · `Avoid` · `Close` · `Review`

### Learning states
`Observation` · `Inference` · `Hypothesis` · `Validated Learning` ·
`Rejected Hypothesis`

### Runtime states
`Healthy` · `Recovering` · `Degraded` · `Stale` · `Failed`

### Broker states
`Healthy` · `Latent` · `Degraded` · `Offline` · `Advisory Only`

### Risk levels
`Critical` · `High` · `Medium` · `Low` · `Informational`

### Confidence bands
| Band | Range |
|---|---|
| Exceptional | 95–100 |
| Very High | 90–94 |
| High | 80–89 |
| Moderate | 70–79 |
| Low | 60–69 |
| Very Low | <60 |

### Freshness labels
`FRESH` · `AGING` · `STALE` · `UNAVAILABLE`

### Lifecycle states
`DRAFT` · `VALIDATING` · `FINAL` · `FAILED` · `SUPERSEDED`

### Change categories
`NEW` · `IMPROVED` · `UNCHANGED` · `DEGRADED` · `REMOVED` · `UNAVAILABLE`

### UI posture lights
`GREEN` · `AMBER` · `RED` · `UNAVAILABLE`

---

## 5. Canonical Contracts

| Contract | Value |
|---|---|
| Brief schema | `css.executive_morning_brief.v1` |
| Archive/EIA schema | `css.executive_intelligence_archive.v1` |
| Platform freeze | `css.executive_intelligence_platform.v1` |
| Trading panel execution marker | `execution_action = NO_EXECUTION` |

### Canonical brief shape

```text
ExecutiveMorningBrief
  envelope (identity, window, hashes, freshness, status, safety locks, KPIs)
  panels:
    executive_decision
    operational_health
    market_intelligence
    trading_intelligence
    learning
  provenance[]
  validation
```

### 173A section mapping (frozen)

| Panel | Absorbed 173A sections |
|---|---|
| Executive Decision | Executive Summary, Confidence, Risk Committee, Recommended Actions |
| Operational Health | Runtime Health, Broker Health |
| Market Intelligence | Overnight Market Summary, Market Regime Analysis |
| Trading Intelligence | Opportunity Ranking, Portfolio Summary |
| Learning | AI Insights, Learning Summary |
| Envelope | Executive KPIs + meta |

---

## 6. Canonical Data Model Objects

Must exist conceptually in implementation:

- `ExecutiveMorningBrief`  
- `MorningBriefArchiveRecord`  
- `MorningBriefVersion`  
- `MorningBriefManifest`  
- `MorningBriefProvenance`  
- `MorningBriefValidationResult`  
- `EiaReportIdentity`  
- `EiaReportLineage`  
- `EiaComparisonRequest` / `EiaComparisonResult`  
- `EiaTrendSeries`  
- `EiaReplayPack`  
- `EiaSearchQuery` / `EiaSearchHit`  
- `EiaExecutiveChanges`  
- `EiaLearningTrack` / `EiaLearningTrajectory`  
- `EiaIntegrityRecord`  
- `EiaBookmark`  

---

## 7. Canonical Archive

### Storage roots (frozen)

```text
artifacts/runtime_reports/morning_briefings/
  manifest.json
  latest.json
  YYYY/MM/YYYY-MM-DD/
    current.json
    vNNN/
      executive_morning_brief.json    # required
      executive_morning_brief.md      # required for FINAL
      executive_morning_brief.pdf     # optional
      manifest.json
      validation.json
    failed/...

artifacts/runtime_reports/executive_intelligence_archive/
  eia_manifest.json
  identity_index.json
  lineage_index.json
  search_index/          # derived
  trends/                # derived
  integrity/             # audit/hash chain
  bookmarks/             # non-secret
```

### Archive rules (frozen)

1. Filesystem JSON (+ MD) is **source of truth**.  
2. SQLite (if any) is **index-only**, never SoT.  
3. Canonical date key: `YYYY-MM-DD`.  
4. Versions: `v001`, `v002`, … — never silent overwrite of FINAL bytes.  
5. Retention: **indefinite** unless governance authorizes deletion.  
6. Secrets forbidden in all stored reports.  
7. Provenance by path + hash; no indiscriminate raw broker dumps.  
8. Atomic publish via temp + `os.replace` (or equivalent).  
9. Market panel `UNAVAILABLE` **blocks FINAL** in v1.  
10. `report_hash` covers sanitized FINAL JSON bytes and is immutable.

---

## 8. Canonical Identity & Lineage

### Identity fields (required on durable records)

`report_id` · `report_date` · `report_version` · `generated_at_utc` ·
`reporting_window_start` · `reporting_window_end` · `runtime_id` ·
`supervisor_id` · `market_session` · `report_hash` · `schema_version` ·
`archive_version` · `briefing_type` · `report_status` · `advisory_only` ·
`data_freshness_status` · `validation_status` · source provenance

### Lineage links (frozen)

`previous` · `next` · `parent` · `children` · `superseded_by` ·
`replay_origin` · `linked_market_events` · `linked_recommendations` ·
`linked_learning`

---

## 9. Canonical APIs (GET-only)

```text
GET /mission-control/api/morning-briefings
GET /mission-control/api/morning-briefings/latest
GET /mission-control/api/morning-briefings/{report_date}
GET /mission-control/api/morning-briefings/{report_date}/versions
GET /mission-control/api/morning-briefings/compare?from=&to=

GET /mission-control/api/eia/compare
GET /mission-control/api/eia/trends
GET /mission-control/api/eia/calendar
GET /mission-control/api/eia/timeline/{report_date}
GET /mission-control/api/eia/replay/{report_id}
GET /mission-control/api/eia/search
GET /mission-control/api/eia/changes
```

Optional read-only mirrors under `/api/v1/` are allowed.  
No POST/PUT/PATCH that grants trading authority.

---

## 10. Canonical Executive KPIs

Frozen KPI set (definitions in 173D §3):

1. Runtime Health  
2. Market Readiness  
3. Opportunity Density  
4. Decision Quality  
5. Learning Velocity  
6. Capital Efficiency  
7. Risk Stability  
8. Broker Reliability  
9. Strategy Strength  
10. Market Confidence  
11. Recommendation Quality  

MC legacy aliases (`uptime`, `portfolio_health`, `system_readiness`,
`rc1_readiness`, etc.) may continue to be populated as compatible fields.

---

## 11. Canonical Governance Rules

1. Fail closed on stale/missing/malformed/inconsistent core evidence.  
2. Never synthesize market, broker, portfolio, or runtime facts.  
3. Label unavailable sections explicitly.  
4. FAILED attempts stored separately; do not replace latest good FINAL pointer.  
5. Integrity hash mismatch → do not serve as authoritative FINAL/replay.  
6. Advisory-only banner required on MC/mobile EIA surfaces.  
7. Engine regime gate remains authoritative for trading filters; executive
   regimes are presentation mappings only.  
8. Knowledge Graph and PDF are **out of freeze critical path** (post-179).  

---

## 12. Canonical Experience (IA Freeze)

Mission Control must eventually provide:

Landing (latest MIB) · Morning Brief · Timeline · Compare · Replay · Search ·
Bookmarks · Favorites · Pinned Reports · Trend Explorer · Historical Replay  

Mobile must eventually provide:

Recent · Historical · Trends · Replay summary · Search · Bookmarks · Offline
viewing of previously opened FINALs  

---

## 13. Canonical Implementation Sequence (Frozen Order)

| Phase | Purpose |
|---|---|
| **174** | Assembler + immutable archive + basic GET |
| **175** | Overnight market producer + market FINAL policy |
| **176** | Identity, lineage, compare, changes, calendar/browser |
| **177** | Trends, search, longitudinal learning tracks |
| **178** | Replay, integrity verifier, trend/replay UX |
| **179** | Mobile polish, bookmarks/pins, hardening |

Do not reorder foundations (174 before 176–178). 175 should precede strong
market compare quality but must not block 174.

---

## 14. Explicit Non-Goals Under Freeze v1.0

- Production execution from MIB/EIA  
- Replacing canonical regime gate enums with executive ontology  
- SQLite as report source of truth  
- Mandatory PDF generation  
- Executive Knowledge Graph implementation  
- Midday/close/weekly/monthly briefing types (design-compatible only)  
- Automatic strategy weight writes from learning trajectories  

---

## 15. Supersession Procedure

To change a frozen decision:

1. Raise governance note citing Freeze v1.0 clause.  
2. Issue `CSS_EXECUTIVE_INTELLIGENCE_ARCHITECTURE_FREEZE_V1.x` or `V2`.  
3. List exact clauses replaced.  
4. Keep prior freeze document immutable in `docs/governance/`.  

---

## 16. Freeze Declaration

**Architecture Freeze v1.0 is declared** for the CSS Executive Intelligence
Platform as of 2026-07-18.

Implementation Phases 174–179 shall conform to this freeze.

Signed as documentation authority within repository governance (no code
certificate implied).

---

## 17. Checklist for Implementers

- [ ] Use `css.executive_morning_brief.v1` only  
- [ ] Write under `artifacts/runtime_reports/morning_briefings/`  
- [ ] Five panels + envelope only as product shape  
- [ ] Assign `report_id` + `report_hash` on FINAL  
- [ ] Never overwrite FINAL JSON bytes  
- [ ] Enforce safety locks on all outputs  
- [ ] Block FINAL if market panel UNAVAILABLE  
- [ ] Sanitize secrets before persist  
- [ ] Expose frozen GET APIs  
- [ ] Keep advisory-only UX banners  
- [ ] Map executive regimes; do not replace engine gate  
- [ ] Follow phase order 174→179  
