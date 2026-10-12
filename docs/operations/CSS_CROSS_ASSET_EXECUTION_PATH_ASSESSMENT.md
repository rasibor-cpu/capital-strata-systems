# CSS cross-asset pilot — execution-path readiness assessment

Status: **ENGINEERING REVIEW COMPLETE FOR INSPECTED MODULES; LIVE CROSS-ASSET CERTIFICATION NOT MET**.

Candidate review branch: `governance/cad20-cross-asset-pilot-closeout` (PR #106, layered on draft PR #105). This is an engineering assessment from source inspection and previously supplied local test results, **not** an executed broker-system test.

## Verified implemented constraints
- `backend/config/order_limit_config.py` defaults: `live_pilot_max_position_cad=20.00`, `live_pilot_max_total_cad=40.00`, `live_pilot_max_concurrent_positions=2`, `live_pilot_daily_loss_cad=2.00`, `live_pilot_session_loss_cad=4.00`, `live_pilot_max_orders_per_session=10`. Validation caps are present.
- `backend/runtime/pilot_portfolio_limit.py` evaluates *caller-provided CAD amounts plus estimated CAD fees* against parent/concurrent/aggregate caps. It is an evaluator, not proof that upstream instrument values are trustworthy or that execution uses it.
- `backend/runtime/pilot_exposure_reservation.py` uses SQLite `BEGIN IMMEDIATE` for atomic reservations of *caller-provided CAD amounts* and duplicate child-ID detection. It is not broker-verified accounting of actual contract exposure.
- `engine/execution/execution_gate.py` explicitly rejects pilot minimum-size exception when `notional_currency` is not `CAD`; the AntiBleed evaluation otherwise remains currency-agnostic. This does not implement automatic FX conversion or derivative multipliers.
- `backend/runtime/controlled_pilot_readiness.py` only aggregates supplied evidence and is non-executing.
- Owner-confirmed limits: CAD 20 order/parent; CAD 40 aggregate; 2 parent exposures; crypto, FX, futures, options in intended test scope. Asset specific tighter limits may follow.

## Asset-class certification matrix

| Asset class | Minimum risk data for an eligible live order | Assessment of inspected pilot path |
|---|---|---|
| Crypto spot | Quote asset, quote-to-CAD mid with timestamp/source, filled+open+fee commitment, size/lot minimum, no borrowing/leverage | **NOT CERTIFIED**: no evidence that quote-to-CAD normalization is mandatory before pilot reservation |
| FX | Base/quote/settlement currency, position units, contract multiplier, effective CAD notional, leverage and stop/liquidation/worst-case loss, margin and costs | **NOT CERTIFIED**: CAD converter, instrument-level leverage control and broker connector not demonstrated |
| Futures | Exchange, symbol/expiry, lot multiplier/tick value, contract notional in CAD, intraday/overnight margin, gap/liquidation exposure, loss bounds | **NOT CERTIFIED**: genuine CAD 20 maximum economic exposure unproven; standard contracts may be ineligible |
| Options | Underlying, call/put, strike/expiry, quantity, multiplier, premium, worst-case loss, assignment/margin, currency conversion, spread-leg atomicity | **NOT CERTIFIED**: defined-risk multi-leg accounting and max-loss/underlying equivalence unproven |

**No global asset-class activation** is supported by inspected evidence. Unavailable, stale, inconsistent or unbounded risk inputs must fail closed. Margin/premium paid is not a substitute for notional or max-loss assessment.

## Practical verification required before activation
1. Freeze exact code revision and actual runtime/broker account identifiers; confirm all four safety flags still fail closed.
2. Identify each exchange/broker route and instrument minimums. Perform **read-only**, credential-safe broker API metadata, positions, balances and permissions checks; no probe order.
3. Build auditable per-instrument CAD exposure and worst-case-loss normalization. Validate fees, pending/cancelled/partial fills, quote freshness, leverage and contract multipliers.
4. Prove all submit paths (including UI, bot, scheduler, recovery and manual) traverse reservation + R7 + AntiBleed + approval + global kill switch atomically; include concurrent orders and crash/restart tests.
5. Confirm designated independent release reviewer has enrolled signing key and has actually signed candidate independently from sponsor; Diana's acceptance of role is not an approval signature. Ehis is an alternative *candidate* reviewer but not registered in the current one-holder role registry.
6. Validate release and genuine 72h operational evidence. Owner's schedule decision to proceed is not an endurance PASS.
7. No deployment or real-money orders until independent certification passes.

## Existing regression evidence
- Isolated Windows candidate `7b527d24`: 105 pass, 1 skip (extended targeted selection).
- Additional overlapping focused selection: 56 pass, 1 skip, no failures.
- Neither run is a complete broker integration, asset-class qualification or 72-hour wall-clock certifier.

**Decision: engineering closeout preparation GO; live real-money execution NO-GO.**
