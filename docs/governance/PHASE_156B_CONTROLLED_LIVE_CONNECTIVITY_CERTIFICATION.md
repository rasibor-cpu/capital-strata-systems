# Phase 156B - Controlled Live Connectivity Certification

## Purpose

Phase 156B adds a reusable advisory certifier for controlled live broker
connectivity. It extends Phase 156A by performing deeper read-only operational
checks after Phase 156A has already passed.

This phase certifies operational connectivity only. It never certifies live
execution authority.

## Validation Sequence

The certifier in `backend/runtime/live_connectivity_certifier.py` follows this
sequence:

1. Invoke Phase 156A live broker readiness validation.
2. Fail closed immediately unless Phase 156A returns `GREEN`.
3. Bootstrap the configured broker adapter through the existing broker
   bootstrap path.
4. Authenticate using read-only probes and measure authentication latency.
5. Retrieve account information.
6. Retrieve live market data for canonical instruments.
7. Analyze latency against configurable thresholds.
8. Compute a 0-100 connectivity score.
9. Verify execution remains blocked by firewall and authority controls.
10. Return a `GREEN`, `AMBER`, or `RED` advisory certification report.

## Broker Read Checks

OANDA account validation confirms:

- Account ID
- Alias
- Currency
- Balance
- NAV
- Margin Available

OANDA market data validation checks:

- `EUR_USD`
- `USD_JPY`

Coinbase account validation confirms:

- Portfolio
- Wallet list
- Asset balances
- Portfolio value

Coinbase market data validation checks:

- `BTC-USD`
- `ETH-USD`

All checks are read-only.

## Connectivity Scoring

The score is computed from:

- Phase 156A credential and readiness health
- Authentication success
- Account retrieval success
- Market data retrieval success
- Execution firewall state
- Latency status

The default maximum score is 100. A low score does not authorize or deny
trading; it only classifies operational connectivity for review.

## Latency Scoring

The certifier captures:

- `authentication_ms`
- `account_ms`
- `market_data_ms`
- `overall_ms`

Latency is classified as:

- `GREEN` when all timings are within the configured green thresholds
- `AMBER` when connectivity works but exceeds green thresholds
- `RED` when timings exceed amber thresholds or required latency evidence is
  unavailable

Thresholds are configurable through `ConnectivityLatencyThresholds`.

## Firewall Verification

Phase 156B verifies that:

- `execution_allowed == false`
- `live_trading_blocked == true`
- `broker_execution_armed == false`
- live execution authority is not granted
- the existing execution boundary remains active

If execution authority is granted, the certification fails closed to `RED`.

## Relationship To Existing Controls

Phase 156A remains the prerequisite live broker readiness validation. Phase
156B stops immediately when Phase 156A is not `GREEN`.

Broker bootstrap remains authoritative for adapter construction. Phase 156B
does not replace or bypass broker startup selection, credential loading, or
adapter registration.

Broker readiness remains the canonical dashboard/readiness framework. Phase
156B produces a connectivity certification report for controlled operational
review.

The execution firewall, execution boundary validation, RBAC, NO-GO protections,
and R7 governance remain authoritative for live execution decisions. Phase 156B
only verifies that those protections are still blocking execution.

## Safety Guarantees

Phase 156B must never:

- submit orders
- cancel orders
- modify broker state
- arm execution
- enable live trading
- bypass the execution firewall
- change account balances

Every report remains advisory-only and returns:

- `advisory_only: true`
- `execution_allowed: false`
- `live_trading_blocked: true`
- `broker_execution_armed: false`

`GREEN` means operational connectivity passed read-only certification. It does
not authorize live execution.
