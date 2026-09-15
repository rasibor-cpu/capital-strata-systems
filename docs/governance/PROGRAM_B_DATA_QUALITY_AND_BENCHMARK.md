# CSS Enterprise Program B — Data Quality & Benchmark Comparison

## Status

IMPLEMENTED — RESEARCH/SHADOW ONLY

## Purpose

This increment closes two Program B gaps:

1. canonical dataset-quality evidence;
2. deterministic benchmark comparison.

## Dataset quality controls

Research datasets now have an explicit evidence contract covering:

- dataset/source identity;
- row-count sufficiency;
- required columns;
- missing-value count;
- duplicate timestamp count;
- monotonic timestamp order;
- UTC declaration and observation bounds;
- freshness;
- SHA-256 integrity.

Quality decisions are fail-closed and return a deterministic 0-100 evidence
quality score. A failed dataset is not approved for research certification.

## Benchmark comparison

Strategy evidence can now be compared deterministically against a benchmark on:

- total return;
- Sharpe ratio;
- maximum drawdown.

The comparison reports excess return, Sharpe spread, and drawdown difference.
A strategy is marked `OUTPERFORM` only when it satisfies the configured policy.

## Safety boundary

These modules are analytics/evidence only. They do not:

- place or cancel orders;
- alter broker state;
- allocate real capital;
- authorize live trading;
- move money;
- bypass the canonical CSS gates.

## Next Program B gaps

1. actual correlation/concentration analytics;
2. Monte Carlo outcome simulation;
3. experiment registry and research approval workflow;
4. consolidated institutional research package/export.
