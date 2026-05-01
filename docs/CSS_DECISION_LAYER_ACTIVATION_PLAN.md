# CSS Decision Layer Activation Plan

## Status

The PCNRASS-safe decision helper layer has been added to:

`backend/intelligence/trade_decision_orchestrator.py`

Current helper functions:

- compute_css_decision_score()
- get_css_mode_threshold()
- css_trade_gate()

## Purpose

This layer standardizes CSS trade conviction scoring before live integration.

## Activation Rule

The decision layer must only be wired into the orchestrator after confirming the existing pipeline already produces or can safely derive:

- VWAP edge
- Momentum
- Pressure
- Liquidity score
- Regime alignment
- Estimated execution cost

## PCNRASS Constraints

Do not modify:

- Login/authentication
- Dashboard rendering
- Broker adapters
- PnL engine
- Existing trade execution path

## Safe Integration Path

1. Read existing signal values from the orchestrator pipeline.
2. Normalize each signal to a 0–100 scale.
3. Pass values into compute_css_decision_score().
4. Compare result against get_css_mode_threshold(mode).
5. Use css_trade_gate() as an additional confirmation gate.
6. Preserve the old decision result as fallback.
7. Log both old score and new CSS decision score for comparison.

## Non-Regression Rule

Until fully tested, the new decision layer must run in observer mode only.

Observer mode means:

- Calculate CSS score
- Display/log CSS score
- Do not block or force trades yet

## Next Laptop Task

Implement observer-mode wiring first.

Only after successful testing should the CSS decision gate become active.
