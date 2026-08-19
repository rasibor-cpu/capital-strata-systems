> **RC-LIVE-CONSOL-001 recovery addendum**
> Recovered onto `css-v1.0.1-maintenance` as **fixture/offline providers only**.
> ExecutionGate dependency injection and AntiBleed wiring were **not** recovered.
> Live network access fails closed. Live trading remains unauthorized.



## 1. Executive summary

Phase 186A adds deterministic, fixture-backed adapters for Phase 185A market and FX
contracts. Providers are **OFFLINE_CERTIFICATION_ONLY**. They prove parsing,
provenance, freshness, quality, fee/slippage estimation, and ExecutionGate DI
compatibility without authorizing live trading or contacting brokers.

Phase **186A-R1** hardens determinism and evidence custody: immutable per-result
conversion provenance, explicit identity conversion, canonical evidence hashes,
inclusive freshness cutoffs, triangulation integrity, composite hash custody, and
fixture-root restriction.

## 2. Existing provider audit

| Component | Status | I/O | Provenance | Freshness | Reuse |
|---|---|---|---|---|---|
| `backend/app/market/*` (185A) | **active** | contracts / unavailable defaults | yes | status fields | **reuse** — authoritative contracts |
| `backend/app/risk/live_microstructure_provider.py` | **active** | AntiBleed bridge | partial | via snapshot | **extend** — keep default unavailable |
| `backend/app/fx_daily_rates.py` | **active** (credit limits) | local JSON FX; same-ccy returns 1.0 | partial | date as_of | **do not reuse for pilot CAD** — silent 1.0 forbidden for missing rates |
| `backend/runtime/oanda_live_read_only_adapter.py` | **active** network | live HTTP | partial | operational | **do not reuse offline** |
| `backend/app/brokers/oanda_adapter.py` | **active** | broker I/O | partial | n/a | **avoid duplication** |
| Coinbase quote paths | **active** network | live | partial | partial | **avoid offline** |

## 3. Non-duplication decisions

- Reuse Phase 185A contracts; extend with optional provenance/hash fields.
- Do not wire `fx_daily_rates.get_fx_rate` into pilot conversion.
- Do not call OANDA/Coinbase HTTP adapters from Phase 186A providers.

## 4. OANDA fixture adapter

`OandaFixtureMarketProvider` reads local JSON only under an approved fixture root.
Computes mid/spread/spread_bps. Rejects non-positive prices, ask < bid, missing
timestamps, unsupported instruments, stale/future quotes. Emits `evidence_hash`.

## 5. FX conversion adapter

`FixtureFXConversionProvider` returns immutable `FXConversionQuote` objects that
carry per-result provenance (`conversion_path`, `path_type`, contributing rate /
provider IDs / timestamps, `evidence_hash`). Mutable `last_conversion_path` is not
used for evidence custody.

## 6. Direct / inverse / triangulated / identity rules

1. **IDENTITY** when `base == quote`: rate = 1 exactly; path_type = IDENTITY;
   quality = GOVERNED_IDENTITY; no fixture rate required; never used when currencies differ.
2. **DIRECT** pair if present and fresh.
3. Else **INVERSE** of opposite pair if present and fresh.
4. Else **TRIANGULATED** via configured hub (exactly two legs); both legs fresh;
   timestamps within governed window; quality = weakest leg; contradictory duplicate
   rates fail closed at load; no arbitrary graph search.
5. Else `NOT_AVAILABLE` with `fail_reason` on the result object.

Missing cross-currency rates never become 1.

## 7. Fee model

Instrument-scoped fixture `fee_bps` with model id/version and `evidence_hash`.
Insufficient facts → `NOT_AVAILABLE`.

## 8. Slippage model

Instrument-scoped `slippage_bps` with `evidence_hash`. Zero forbidden unless
`allow_zero=true`.

## 9. Composite provider (localized, non-AntiBleed)

`OfflineCertificationMicrostructureProvider` requires usable snapshot/fee/slippage,
matching instrument scope, expected_move_bps **and** non-empty
`expected_move_provenance`, and valid component hashes. It returns an immutable
`OfflineMicrostructureResult` whose `inputs` are
`OfflineCertificationQuoteFacts` — a **passive diagnostic bundle** of four
numbers (`expected_move_bps`, `fee_bps`, `spread_bps`, `slippage_bps`).

That object is **not** `LiveMicrostructureInputs` and **not** AntiBleedGuard.
The historical `backend.app.risk.live_microstructure_provider` AntiBleed bridge
was **not recovered**. Default runtime providers remain unavailable. Not
auto-wired into ExecutionGate or mobile live paths.

## 10. Freshness and quality rules

**Inclusive cutoff:** `age_seconds <= max_age_seconds` → FRESH; `>` → STALE;
`< 0` → FUTURE (fail-closed). Missing timestamps fail closed. Timezone-offset
equivalents normalize to UTC. No undocumented wall-clock reliance in deterministic
tests (caller supplies `evaluation_time`).

## 11. Provenance, versioning, and canonical hashing

Canonical SHA-256 evidence hashes cover schema/model versions, provider identity,
instrument/currency scope, source timestamps, freshness/quality/status, conversion
path, and contributing fixture facts. Evaluation-only wall-clock is excluded when
tests pin `evaluation_time`.

## 12. ExecutionGate dependency-injection boundary

Optional kwargs: `market_snapshot`, `fx_conversion`, `offline_provider_diagnostics`.
Production defaults remain unavailable. Gate order unchanged. AntiBleed first.

## 13. Failure modes

Malformed, crossed, stale, future, unsupported instrument, missing FX legs,
timestamp inconsistency, contradictory rates, insufficient fee/slippage facts,
missing expected-move provenance, fixture path traversal → fail-closed.

## 14. Security and fixture controls

Fixtures under `tests/fixtures/phase186a/` are synthetic. Adapters may read only
the approved fixture root (`phase186a` or an explicit `approved_root`). Path
traversal outside that root fails closed. No credentials, account IDs, tokens, or
live artifacts. Static tests reject network/credential/order-adapter imports.

## 15. Test evidence

`tests/test_phase186a_certified_offline_provider_adapters.py` plus Phase 184A/185A
regression suites.

## 16. Remaining online-certification requirements

Certified live quote/FX providers, broker auth TTL, OANDA LIVE readiness, founder
GO/NO-GO, freeze SHA — out of scope.

## 17. OFFLINE_CERTIFICATION_ONLY

Providers in this phase are **OFFLINE_CERTIFICATION_ONLY**. Offline certification
does **not** imply broker or live certification.

## 18. Live trading remains unauthorized

This phase does **not** authorize live trading, broker contact, or freeze designation.
