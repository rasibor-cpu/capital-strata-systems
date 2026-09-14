# Phase 155B — CAIE Scoring Engine

## Status

IMPLEMENTED — SHADOW ONLY

## Purpose

Phase 155B scores already validated CAIE opportunities using expected value,
confidence, risk, liquidity, regime alignment, and capital efficiency.

## Model

The engine calculates:

- expected value from win probability, expected return, and drawdown;
- a confidence bonus only when expected value is already positive;
- drawdown risk penalty;
- liquidity penalty;
- regime-alignment penalty;
- bounded return-to-risk capital-efficiency bonus.

All calculations use `Decimal`.

## Safety

The score is advisory only and returns `status=SHADOW_ONLY`.

The engine has no:

- order submission;
- broker execution route;
- transfer/withdrawal/deposit/funding path;
- client-fund authority;
- live-trading authorization.

A high score cannot bypass CSS risk, execution, broker, capital, margin, or
governance gates.

## Fail-closed behavior

The scorer revalidates the proposal before scoring. Invalid proposals raise a
validation error and receive no score.

## Phase boundary

This phase does not rank portfolios, allocate capital, integrate into runtime,
learn from outcomes, alter dashboards, or promote CAIE beyond shadow mode.
Those remain later Phase 155 sub-phases.
