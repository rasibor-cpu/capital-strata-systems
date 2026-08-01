# MI-EXT-001 — External Events, Sources and Provenance Charter

**Program:** CSS Market Intelligence
**Work item:** MI-EXT-001
**Branch:** `css-market-intelligence-external-sources-001`
**Base commit:** `66e11d4f83600a7765b4e55afa33d19e301dd70e`
**Worktree:** `C:\rasib\source\capital-strata-systems-mi`
**Status:** advisory-only design + offline fixture implementation
**Live trading / runtime activation:** NOT AUTHORIZED

---

## 1. Executive summary

MI-EXT-001 strengthens the existing CSS Market Intelligence layer with a governed external-event, source-trust, and provenance contract. It extends Global Intelligence (GIE), `intel/` adapters, overnight market intelligence, and Phase 138 multi-factor market intelligence. It does **not** create a second parallel Market Intelligence engine, does **not** modify the running CSS endurance instance, and does **not** grant execution authority.

Every ingested event is forced to `advisory_only=true` and `execution_allowed=false`.

## 2. Existing-layer audit

| Module / area | Path (representative) | Purpose | Inputs | Outputs | Persistence | Frequency | Provenance | Limitations | Status on HEAD `66e11d4f` |
|---|---|---|---|---|---|---|---|---|---|
| Overnight MI | `backend/executive_intelligence/overnight_market.py` | Overnight session market context | broker/market snapshots, calendars | executive overnight summaries | session/runtime | overnight cycle | section-level | not a full external news provenance layer | **active** |
| Multi-factor MI | `backend/market_intelligence/*` | Factor scoring / dashboard intel | market features | factor scores / MC projections | local/runtime | periodic | limited | not source-tiered event store | **active** |
| GIE | `backend/intelligence/global_intelligence/` | Global event models, calendars, governance responses | static calendars, partial feeds | `IntelligenceEvent`, regime/governance hints | in-process / local | partial | source name string only | weak ingestion; no catalogue tiers | **partial** |
| Intel adapters | `intel/` (RSS/FRED/GDELT/etc.) | Envelope ingestion adapters | external feeds | `IntelEnvelope` | adapter-local | adapter-dependent | envelope metadata | uneven coverage; licensing not catalogue-governed | **partial / legacy** |
| MC market intelligence | Mission Control market_intelligence pages + `source_registry` | Operator display / section provenance | backend projections | UI panels | UI/runtime | on demand | section provenance ≠ news provenance | display only; not event dedup | **active (display)** |
| Sentiment engines | sentiment / strategy intelligence tests & engines | sentiment scoring | text/features | scores | local | periodic | weak | not trust-tiered | **partial** |
| Economic calendar | GIE calendars / macro helpers | scheduled macro awareness | static/scheduled calendars | calendar events | local | scheduled | limited | not multi-jurisdiction live catalogue | **partial** |
| Broker market data | broker connectors / reporting | prices, account, fills | broker APIs | market/account state | runtime | live/runtime | broker-id provenance | price authority ≠ news authority | **active** |
| Regulatory feeds | none canonical | — | — | — | — | — | — | no governed SEC/CBN/NGX catalogue | **absent / gap** |
| Event classification | GIE `EventCategory` + local heuristics | coarse categories | titles/metadata | enum categories | in-process | on ingest | none | narrower than MI-EXT taxonomy | **partial** |
| Source confidence | scattered confidence floats | confidence scores | heuristics | float | in-process | on score | inventable risk | no UNAVAILABLE discipline | **partial** |
| Duplicate suppression | limited / local | ad-hoc | payloads | filtered sets | local | on ingest | history often dropped | no multi-source merge contract | **partial** |
| Freshness/staleness | ad-hoc TTLs | age checks | timestamps | drop/keep | local | on read | weak | no FRESH/AGING/STALE/EXPIRED contract | **partial** |
| Signal generation | strategy / opportunity engines | signals | market + intel | signals | runtime | continuous | mixed | must not take MI-EXT as order authority | **active (separate)** |
| Portfolio decisions | portfolio / executive decision engines | allocation advice | portfolio + intel | recommendations | runtime | periodic | mixed | DIP/Trade DNA absent on this SHA | **active / partial** |
| Execution-gate inputs | ExecutionGate / RiskGovernor / AntiBleed | hard execution controls | risk/auth/size | allow/deny | runtime | per order | N/A | MI-EXT must never bypass | **active (out of scope)** |
| Trade DNA / Edge / Enterprise Intel | maintenance branch only | profit attribution learning | trades/events | advisory learning | maintenance | N/A on this SHA | N/A | **absent until MR-001** | **absent** |
| Alerts / notifications | MC / ops alerts | operator alerts | health/events | notifications | runtime | event-driven | limited | design-only for MI-EXT panels this phase | **partial** |

## 3. Non-duplication decision

**Spine:** catalogue → fixture/live adapters → validate/normalize/hash → dedup/corroborate → freshness → classify → advisory impact → optional GIE bridge → overnight/MC projection later.

Reuse GIE `IntelligenceEvent` via optional fail-safe `gie_bridge.py` for compatibility only. Do not fork overnight MI or Phase 138 into a second engine. Do not create a second GIE scheduler/store/decision engine. DIP/Trade DNA integration is design-only until MR-001.

## 4. Source tiers

1. **TIER 1 — OFFICIAL PRIMARY** — regulators, central banks, exchanges, statistical agencies, issuer filings
2. **TIER 2 — VERIFIED INSTITUTIONAL** — Reuters/Bloomberg (licensed), banks, securities firms, recognized data providers
3. **TIER 3 — SECONDARY NEWS** — established media / aggregators (context only)
4. **TIER 4 — UNVERIFIED / SOCIAL** — not eligible for actionable CSS intelligence without corroboration

Lower tiers cannot override contradictory higher-tier sources.

## 5. Source catalogue

Canonical file: `docs/governance/MI_EXT_001_SOURCE_CATALOGUE.json`.

Each source defines ID, name, jurisdiction, category, classification, trust tier, latency, update frequency, access method, auth, cost, licensing, instruments, failure behavior, freshness, evidence retention, advisory eligibility, and execution prohibition.

Commercial / unreviewed sources remain `enabled=false` with `requires_terms_review=true` / `access_status=BLOCKED`.

## 6. Provenance contract

Schema: `docs/governance/MI_EXT_001_EVENT_SCHEMA.json` and `ExternalEvent` dataclass.

Required fields include event/source identity, URLs/references, publisher, jurisdiction, timestamps (`published_at` / `retrieved_at` / `effective_at`), title, summary, category, instruments/asset classes, raw/normalized hashes, parser/schema versions, confidence, verification, corroboration, contradiction, freshness, licensing, and hard flags `advisory_only=true`, `execution_allowed=false`.

Unknown facts remain `UNKNOWN` or `UNAVAILABLE`. The system must not invent timestamps, instruments, prices, regulatory meaning, confidence, or source identity.

## 7. Deduplication

Deterministic clustering via normalized title, category, instruments, and publication-day window / semantic fingerprint. Merged events expose primary source, corroborating sources, conflicting sources, duplicate count, first seen, last updated, and canonical event hash. Source history is preserved via corroborating/conflicting IDs — never deleted silently.

## 8. Freshness

States: `FRESH`, `AGING`, `STALE`, `EXPIRED`, `UNKNOWN`.
Category families map to windows (real-time alerts, regulatory, filings, macro, central-bank, research, etc.). Only `FRESH` / `AGING` may be treated as actionable advisory intelligence.

## 9. Classification

Deterministic keyword rules over title+summary into the MI-EXT category taxonomy (monetary policy, inflation, employment, regulatory action, outages, crypto regulation, etc.). Unknown → `unknown`. Explainable by rule match order.

## 10. Impact assessment

Advisory-only assessment of jurisdiction/asset class/instruments (when present), direction, magnitude, horizon, evidence, counter-evidence, and completeness. Stale events do not silently drive current recommendations. Impact never authorizes execution or mutates ExecutionGate / RiskGovernor / AntiBleed / position size / live authority.

## 11. Decision-layer integration

`decision_integration.py` emits an `AdvisoryContextPatch` (market context, event-risk warnings, instrument watchlist, research opportunities, regime hints, confidence adjustment hint) with all execution mutation flags hard-false.

Profit-attribution learning (markets/strategies/regimes/events/instruments/sessions/entries/exits) targets Trade DNA / Decision Analytics / Edge / Enterprise Intelligence **after** MR-001. No auto-allocation authority.

## 12. Adapter contract

`ExternalSourceAdapter`: fetch → validate → normalize → hash → (pipeline) persist/dedup/classify/score/health, fail closed. Supports timeouts, retries, rate-limits, unavailable/malformed/stale/auth/licensing/schema/partial/duplicate. Adapter failures must not crash CSS.

First wave: `FixtureJsonAdapter` only — no live network in this phase.

## 13. Security / licensing

- Credentials never logged; secrets never in event payloads
- Licensing recorded per source; redistribution restrictions honored
- Unsupported scraping prohibited
- URL scheme validation; payload size bounds; redacted errors
- Source spoof detection (adapter `source_id` must match event)
- Malformed documents fail safely

## 14. Observability

`SourceHealth`: enabled, last success/attempt, freshness, latency, failure counts, rate-limit state, parser version, last event count, redacted last error, trust tier, operational status. Mission Control panels may be designed later — not activated against the running endurance instance in this phase.

## 15. Tests

Offline tests cover registration, tier ordering, provenance completeness, hashing, dedup, contradiction, freshness, unsupported rejection, malformed payloads, timeout/rate-limit/licensing, classification, impact, corroboration, Tier-1 dominance, no execution enablement, adapter crash containment, replay determinism, **static execution-boundary scanning**, **fixture-only/no-network guarantees**, and **catalogue-integrity validation**.

Blocked in this environment (not counted as passed): Mission Control / Phase 138 launcher tests that require the `cryptography` package (`ModuleNotFoundError`) — **BLOCKED**, dependencies not installed per program rules.

## 16. Current limitations

- No live external connections
- Many institutional/commercial sources blocked pending terms review
- DIP/Trade DNA/Edge Intelligence absent on this branch
- MC panels not activated
- Persistence is in-pipeline only (no production store activation)
- Impact assessment is conservative/heuristic, not a predictive model
- Controlled-online validation **unauthorized**
- Live trading **unauthorized**

## 17. Future controlled-online validations

Separate approval required for: SEC EDGAR fair-access live pull, Fed/BLS/BoC/CBN/NBS official release polling, Coinbase public MD (rate-limited), and any licensed Reuters/Bloomberg access after commercial review. Until approved, `LiveNetworkFetchAdapter` and `is_live_fetch_authorized()` fail closed.

## 18. Explicit advisory-only statement

**MI-EXT-001 is advisory-only.** External events may inform research context and operator awareness. They must not authorize execution, bypass ExecutionGate, modify RiskGovernor or AntiBleedGuard, change position size, change live authority, or submit orders.

---

## 19. Hardening certifications (MI-EXT-001 final bounded review)

### 19.1 Fixture-only / no-network certification
Wave 1 ingestion uses `FixtureJsonAdapter` only. Approved fixture root: `tests/fixtures/mi_ext_001/`. Paths outside that root are rejected. The `external_events` package does not import `requests` / `httpx` / `aiohttp` / `socket` / `urllib.request`. `LiveNetworkFetchAdapter` fails closed. No API credentials are required or read into event payloads during fixture processing. **Live network calls: NOT AUTHORIZED.**

### 19.2 Static execution-boundary certification
Automated AST/static tests prove `backend/intelligence/external_events/` does not import or invoke ExecutionGate, RiskGovernor, AntiBleedGuard, Margin Gate mutation, broker order adapters, order routers, live-authority mutation, position-sizing engines, or runtime start/stop controls. Allowed outputs remain advisory data / optional GIE projection only.

### 19.3 Catalogue-integrity rules
Every source must declare unique `source_id`, recognized trust tier, jurisdiction, access method, cost/access classification, licensing classification, freshness threshold, advisory influence rule, `direct_execution_influence=false`, `prohibited_from_direct_execution=true`, operational state, and `online_validation_required`. Catalogue carries deterministic `catalogue_integrity_hash`. Tier 4 cannot be advisory-enabled; blocked/unreviewed/commercial-without-approved-license sources cannot be enabled; lower-tier contradictions cannot override Tier 1.

### 19.4 Exact GIE integration boundary
- **Authoritative owner of provenance/dedup/freshness/advisory impact:** MI-EXT (`backend/intelligence/external_events/`).
- **Existing consumer model:** GIE `IntelligenceEvent` via optional `gie_bridge.to_gie_event`.
- Bridge does **not** create a second scheduler, event store, or decision/execution engine.
- Bridge is optional and fail-safe (`None` when GIE unavailable or published_at UNAVAILABLE/UNKNOWN — timestamps are never invented).
- Bridge does not mutate execution state, capital, sizing, or live authority.

### 19.5 Authorization status
| Item | Status |
|---|---|
| Fixture-only offline operation | CERTIFIED |
| Static execution boundary | CERTIFIED |
| Controlled-online validation | UNAUTHORIZED |
| Live trading | UNAUTHORIZED |
| Active CSS endurance runtime modification | FORBIDDEN / NOT PERFORMED |
| Cryptography-dependent MC/Phase138 launcher tests | BLOCKED (env) |
