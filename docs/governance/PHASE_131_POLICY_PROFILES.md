# Phase 131 Policy Profiles

## Purpose

Phase 131 adds institutional advisory policy profiles. Profiles define risk constraints that can be used by later governance and portfolio review layers.

## Profiles

Supported profiles:

- `CONSERVATIVE`
- `BALANCED`
- `GROWTH`
- `CAPITAL_PRESERVATION`
- `HIGH_CONVICTION`

Each profile defines:

- max drawdown tolerance
- concentration limit
- minimum cash reserve
- max risk budget utilization
- allocation bias
- allowed recommendation ceiling

## Fail-Safe Default

Unknown or missing profile names default to `CAPITAL_PRESERVATION`. This prevents accidental permissive behavior.

## Advisory-Only Design

Policy profiles are constraints and evidence for advisory review. They do not enforce broker execution, change allocations, arm live trading, or bypass any CSS risk authority.

## Relationship To Phase 129D And Phase 130

Phase 131 profiles are designed to be usable by Portfolio Risk Committee and Adaptive Portfolio Management in later phases. In this phase they are exposed as advisory profile metadata only.

## Future Path

Policy profiles may support supervised automation after explicit governance approval. Phase 131 deliberately stops at advisory visibility and deterministic profile lookup.
