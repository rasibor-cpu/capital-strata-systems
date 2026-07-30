# DIP-002 — Trade DNA Canonical Schema

**Programme:** CSS Decision Intelligence Platform (DIP)
**Workstream:** DIP-002
**Title:** Trade DNA Canonical Schema
**Status:** SCHEMA IMPLEMENTED — CAPTURE PIPELINE NOT WIRED
**Repository:** `C:\rasib\source\capital-strata-systems`
**Branch:** `css-v1.0.1-maintenance`
**Base HEAD:** `c1b2f88b743e31cc94954b4a95b432cd5098183b`
**Date:** 2026-07-30

**Does not authorize:** live capture wiring, ExecutionGate changes, Mission Control changes, automatic capital movement, or desktop interference.

---

## 1. Objectives

1. Ratify the canonical **Trade DNA** immutable fact schema (`css.trade_dna.v1`).
2. Separate **Facts / Derived / Advisory** into distinct layers.
3. Introduce an **Evidence Graph** so no analytical conclusion exists without cited trades, versions, sample size, confidence, and timestamp.
4. Provide deterministic validation, content hashing, and append-only revision semantics.
5. Remain **offline from execution** — schema and store foundation only.

---

## 2. Scope

### In scope

| Item | Location |
| --- | --- |
| Fact schema + deserialize | `backend/intelligence/trade_dna/schema.py` |
| Content hash | `backend/intelligence/trade_dna/hashing.py` |
| Validation | `backend/intelligence/trade_dna/validation.py` |
| Append-only revisions | `backend/intelligence/trade_dna/revisions.py` |
| Derived metrics envelope | `backend/intelligence/trade_dna/derived.py` |
| Evidence Graph | `backend/intelligence/trade_dna/evidence_graph.py` |
| Advisory envelope | `backend/intelligence/trade_dna/advisory.py` |
| Serialization | `backend/intelligence/trade_dna/serialization.py` |
| Deterministic tests | `tests/test_dip002_trade_dna_schema.py` |

### Out of scope / non-goals

- Wiring DNA writer into `TradeRuntimeService` / close events
- Modifying ExecutionGate, RiskGovernor, AntiBleed, brokers, sizing
- Mission Control panels
- Decision Analytics / Edge / Capital engines (DIP-003+)
- Desktop runtime
- Persisting derived metrics inside fact DNA

---

## 3. Evidence model (three layers)

```text
Layer 1 FACTS (immutable TradeDNARecord)
  → content_hash, revision chain, evidence custody

Layer 2 DERIVED (DerivedTradeMetrics)
  → keyed by dna_id + analysis_version; recomputable

Layer 3 ADVISORY (AdvisoryConclusion)
  → must bind EvidenceGraphNode; advisory_only locked
```

### Layer 1 — Facts

Identity, Execution, Market, Strategy, Risk, Governance, Liquidity, Volatility, Indicators, Broker, Timing, Outcome labels, Metadata, Versioning, Evidence custody, Content hash, Revision chain.

Facts never change in place. Corrections create superseding revisions.

### Layer 2 — Derived

Profit, return %, holding period, MAE, MFE, expectancy/edge contribution, capital efficiency, execution quality, Sharpe/drawdown contribution.

Stored separately. Forbidden as top-level DNA fact keys.

### Layer 3 — Advisory

Increase allocation, pause strategy, research exits, reduce volatility exposure, confidence, opportunity ranking.

Never become facts. Serialized through `AdvisoryPayloadBuilder.lock`.

---

## 4. Schema

**Schema version:** `css.trade_dna.v1`

Categories (extensible via ignored unknown keys + `metadata.extensions`):

| Category | Role |
| --- | --- |
| identity | `trade_id`, `dna_id`, instrument, side, session |
| execution | prices, qty, notional, fees, slippage, fill result |
| market | symbol, venue, session, regime |
| strategy | strategy_id, engine_mode, signal, model |
| risk | stops, risk_pct, margin, settings bag |
| governance | gate final/reason, kill-switch, decisions bag |
| liquidity | spread regime, volume proxy, gap |
| volatility | ATR, realized vol, vol regime |
| indicators | observed snapshot bag |
| broker | broker_name/mode (no secrets) |
| timing | opened/closed/decision/executed ISO timestamps |
| outcome | status, exit_reason, win_loss (no MAE/MFE) |
| evidence_custody | evidence_version, source event IDs, writer |
| revision | revision number, supersedes_dna_id, reason |
| metadata | provenance + extensions |
| content_hash | SHA-256 over canonical JSON excluding itself |

---

## 5. Evidence Graph

Every analytical/advisory conclusion must reference:

| Field | Required |
| --- | --- |
| `trade_ids` | yes (≥1) |
| `dna_ids` | recommended |
| `evidence_version` | yes (`css.trade_dna.evidence.v1`) |
| `analysis_version` | yes (`css.trade_dna.analysis.v1`) |
| `sample_size` | yes (≥1) |
| `confidence` | yes (0.0–1.0) |
| `generated_at` | yes (ISO-8601) |

`build_advisory_conclusion` refuses conclusions without evidence trade IDs.

---

## 6. Versioning strategy

| Version family | Constant | Purpose |
| --- | --- | --- |
| Schema | `SCHEMA_VERSION` | Fact document shape |
| Evidence | `EVIDENCE_VERSION` | Custody / citation envelope |
| Analysis | `ANALYSIS_VERSION` | Derived metric computation family |
| Advisory | `ADVISORY_VERSION` | Recommendation envelope |

### Compatibility rules

1. Readers accept only registered entries in `SUPPORTED_SCHEMA_VERSIONS`.
2. Unknown category keys are ignored on deserialize (forward additive fields).
3. Breaking field semantics require a new `css.trade_dna.vN` and registry update.
4. Migration: recompute derived/advisory from immutable facts; never rewrite historical DNA hashes.
5. Superseding revisions preserve prior `dna_id` forever; head = latest revision for a `trade_id`.

---

## 7. Validation rules

| Rule | Fail code |
| --- | --- |
| Required `trade_id` / `dna_id` | `missing_required_field` |
| Unsupported schema version | `unsupported_schema_version` |
| Non-positive entry/exit price | `non_positive_price` |
| Invalid / unordered timestamps | `invalid_timestamp` / `timestamp_order` |
| Instrument ≠ market.symbol | `instrument_inconsistency` |
| Missing / wrong content hash | `missing_content_hash` / `content_hash_mismatch` |
| Revision >1 without supersedes | `revision_missing_supersedes` |
| Self-supersede | `revision_self_reference` |
| Duplicate commit of same dna_id | `dna_id_already_committed` |
| Supersede unknown / trade mismatch / gap | `supersedes_*` / `revision_sequence_gap` |

---

## 8. Immutability

1. `AppendOnlyDNAStore.commit` never overwrites an existing `dna_id`.
2. `supersede` allocates a new `dna_id`, increments revision, sets `supersedes_dna_id`.
3. Content hash seals the fact body.
4. Derived and advisory layers remain outside the sealed body.

---

## 9. Future capture pipeline (not implemented here)

When authorized (expected DIP-002b / DIP-003 precursor):

1. On validated close (and eligible open), project lifecycle + MW-004 economics → `TradeDNARecord`.
2. Commit via append-only store / durable JSON documents.
3. Emit evidence custody source event IDs from lifecycle/gate/context.
4. Still **no** execution behaviour change — write-after-fact only.

---

## 10. Tests

`tests/test_dip002_trade_dna_schema.py` covers:

- serialization / deserialization
- schema versioning
- content hash stability and mismatch
- append-only revisions
- invalid records / missing required fields
- invalid timestamps and prices
- instrument consistency
- fact / derived / advisory separation
- evidence graph + advisory lock
- backward-compatible unknown extension handling
- unsupported schema fail-closed

---

## 11. Recommendation

**SCHEMA_READY — AWAITING CAPTURE WIRING AUTHORIZATION**

Next step (when approved): durable DNA writer from close events **without** modifying gate/sizing behaviour, then DIP-003 Decision Analytics.

---

*End of DIP_002_TRADE_DNA_SCHEMA.md*
