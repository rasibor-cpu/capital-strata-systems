# PHASE 177C — Multi-Broker Canonical Architecture (Revision B)

**Status:** Implemented (pending commit authorization)
**Date:** 2026-07-20
**Revision:** B — IBKR removed from roadmap; Binance added

---

## Approved Tier-1 registry

1. Coinbase — Primary Crypto Broker
2. Binance — Secondary Crypto Broker
3. OANDA — Primary FX Broker
4. Questrade — Primary Canadian Equities Broker

**Excluded from active roadmap:** Interactive Brokers (IBKR), Alpaca

---

## Architecture

Capability-advertising plugin registry (`backend/app/brokers/canonical_tier1.py`):

- Brokers declare capabilities; execution engine does not hard-code per-broker behaviour beyond registry lookup.
- Future brokers register as plugins under `backend/app/brokers/plugins/`.
- Execution advertisement is always `execution_enabled=false` / `order_submission=false` in this phase.

Supporting modules:

| Module | Role |
|--------|------|
| `contamination_isolation.py` | Cross-broker endpoint/credential/runtime field isolation |
| `live_read_only.py` | LIVE_READ_ONLY contract (auth/balances/positions/MD/products/health; no orders) |
| `backend/broker_reporting/` | Executive broker reports + enterprise paginated layout |

---

## LIVE_READ_ONLY

Restored as a first-class capability for all Tier-1 brokers.

Allowed: authenticate, load balances/positions/market data, synchronize products, refresh health/readiness.
Forbidden: submit/cancel/modify orders, arm execution, enable live trading.

---

## Contamination

`analyze_environment_contamination` / `analyze_runtime_state_contamination` detect:

- Foreign host tokens under another broker’s endpoint / API version keys
- Nested runtime fields mixing broker namespaces (e.g. Coinbase URL under OANDA path)
- Live-enable flags coexisting with sandbox/practice endpoints

Profile scrubbing in `broker_environment_profiles.py` now scopes keys per broker (Coinbase, OANDA, Binance, Questrade) and scrub foreign contaminated fields.

---

## Mission Control

Broker Management displays every Tier-1 broker with Role + Operational State, Readiness, Certification, Latency, Authentication, Market Data, Account, Execution, Last Sync.

IBKR row removed. PAPER remains a simulation lane when NONE/PAPER selected.

---

## Executive Reporting

`build_broker_executive_report_package` produces paginated documents (cover, executive summary, TOC, numbered pages) for browser/mobile/PDF-identical layout, including:

Broker Summary · Readiness · Health · Latency · Certification · Connection History · Account Summary · Market Data Summary · Contamination · LIVE_READ_ONLY contracts

Separate from Phase 178 financial arithmetic (`trading_impact=false`, no execution authority).

---

## Explicit non-goals / remaining work

- Phase 178B supersedes the placeholder behavior: Binance / Questrade now expose source-only structured operational adapters; execution remains blocked
- Full LIVE_READ_ONLY network validation against live Binance/Questrade accounts is a follow-on ops phase
- Historical `backend/brokers/ibkr/*` stubs left on disk but demoted from registry/startup/MC

---

## Safety

- Runtime Mode Resolver (177A) unchanged — fail-closed DISABLED when intent missing
- No broker capable of live execution via this phase
- Mission Control / Mobile remain advisory for broker controls
