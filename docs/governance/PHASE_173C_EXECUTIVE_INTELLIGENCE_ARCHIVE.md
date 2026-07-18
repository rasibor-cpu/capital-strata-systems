# PHASE 173C — Executive Intelligence Archive and Historical Analytics

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Phase type:** Architecture only  
**Status:** DESIGN COMPLETE — no production code, no tests, no runtime artifacts, no commits, no pushes  
**Date:** 2026-07-18  
**Upstream:**  
- `docs/governance/PHASE_173A_EXECUTIVE_MORNING_BRIEFING_ARCHITECTURE.md`  
- `docs/governance/PHASE_173B_EXECUTIVE_INTELLIGENCE_DATA_LAYER.md`  
**Contract family:** `css.executive_intelligence_archive.v1`  

---

## Executive Summary

Phase 173C designs the **Executive Intelligence Archive (EIA)** — CSS’s permanent
institutional memory for executive briefings.

173A defined the morning product surface.  
173B defined the five-panel `ExecutiveMorningBrief` and dated versioned store.  
**173C elevates that store into an authoritative historical system** supporting:

| Capability | Role |
|---|---|
| Retrieval | Exact date / version / identity fetch |
| Comparison | Yesterday through custom ranges across defined categories |
| Trend analysis | 7d / 30d / 90d / 365d / all-time analytics objects |
| Replay | Reconstruct what CSS knew on any historical date (advisory-only) |
| Governance | Immutability, hashes, provenance, secret sanitization |
| Auditability | Lineage chain, version history, integrity verification |
| Explainability | Change narratives, recommendation/event jump targets |

The EIA is the **authoritative historical repository** for all executive
briefings (morning first; midday/close/weekly/monthly as future briefing types
on the same spine).

### Safety locks (immutable for all EIA outputs)

| Flag | Locked value |
|---|---|
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `live_trading_blocked` | `true` |
| `broker_execution_armed` | `false` |

Replay, compare, trend, and search **never** place orders, arm brokers, mutate
limits, or grant trading authority.

### Explicit non-delivery (this phase)

- No production code  
- No tests  
- No runtime artifacts  
- No commits  
- No pushes  

---

## Design Principles

1. **Archive is institutional memory** — not a cache; FINALs are permanent.  
2. **Identity before navigation** — every report has a stable UUID + content hash.  
3. **Lineage is first-class** — previous/next/parent/superseded/derived/replay links.  
4. **Filesystem remains source of truth** — extend 173B paths; index for search/trends.  
5. **Derived analytics are recomputable** — trends/comparisons can rebuild from FINALs.  
6. **Fail closed on integrity failure** — hash mismatch → do not serve as FINAL truth.  
7. **Replay is reconstruction, not re-decision** — show archived evidence, do not
   re-run live gates against today’s market.  
8. **Advisory-only everywhere** — including mobile offline caches.  
9. **Secrets never archived** — sanitizer inherited from 173B FINAL gate.  
10. **Smallest viable index** — JSON manifests first; optional SQLite search index later.

---

## Relationship to 173A / 173B

| Layer | Owns |
|---|---|
| 173A | Morning landing UX + 13→product intent |
| 173B | `ExecutiveMorningBrief` five panels + dated versioned store + basic GET APIs |
| **173C** | **Identity, lineage, compare, trends, timeline, replay, search, changes, longitudinal learning, EIA governance, MC/mobile historical product** |

173B storage root remains canonical:

```text
artifacts/runtime_reports/morning_briefings/
```

173C adds the **EIA control plane** beside it:

```text
artifacts/runtime_reports/executive_intelligence_archive/
  eia_manifest.json
  identity_index.json
  lineage_index.json
  search_index/          # optional derived
  trends/                # derived trend snapshots
  integrity/             # hash chains / audit logs
  bookmarks/             # user/system bookmarks (non-secret)
```

Briefing payloads stay under the 173B morning (and future briefing-type) trees.
EIA indexes **reference** them; they do not duplicate full payloads unless a
replay pack explicitly materializes a sealed snapshot.

---

## SECTION 1 — Report Identity

### Canonical identity object: `EiaReportIdentity`

| Field | Type | Rules |
|---|---|---|
| `report_id` | UUID string | Assigned once at first durable DRAFT→persist; **never reused** |
| `report_date` | `YYYY-MM-DD` | Canonical calendar key (operator reporting TZ) |
| `report_version` | string | `v001`, `v002`, … (173B version key) |
| `generated_at_utc` | ISO-8601 UTC | Wall-clock generation instant |
| `reporting_window_start` | ISO-8601 UTC | Overnight/session window start |
| `reporting_window_end` | ISO-8601 UTC | Window end / cutover |
| `runtime_id` | string \| null | From canonical runtime snapshot at generation |
| `supervisor_id` | string \| null | From supervisor state at generation |
| `market_session` | string | e.g. `OVERNIGHT_TO_OPEN`, `ASIA`, `LONDON`, `NY`, `CUSTOM` |
| `report_hash` | string | SHA-256 (or CSS canonical hash) of sanitized FINAL JSON bytes |
| `schema_version` | string | Brief schema, e.g. `css.executive_morning_brief.v1` |
| `archive_version` | string | EIA envelope version, e.g. `css.executive_intelligence_archive.v1` |
| `briefing_type` | string | `MORNING` (extensible: `MIDDAY`, `CLOSE`, `WEEKLY`, `MONTHLY`) |
| `report_status` | enum | `DRAFT` \| `VALIDATING` \| `FINAL` \| `FAILED` \| `SUPERSEDED` |

### Immutable identity rules

1. **`report_id` is permanent** for that version artifact. Regenerating the same
   `report_date` creates a **new** `report_id` + new `report_version`.  
2. **`report_hash` is computed only on sanitized FINAL bytes** and never changes.  
3. Identity fields inside a FINAL payload are **byte-immutable**.  
4. Pointers/indexes may update `is_current` / lineage links without mutating the
   FINAL payload (173B rule preserved).  
5. If on-disk bytes no longer match `report_hash`, the record is
   `INTEGRITY_FAILED` and must not be served as authoritative FINAL.  
6. `report_date` + `report_version` + `briefing_type` must be unique in the archive.  
7. `report_id` is the preferred external key for bookmarks, replay, and audit.

### Identity index

`identity_index.json` (or sharded by year) maps:

- `report_id → path + hash + status`  
- `(briefing_type, report_date, report_version) → report_id`  
- `current_report_id_by_date[briefing_type][report_date]`

---

## SECTION 2 — Report Lineage

### Lineage object: `EiaReportLineage`

Every FINAL (and optionally FAILED) report participates in a navigable chain.

| Link | Meaning |
|---|---|
| `previous_report` | Prior FINAL for same `briefing_type` by `report_date` order (or null) |
| `next_report` | Next FINAL by date (or null) |
| `parent_report` | Logical parent (e.g. morning brief that a midday brief derives from; or null) |
| `superseded_by` | Newer FINAL `report_id` for same date/type that became current (or null) |
| `derived_reports` | List of child `report_id`s (comparisons packs, replay packs, AI narrative overlays) |
| `replay_origin` | If this artifact is a replay materialization, the original FINAL `report_id` |

Each link stores at minimum: `report_id`, `report_date`, `report_version`,
`report_hash`, `relation`.

### Chain rules

1. Date navigation uses **current FINAL per date** by default.  
2. Version navigation uses `superseded_by` / reverse supersession list.  
3. `derived_reports` never alter parent immutability.  
4. Replay packs set `replay_origin` and `briefing_type` may be
   `REPLAY_PACK` (derived), not a new morning truth.  
5. Broken links (missing target) → lineage status `DEGRADED` but parent FINAL
   remains readable.

### Lineage index

`lineage_index.json` stores adjacency lists for O(1) previous/next and
supersession graphs. Rebuildable from identity index + dated folders.

---

## SECTION 3 — Historical Comparison Engine

### Comparison request: `EiaComparisonRequest`

| Field | Values |
|---|---|
| `baseline` | `YESTERDAY` \| `PREVIOUS_BUSINESS_DAY` \| `PREVIOUS_WEEK` \| `PREVIOUS_MONTH` \| `PREVIOUS_QUARTER` \| `PREVIOUS_YEAR` \| `CUSTOM` |
| `from_report_id` / `to_report_id` | Preferred exact identities |
| `from_date` / `to_date` | Used when resolving current FINALs |
| `categories` | Subset of comparison categories |
| `briefing_type` | Default `MORNING` |

### Comparison categories

| Category | Primary inputs from brief panels / envelope |
|---|---|
| Runtime | Operational Health runtime fields, heartbeat, freshness |
| Market | Market Intelligence overnight + regime |
| Broker | Broker venue status / reliability summary |
| Portfolio | Trading Intelligence portfolio summary |
| Risk | Executive Decision committee/risk + risk health KPI |
| Strategies | Learning + opportunity/strategy leadership fields |
| Learning | Learning panel deltas |
| Executive KPIs | Envelope KPI board |
| Confidence | Decision/panel confidence scores |
| Opportunity quality | Ranked opportunity scores / dispersion |
| Regime | Regime label + transition counts |
| Capital efficiency | Capital posture / allocation efficiency fields when present |

### Comparison result: `EiaComparisonResult`

```text
EiaComparisonResult
  comparison_id
  baseline_report_id / candidate_report_id
  generated_at_utc
  advisory_only = true
  categories[]:
    category
    status: NEW | IMPROVED | UNCHANGED | DEGRADED | REMOVED | UNAVAILABLE
    metrics[]: { name, from_value, to_value, delta, unit, directionality }
    notes[]
  overall_change_score   # bounded advisory score, not execution signal
  provenance[]
  integrity_ok
```

### Resolution rules

1. Prefer `report_id` pins; else current FINAL for date.  
2. If either side missing → category `UNAVAILABLE`, no synthesis.  
3. Directionality tables define whether “up” is IMPROVED or DEGRADED per metric
   (e.g. alert_count up = DEGRADED).  
4. Comparisons are **derived artifacts** (optional persist under
   `derived_reports`) and may be recomputed.

### Conceptual APIs

```text
GET /mission-control/api/eia/compare?baseline=PREVIOUS_BUSINESS_DAY&date=YYYY-MM-DD
GET /mission-control/api/eia/compare?from=YYYY-MM-DD&to=YYYY-MM-DD
GET /mission-control/api/eia/compare/by-id?from_id=<uuid>&to_id=<uuid>
```

---

## SECTION 4 — Trend Analytics

### Trend windows

`7d` · `30d` · `90d` · `365d` · `all_time`

### Trend object: `EiaTrendSeries`

| Field | Notes |
|---|---|
| `series_id` | Stable id per metric + window |
| `metric` | e.g. `runtime_health_score`, `broker_reliability`, `confidence`, … |
| `window` | enum above |
| `points[]` | `{ report_date, report_id, value, status }` |
| `moving_average` | SMA/EMA config + values |
| `drift` | Change vs window start / vs prior window |
| `coverage` | Fraction of expected business days present |
| `integrity_ok` | All points hash-verified when claimed |
| `advisory_only` | `true` |

### Supported trend families

| Family | Examples |
|---|---|
| Moving averages | KPI and confidence SMAs |
| Confidence drift | Decision confidence slope / volatility |
| Runtime stability | Freshness incidents, heartbeat gap rates |
| Market regimes | Regime occupancy histogram / transition rate |
| Strategy leadership | Top strategy tenure / rotation |
| Broker reliability | Per-venue uptime / fail-closed counts |
| Risk evolution | Risk health, veto frequency |
| Learning progression | Optimality rate, missed-opportunity trend |
| Capital efficiency | Allocation efficiency when present |
| Decision quality | Post-hoc recommendation accuracy overlays (when evidence exists) |

### Materialization

- **On demand** from FINAL briefs (default).  
- **Optional nightly snapshot** under `trends/YYYY-MM-DD/` for MC dashboard speed.  
- Snapshots are derived; regenerable; never replace FINALs.

### Conceptual APIs

```text
GET /mission-control/api/eia/trends?metric=confidence&window=30d
GET /mission-control/api/eia/trends/board?window=90d
```

---

## SECTION 5 — Executive Timeline

### Timeline model: `EiaExecutiveCalendar`

Navigation axes: **Year → Month → Week → Day**.

| Capability | Behavior |
|---|---|
| `latest` | Current latest FINAL (`briefing_type=MORNING` default) |
| `previous` / `next` | Adjacent available FINAL dates |
| `jump to date` | Exact `YYYY-MM-DD` |
| `jump to market event` | Timeline annotations linked to intel/regime events |
| `jump to major recommendation` | Anchors into Executive Decision actions with `report_id` + fragment |

### Calendar cell: `EiaCalendarDay`

```text
date
has_final
has_failed
current_report_id
overall_status
regime_label
tags[]
annotations[]   # market events / major recommendations / bookmarks
```

### Annotation sources

- Regime transitions from Market panel  
- Major recommendations (priority ≥ threshold)  
- Runtime RED days  
- User bookmarks / pinned reports  
- Optional external market event tags (cited)

### Conceptual APIs

```text
GET /mission-control/api/eia/calendar?year=2026&month=07
GET /mission-control/api/eia/timeline/latest
GET /mission-control/api/eia/timeline/{report_date}
```

---

## SECTION 6 — Replay Mode

### Purpose

Mission Control reconstructs **exactly what CSS knew** on a historical date from
archived FINAL evidence — not what today’s live systems believe.

### Replay package: `EiaReplayPack`

| Component | Source |
|---|---|
| Executive Brief | FINAL `executive_morning_brief.json` |
| Runtime | Provenance-referenced snapshot hashes + embedded sanitized runtime summary from brief |
| Market regime | Market panel freeze |
| Risk | Risk/committee freeze |
| Portfolio | Portfolio freeze |
| Recommendations | Recommended actions freeze |
| Broker status | Sanitized broker panel freeze |
| Learning | Learning panel freeze |

### Replay rules

1. **Advisory-only** — no live execution, no broker calls required for replay.  
2. **No re-gate against live market** for historical truth claims.  
3. Optional “compare to live now” is a **separate** mode and must be labeled
   `LIVE_DELTA` (not replay).  
4. If provenance targets are missing but brief embeds summaries, serve brief
   layer and mark deep runtime replay `DEGRADED`.  
5. If `report_hash` fails → refuse authoritative replay.  
6. Replay UI shows watermark: `HISTORICAL REPLAY · ADVISORY ONLY`.

### Replay origin lineage

Creating a materialised replay export sets:

- new derived `report_id`  
- `replay_origin = <original report_id>`  
- parent remains original FINAL  

### Conceptual APIs

```text
GET /mission-control/api/eia/replay/{report_id}
GET /mission-control/api/eia/replay/by-date/{report_date}
```

---

## SECTION 7 — Search

### Search request: `EiaSearchQuery`

Search dimensions:

| Dimension | Notes |
|---|---|
| date | exact or range |
| market | market/session tags |
| asset | instruments mentioned in opportunities/portfolio |
| strategy | strategy ids/names |
| confidence | min/max |
| recommendation | action text/tags |
| market regime | regime labels |
| runtime event | incident tags / RED runtime days |
| risk event | vetoes / risk RED |
| broker | venue status filters |
| keyword | full-text over MD/JSON sanitized fields |
| report tags | operator/system tags |

### Search index strategy

| Phase | Approach |
|---|---|
| v1 | Manifest + identity scan + extracted `search_doc.json` beside each FINAL |
| v2 | Optional SQLite FTS index over `search_doc` fields |
| Never | Index secrets or raw broker payloads |

### `search_doc.json` (per FINAL, derived)

Compact extract: date, regime, venues, assets, strategies, action keywords,
KPI scalars, tags, `report_id`, paths. Rebuildable.

### Conceptual API

```text
GET /mission-control/api/eia/search?q=...&regime=RISK_OFF&from=...&to=...
```

---

## SECTION 8 — Executive Changes

### Automatic change briefs: `EiaExecutiveChanges`

Prebuilt narratives/objects for:

- What changed since yesterday?  
- What changed since last week?  
- What changed since last month?  
- What changed since the previous regime?  

### Change categories

`NEW` · `IMPROVED` · `UNCHANGED` · `DEGRADED` · `REMOVED`

### Change item

```text
category
domain            # Runtime|Market|Broker|...
title
detail
from_value / to_value
evidence_report_ids[]
severity
```

### Regime-relative changes

Resolve `previous regime` as the most recent prior date where `regime_current`
differs from baseline date’s regime; compare current FINAL vs that date’s FINAL.

### Persistence

May store under derived path:

```text
.../derived/changes/{baseline}/{report_date}.json
```

Always recomputable from Comparison Engine.

---

## SECTION 9 — Longitudinal Learning

### Purpose

Define how CSS **learns over time** using EIA as the evidence backbone — without
auto-applying weight changes (advisory unless a future governed learning phase
explicitly allows controlled updates outside EIA).

### Longitudinal tracks: `EiaLearningTrack`

| Track | Signals |
|---|---|
| Strategy evolution | Leadership changes, tenure, retirement of strategies |
| Confidence calibration | Predicted confidence vs later outcomes (when outcome evidence exists) |
| Market behaviour | Regime occupancy, transition shocks |
| Model improvement | Learning panel optimality / reliability trends |
| Runtime reliability | Stability trends, incident rates |
| Committee decisions | Consensus/veto distributions over time |
| Broker quality | Venue reliability trends |
| Recommendation accuracy | Advisory action followed by measurable outcomes **when** outcome linkage exists |

### Learning memory objects

- `EiaLearningSnapshot` — point-in-time extract from a FINAL Learning panel  
- `EiaLearningTrajectory` — series across windows  
- `EiaCalibrationRecord` — confidence vs outcome joins (nullable if outcomes absent)

### Rules

1. EIA stores **observations and trajectories**, not silent production mutations.  
2. Missing outcomes → accuracy tracks marked `INSUFFICIENT_EVIDENCE`.  
3. Feeds future AI narrative layers by citation to `report_id` / `report_hash` only.

---

## SECTION 10 — Governance

### Immutability

- FINAL briefing JSON/MD bytes immutable (173B).  
- Identity + `report_hash` permanent.  
- Supersession via new versions + lineage, not overwrite.

### Retention

- Retain indefinitely unless explicit future governance authorizes deletion.  
- Derived indexes/trends may be rebuilt/purged without deleting FINALs.

### Archive integrity

- Per-report `report_hash`  
- Optional daily `integrity_manifest` listing hashes  
- Periodic verifier job (future) flags `INTEGRITY_FAILED`

### Digital hashes

- Content hash over sanitized FINAL JSON  
- Optional hash chain: `prev_day_hash` in integrity log for tamper evidence

### Audit trails

Append-only `integrity/audit.jsonl` events:

`GENERATED`, `FINALIZED`, `SUPERSEDED`, `REPLAY_CREATED`, `COMPARE_PERSISTED`,
`INTEGRITY_FAILED`, `SEARCH_REINDEXED`

### Version history

Full `vNNN` tree + lineage supersession graph.

### Data provenance

`MorningBriefProvenance` / EIA provenance entries: path, hash, producer,
freshness — reference, don’t copy secrets.

### Secret sanitization

Hard gate before FINAL (173B); EIA refuses to index unsanitized payloads.

### Advisory-only guarantees

All EIA APIs and UI surfaces embed locked safety flags; replay watermark
mandatory.

---

## SECTION 11 — Mission Control

### Surfaces

| Surface | Purpose |
|---|---|
| Historical Report Browser | List/filter FINALs and FAILED attempts |
| Executive Timeline | Year/month/week/day navigation |
| Trend Dashboard | Windowed trend boards |
| Comparison View | Baseline selectors + category diffs |
| Replay View | Historical reconstruction watermarked |
| Calendar | Status-colored day grid + annotations |
| Bookmarks | User-saved `report_id`s |
| Favorites | Shortlist |
| Pinned reports | Sticky pins on landing / timeline |

### UX rules

- Default landing remains **latest morning FINAL** (173A product intent).  
- Historical modes never look like live armed trading.  
- Status badges: freshness, lifecycle, integrity.  
- Version selector per date.  
- Clear advisory-only banner on all EIA pages.

### Conceptual MC API prefix

```text
/mission-control/api/eia/...
```

Reuses 173B morning-briefings GETs for payload fetch; EIA APIs add identity,
lineage, compare, trends, calendar, replay, search, bookmarks.

---

## SECTION 12 — Mobile

| Feature | Mobile behavior |
|---|---|
| Recent reports | Last N FINALs compact cards |
| Historical reports | Date list + jump-to-date |
| Executive trends | Sparklines for key KPIs / confidence |
| Replay summary | Read-only five-panel digest + watermark |
| Search | Constrained filters (date, regime, keyword) |
| Bookmarks | Sync or device-local ids |
| Offline viewing | Cache previously opened FINAL JSON only |

Mobile excludes heavy compare matrices by default; offers “changes since
yesterday/week” summaries instead.

---

## SECTION 13 — Implementation Roadmap

| Phase | Scope | Depends on |
|---|---|---|
| **173D** | Implement 173B data layer: assembler, archive store, FINAL/versioning, basic MC/mobile GET latest+by-date | 173A, 173B design |
| **173E** | Overnight Market Summary producer + Market panel completeness; secret sanitizer hardening | 173D |
| **173F** | EIA identity + lineage indexes; compare engine; executive changes; MC browser + calendar | 173D (173E preferred for market compare quality) |
| **174** | Trend dashboard + longitudinal learning tracks + search index (FS `search_doc`, optional SQLite FTS) | 173F |
| **175** | Replay mode packs + integrity verifier + bookmarks/favorites/pins + mobile offline/replay summary | 173F, 174 |

### Dependency graph

```text
173A (product) → 173B (data contract/archive design)
                      ↓
                   173D (implement store + brief)
                      ↓
            ┌─────────┴─────────┐
         173E (market)       173F (EIA compare/lineage)
                      \         /
                       \       /
                        → 174 (trends/search/learning)
                              ↓
                           175 (replay/integrity/UX polish)
```

### Non-goals until listed phases

- Live re-decision in replay  
- Auto-trading from trends  
- Deleting FINALs  
- PDF requirement (still optional)

---

## Canonical EIA Objects (Minimum Set)

| Object | Role |
|---|---|
| `EiaReportIdentity` | Stable identity + hashes |
| `EiaReportLineage` | Navigable chain links |
| `EiaComparisonRequest` / `EiaComparisonResult` | Historical compare |
| `EiaTrendSeries` | Windowed trends |
| `EiaExecutiveCalendar` / `EiaCalendarDay` | Timeline/calendar |
| `EiaReplayPack` | Advisory historical reconstruction |
| `EiaSearchQuery` / `EiaSearchHit` | Search |
| `EiaExecutiveChanges` | Automatic change briefs |
| `EiaLearningTrack` / `EiaLearningTrajectory` | Longitudinal learning |
| `EiaIntegrityRecord` | Hash/audit evidence |
| `EiaBookmark` | Pinned/favorite references |

---

## Acceptance Criteria (future implementation)

- [ ] Every FINAL has UUID identity + `report_hash`  
- [ ] Lineage previous/next/superseded navigable  
- [ ] Compare supports listed baselines + categories  
- [ ] Trends for 7/30/90/365/all-time recomputable  
- [ ] Calendar year/month/week/day navigation works  
- [ ] Replay reconstructs archived brief layers without live execution  
- [ ] Search supports listed dimensions via derived index  
- [ ] Executive change briefs emit NEW/IMPROVED/UNCHANGED/DEGRADED/REMOVED  
- [ ] Longitudinal tracks readable without mutating production weights  
- [ ] Integrity failure blocks authoritative serve  
- [ ] MC + mobile historical experiences match sections 11–12  
- [ ] Advisory-only locks present on all EIA outputs  

---

## Known Limitations

1. Outcome-linked recommendation accuracy requires trade/outcome joins that may
   be incomplete early on.  
2. Deep runtime replay degrades if provenance artifacts were rotated/deleted.  
3. Full-text search quality depends on `search_doc` extraction richness.  
4. Business-day and holiday calendars remain policy inputs (open from 173B).  
5. Multi-briefing-type lineage (`MIDDAY`/`CLOSE`) is designed but not required
   before morning EIA is live.  

---

## Open Questions

1. Should integrity hash-chain be daily or per-report only for v1?  
2. Are bookmarks server-side (RBAC user store) or device-local first?  
3. Minimum provenance retention for deep replay (30d artifacts vs brief-only)?  
4. Default compare baseline for landing widget: yesterday vs previous business day?  
5. When outcomes exist, which ledger is authoritative for accuracy tracks?

---

## Governance Statement

Phase 173C is architecture-only. It defines the Executive Intelligence Archive
as CSS’s permanent institutional memory — identity, lineage, comparison, trends,
timeline, replay, search, executive changes, longitudinal learning, governance,
and Mission Control / mobile historical experiences — with a phased roadmap
through 175.

**Deliverable:**

- `docs/governance/PHASE_173C_EXECUTIVE_INTELLIGENCE_ARCHIVE.md`

**Not delivered:** production code, tests, runtime artifacts, commits, pushes.
