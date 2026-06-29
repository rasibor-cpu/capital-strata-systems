# Phase 134B Confidence Calibration

## Purpose

Phase 134B introduces deterministic confidence calibration and recommendation drift analysis for advisory portfolio recommendations.

This phase does not add machine learning, automatic execution, broker integration, live trading capability, or governance changes.

## Calibration Methodology

The confidence calibration engine groups evaluated recommendations into confidence buckets. For each bucket it compares:

- expected confidence
- actual recommendation accuracy
- average subsequent performance
- calibration gap

The overall calibration score is calculated from the weighted gap between expected confidence and actual accuracy. The engine classifies confidence as:

- `OPTIMISTIC` when confidence materially exceeds observed accuracy
- `PESSIMISTIC` when observed accuracy materially exceeds confidence
- `WELL_CALIBRATED` when the two are aligned

## Drift Detection

The drift analyzer evaluates recommendation sequences for:

- recommendation instability
- excessive oscillation
- policy drift
- regime drift
- recommendation reversals

It produces a drift score, severity, stability estimate, and recommended monitoring action.

## Advisory-Only Operation

Calibration and drift outputs are dashboard and API evidence only. They do not modify recommendation generation, portfolio allocation, trade gates, Runtime Supervisor decisions, broker execution, or Capital Governor behavior.

## Limitations

Calibration quality depends on evaluated recommendation history. Sparse history returns `DATA UNAVAILABLE`. Drift detection identifies sequence instability but does not determine whether the changing recommendations were operationally inappropriate.

## Future Machine-Learning Opportunities

Future offline research may evaluate model-assisted calibration, probability reliability curves, or regime-specific confidence adjustment. These opportunities are discussion-only in Phase 134B and must not be connected to execution without separate governance approval.
