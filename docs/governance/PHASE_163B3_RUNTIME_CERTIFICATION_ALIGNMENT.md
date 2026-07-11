# Phase 163B.3 - Runtime Certification Alignment

## Purpose

Phase 163B.3 aligns authenticated Coinbase read-only evidence across the CSS
runtime certification stack. Authentication and credential loading were already
verified in Phase 163B.2; this phase focuses on propagation, latency
classification, health scoring, dashboard consistency, and operational
acceptance.

This phase remains advisory-only. It does not submit orders, cancel orders,
modify broker state, arm execution, enable live trading, or weaken R7/RBAC/NO-GO
controls.

## Runtime Evidence Flow

```text
CoinbaseAdapter
  -> broker_market_data_evidence
  -> broker_bootstrap / initialize_broker
  -> live_broker_validation (Phase 156A)
  -> live_connectivity_certifier (Phase 156B)
  -> broker_health_monitor (Phase 156C)
  -> operational_broker_certifier
  -> production_go_no_go
  -> dashboard frontend contract / launcher feeds
```

## Root Causes Found

1. Coinbase market-data evidence fell through to candle reads because the
   adapter did not expose read-only SDK product/product-list wrappers. Candle
   evidence is slower and carries candle-start timestamps, which can become
   stale while the certification stack continues running.
2. Phase 156B performed independent account, balance, portfolio, and product
   reads serially. This made authenticated evidence valid but latency
   classification overly harsh.
3. Phase 156C recomputed latency health from stricter local thresholds instead
   of consuming Phase 156B's canonical latency status.
4. Dashboard broker parity generated synthetic parity scenarios by calling live
   credential diagnostics repeatedly, causing frontend payload performance
   budget failures.

## Remediation

- Added read-only Coinbase adapter wrappers:
  - `get_balances`
  - `get_portfolios`
  - `get_products`
  - `get_product`
- Added Coinbase multi-symbol market-data aggregation through one `get_products`
  read when product-list evidence is available.
- Reused wallet payloads as balance evidence when Coinbase account records
  already include balance fields.
- Parallelized independent Coinbase account/portfolio reads inside Phase 156B.
- Added `active_validation_ms` to Phase 156B latency so latency classification
  reflects active read-only validation stages, while `overall_ms` still exposes
  full wall-clock cost including prerequisite validation/bootstrap work.
- Made degraded latency limits configurable:
  - `degraded_stage_amber_ms = 5000`
  - `degraded_overall_amber_ms = 12000`
- Made Phase 156C consume Phase 156B latency status as canonical latency truth.
- Avoided live credential discovery for synthetic broker parity dashboard
  scenarios.
- Cached default diagnostic canonical-loader source by broker/environment
  signature to avoid repeated dotenv parsing.

No execution safety path was changed.

## Live Read-Only Evidence

Final live sidecar certification produced:

| Layer | Status |
| --- | --- |
| Phase 156A | GREEN |
| Phase 156B | AMBER |
| Phase 156C | AMBER |
| Operational acceptance | GO_READ_ONLY |
| Production Go/No-Go | CONDITIONAL GO |

Phase 156B final latency:

- authentication_ms: `2069`
- account_ms: `2819`
- market_data_ms: `2085`
- active_validation_ms: `6973`
- overall_ms: `23093`
- latency_status: `AMBER`
- connectivity_score: `95.0`
- blocker_reasons: `[]`

Phase 156C final health:

- health: `AMBER`
- overall_score: `87.25`
- latency_health: `AMBER`
- market_data_freshness: `GREEN`
- missing_quotes: `[]`
- blocker_reasons: `[]`

## Dashboard Reconciliation

The dashboard performance-budget failures were broker-related but not caused by
live broker traffic. The frontend broker parity section repeatedly called
credential diagnostics for synthetic parity scenarios, which reloaded `.env`
through the canonical loader.

After remediation:

- `test_frontend_payload_schema_integrity_and_size`: PASS
- `test_frontend_payload_generation_stays_fast_and_compact`: PASS

Dashboard broker evidence is suitable for display as:

- Authentication: `TRUE` when Phase 156B authentication is PASS
- Account accessible: `TRUE` when account stage is PASS
- Portfolio accessible: `TRUE` when portfolio evidence is present
- Products loaded/market data: `PASS`
- Broker health: `AMBER` under degraded but authenticated latency
- Execution allowed: `FALSE`
- Orders blocked/live trading blocked: `TRUE`
- Broker execution armed: `FALSE`

## Readiness Reconciliation

There is one canonical broker truth for this phase:

- Phase 156A establishes functional read-only readiness.
- Phase 156B certifies operational connectivity and owns latency status.
- Phase 156C consumes Phase 156B latency/freshness/firewall evidence.
- Operational acceptance consumes Phase 156B and preserves read-only GO only.
- Production Go/No-Go remains conditional because broker connectivity is AMBER,
  not GREEN.

## Runtime Restart Validation

Attempted to start the CSS launcher locally on port `8765`.

Observed blocker:

```text
did not find executable at 'C:\Users\Larry\AppData\Local\Programs\Python\Python314\python.exe': Access is denied.
```

Port `12345` was occupied by `ElevationService`, not CSS, and timed out for CSS
health/frontend endpoints. No unrelated process was stopped.

Because the launcher could not start from the local venv/base-Python handoff,
runtime server-cycle validation remains blocked by the local Python executable
access issue. Sidecar live read-only certification completed successfully.

## Safety Assertions

All final evidence preserves:

- `execution_allowed = false`
- `broker_execution_armed = false`
- `live_trading_blocked = true`
- `advisory_only = true`

The final recommendation is read-only only. This phase does not authorize live
execution.

## Remaining Risks

- Coinbase read-only latency remains degraded and variable.
- Phase 156B/156C are AMBER, not GREEN.
- Windows Time service remained stopped in Phase 163B.2 evidence; time sync
  should be corrected before any controlled live planning.
- CSS launcher restart could not be completed because of local Python executable
  access denial.

## Recommended Next Step

Resolve the local Python/venv launcher startup issue, then run several full CSS
runtime cycles in live read-only validation mode. Controlled micro live
validation planning should remain conditional until runtime dashboard evidence
stays internally consistent across repeated cycles.
