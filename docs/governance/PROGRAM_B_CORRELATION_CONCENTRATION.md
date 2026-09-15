# CSS Enterprise Program B — Correlation & Hidden Concentration Analytics

## Status

IMPLEMENTED — RESEARCH/SHADOW ONLY

## Purpose

This increment converts the previously documented Phase 91 correlation
architecture into deterministic research calculations.

## Implemented

- Decimal-based Pearson correlation;
- deterministic pairwise correlation matrix output;
- institutional relationship classification:
  - STRONGLY_POSITIVE
  - POSITIVE
  - NEUTRAL
  - NEGATIVE
  - STRONGLY_NEGATIVE
- hidden concentration detection using both positive-correlation and portfolio
  weight thresholds;
- moderate/high concentration severity;
- fail-closed validation for mismatched series, zero variance, invalid
  thresholds, and invalid portfolio weights.

## Safety boundary

Correlation analytics are research evidence only. They do not alter:

- trade eligibility;
- capital governor decisions;
- broker execution;
- order routing;
- money movement;
- live-trading authorization.

Existing CSS governance remains authoritative.

## Next Program B gaps

1. Monte Carlo outcome simulation;
2. experiment registry and research approval workflow;
3. consolidated institutional research package/export.
