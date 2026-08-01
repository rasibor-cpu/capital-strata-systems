# PHASE 185A — Live Market Data and FX Conversion Framework

## Status

Framework contracts and provider interfaces on `css-rc-live-001-candidate`.

**Does not authorize live trading.**

**Does not connect to brokers.**

**Does not fetch live market data.**

**Does not weaken fail-closed behaviour.**

Missing information continues to produce `NOT_AVAILABLE` / `UNKNOWN`.

## Purpose

Provide the authoritative contracts that future certified providers will use to supply:

- live microstructure inputs (bid/ask/mid/spread/fee/slippage)
- deterministic FX conversion
- currency normalization
- spread / fee / slippage estimation surfaces

These contracts support AntiBleed, ExecutionGate, Phase 152A, Margin, RiskGovernor,
and portfolio reporting **without** granting execution authority.

## Contracts

### LiveMarketSnapshot

Immutable snapshot fields:

`bid`, `ask`, `mid`, `spread`, `spread_bps`, `estimated_slippage`, `estimated_fee`,
`currency`, `quote_timestamp`, `provider`, `provider_version`, `quality`,
`freshness`, `status`

Default factory: `LiveMarketSnapshot.not_available()`.

### FXConversionQuote

Immutable conversion fields:

`base_currency`, `quote_currency`, `rate`, `timestamp`, `provider`,
`provider_version`, `quality`, `status`

- No online lookup inside this framework.
- `convert(amount)` returns `None` when status/quality/rate are not usable.
- `UNKNOWN` and `NOT_AVAILABLE` remain fail-closed.
- Currency normalization helper returns `None` for missing/`UNKNOWN` codes.

## Provider Model

Interfaces only (Phase 185A):

| Interface | Default behaviour |
|---|---|
| `MarketSnapshotProvider` | `NOT_AVAILABLE` |
| `FXConversionProvider` | `NOT_AVAILABLE` |
| `FeeModelProvider` | `NOT_AVAILABLE` |
| `SlippageProvider` | `NOT_AVAILABLE` |

No certified implementations ship in this phase.

## Freshness and Quality

- `freshness` is an audit field; unavailable snapshots use `NOT_AVAILABLE`.
- `quality` defaults to `UNKNOWN` until a provider is certified.
- `is_usable()` requires `status == AVAILABLE` and non-UNKNOWN quality.

## Provider Certification (future)

A provider may become eligible for certification only after a separate governed phase that includes:

1. Explicit founder approval
2. Deterministic offline fixtures (no live broker dependence for unit proof)
3. Freshness/staleness policy
4. Fail-closed proofs for missing/stale/unknown quotes
5. Explicit non-authorization of live trading until broader LDT blockers clear

## Fail-Closed Philosophy

- Absence of snapshot/FX → diagnostics `NOT_AVAILABLE`, no invented numbers
- AntiBleed bridge returns `None` unless snapshot + fee + slippage are usable **and**
  an explicit `expected_move_bps` is supplied in governed context
- ExecutionGate order unchanged: AntiBleed → Margin → pricing → compounding → sizing → RiskGovernor
- Market/FX payloads are consumed for diagnostics only in this phase
- Live authority AND-gates remain intact (`anti_bleed_guard_pass` still required)

## AntiBleed Integration

`backend/app/risk/live_microstructure_provider.py` now exposes:

- `UnavailableLiveMicrostructureProvider` (default; returns `None`)
- `MarketFrameworkMicrostructureProvider` (bridge to 185A interfaces; still fail-closed by default)

Mobile live path continues using the unavailable default unless a future phase
wires a certified provider.

## ExecutionGate Integration

Optional kwargs:

- `market_snapshot`
- `fx_conversion`

Recorded in `debug` identity fields only. Do not reorder gates. Do not authorize.

## Phase 152A Interaction

Phase 152A CAD 20 capital/position/loss/concurrency limits are **unchanged**.
FX conversion is required for future CAD normalization proofs; until a certified
FX provider exists, FX remains `NOT_AVAILABLE` (LDT FX blocker stands).

## Future Approved Providers

Examples (not implemented here):

- Certified OANDA practice quote snapshot provider
- Offline CSV/fixture FX rate provider for CAD normalization tests
- Broker fee schedule model with explicit version pins

Each requires a superseding phase and certification evidence.

## Non-Goals

- No live trading authorization
- No broker connectivity
- No dependency installs
- No CSS restart
- No freeze SHA designation
- No weakening of AntiBleed, Margin, RiskGovernor, kill switch, or live authority
