# CSS Enterprise Program B — Experiment Tracking & Research Approval

## Status

IMPLEMENTED — RESEARCH GOVERNANCE ONLY

## Purpose

This increment adds a canonical experiment record and research-approval record
so research results can be traced back to a hypothesis, dataset, parameters,
owner, and code reference.

## Experiment evidence

Each experiment records:

- experiment ID;
- strategy ID;
- hypothesis;
- owner;
- dataset ID;
- deterministic parameter snapshot;
- UTC creation time;
- code reference.

## Research approval

Authorized research/risk/admin reviewers may issue one of:

- APPROVED_SHADOW
- CHANGES_REQUIRED
- REJECTED

Approval cannot predate the experiment and requires rationale.

## Safety boundary

Research approval is not trading authority.

Even `APPROVED_SHADOW`:

- does not authorize live trading;
- does not arm broker execution;
- does not permit order submission;
- does not permit money movement;
- does not bypass strategy certification, capital, risk, margin, broker, or
  execution gates.

The helper `approval_allows_live_trading()` is deliberately hard-false.

## Next Program B gap

Consolidated institutional research package/export and Program B closeout.
