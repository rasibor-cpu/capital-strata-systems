# Phase 131 Recommendation Learning

## Purpose

Phase 131 adds advisory recommendation tracking and advisory history persistence. These components record recommendations and later outcome proxies so CSS can evaluate whether advisory guidance would have improved outcomes.

## Advisory-Only Design

Recommendation tracking and advisory history do not make trading decisions. They do not execute trades, change allocations, alter risk gates, or arm live trading.

The tracker can:

- record recommendation snapshots
- compare recommendations against later outcomes
- compute hit rate
- compute avoided loss proxy
- compute missed opportunity proxy
- summarize stored recommendations

The advisory history store can:

- append advisory decisions
- list recent decisions
- summarize recommendation counts
- recover safely from missing or corrupt JSON files

## Persistence Boundary

Persistence is scoped to `artifacts/portfolio/`. Dashboard and API summary endpoints read existing records and do not append new recommendations as a side effect of page views.

## Data Insufficiency Handling

Missing or corrupt files are treated as empty history. Malformed records are ignored. This keeps the learning layer fail-closed and non-disruptive.

## Relationship To Phase 129D And Phase 130

Phase 131 can store advisory outputs from Portfolio Intelligence, Capital Rotation, Adaptive Portfolio Management, and Portfolio Risk Committee review. It does not change how those phases compute recommendations.

## Future Path

The learning layer can support supervised review of recommendation quality in future phases. It does not currently feed decisions back into broker execution or automated trading authority.
