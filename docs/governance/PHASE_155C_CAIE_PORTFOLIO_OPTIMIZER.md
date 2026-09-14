# Phase 155C — CAIE Portfolio Optimizer Shadow Layer

## Status

IMPLEMENTED — SHADOW ONLY

## Purpose

Phase 155C ranks validated/scored opportunities and proposes a portfolio-level
capital plan without changing runtime execution.

## Controls

The optimizer:

- never allocates more than available capital;
- respects configured asset-class caps;
- respects configured broker caps;
- caps single-opportunity concentration;
- ranks higher-scored opportunities first;
- may retain cash when opportunities are unattractive;
- defaults unknown asset/broker caps to zero allocation.

## Safety

The output is a shadow plan only. It has no broker submission path and does not
modify existing capital, trade-gate, margin, broker, or execution authority.

`status=SHADOW_ONLY` is invariant.

## Phase boundary

This phase does not integrate into the runtime, write learning outcomes, expose
dashboard/API state, or promote CAIE beyond shadow mode. Those remain later
Phase 155 sub-phases.
