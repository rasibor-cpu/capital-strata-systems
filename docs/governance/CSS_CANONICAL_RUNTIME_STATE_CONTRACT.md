# CSS Canonical Runtime State Contract

Date: 2026-05-28
Workstream: Item 4/22 — Canonical runtime state finalization
Status: Contract lock / implementation gate
Mode: PCNRASS-safe, documentation-first

## Purpose

This document establishes the canonical runtime state contract for Capital Strata Systems (CSS). It is intended to prevent runtime drift between backend intelligence, broker state, accounting/PnL, governance, execution, and dashboard rendering.

The goal is not to add another parallel state object. The goal is to define one authoritative ownership map so future code changes converge instead of creating duplicate state paths.

## Current discovery summary

Phone-side GitHub inspection confirmed runtime-state related surfaces around:

- `dashboard/runtime/dashboard_state.py`
- `dashboard/runtime/dashboard_state_factory.py`
- `dashboard/runtime/state_builders/*`
- `dashboard/runtime/summary_builders/*`
- `dashboard/runtime/api_bridge.py`
- `dashboard/runtime/ws_bridge.py`
- `dashboard/runtime/dashboard_renderer.py`
- `engine/risk/risk_state_store.py`
- `backend/governance/prop_runtime_state.py`

Recent PR inspection also showed analytics additions around:

- `dashboard/runtime/analytics_state_builder.py`
- `backend/analytics/cost_reality_engine.py`
- `backend/analytics/trade_outcome_analytics_engine.py`
- `backend/analytics/signal_quality_engine.py`
- dashboard/web references to an `analytics` payload section

## Runtime-state authority rule

CSS runtime state must be governed by this ownership hierarchy:

| Layer | Authority | May mutate? | Purpose |
|---|---|---:|---|
| Broker adapters | Broker truth | Yes, externally sourced | Balances, fills, order status, live account facts |
| Accounting/PnL engine | Financial truth | Yes | Realized/unrealized PnL, cost-adjusted results, ledger facts |
| Governance/risk engines | Permission truth | Yes | Allow/block, exposure limits, mode/session constraints |
| Orchestrator | Decision truth | Yes | Trade intent, lifecycle coordination, approved actions |
| Runtime state factory/builders | Aggregation truth | No direct trading mutation | Normalize authoritative inputs for dashboard/API |
| Dashboard/web renderer | Render truth only | No | Display only; never owns financial/execution truth |
| Analytics builders | Read-only insight | No | Summaries, diagnostics, edge/cost visibility |

## Canonical dashboard payload sections

The runtime payload exposed to dashboard/web/API should converge on these top-level sections:

| Section | Required role | Authority source |
|---|---|---|
| `session` | user/session/mode status | auth/session runtime |
| `broker` | selected broker, broker mode, connection and balance summary | broker bootstrap/adapters |
| `account` | cash, equity, buying power, margin-like values | broker + accounting normalization |
| `positions` | open positions and exposure | broker + orchestrator + accounting |
| `orders` | open/pending/recent orders | broker + execution controller |
| `execution` | recent executions, fills, lifecycle events | execution controller/orchestrator |
| `pnl` | realized/unrealized/net/cost-adjusted PnL | canonical PnL/accounting engine |
| `risk` | drawdown, exposure, caps, throttles | risk/governance engines |
| `governance` | allow/block status, policy mode, gate reasons | governance gate/controllers |
| `market` | normalized market scan/regime data | market state builders/intelligence |
| `opportunities` | ranked candidates and edge diagnostics | opportunity scoring/orchestrator |
| `analytics` | expectancy, profit factor, signal quality, cost estimates | read-only analytics builders |
| `health` | runtime heartbeat, stale-data flags, fail-closed state | runtime monitor/health checks |
| `audit` | trace IDs, cycle IDs, last validation state | audit/event log |

No dashboard code should require data hidden only inside `last_scan_results` if the web layer expects a top-level section. If a field is needed by the web renderer, it must be exposed through the canonical payload contract.

## Analytics payload rule

Analytics must remain read-only and must not gate, mutate, size, execute, or reconcile trades. If analytics results are used later for decisioning, that must be promoted explicitly into an intelligence/governance module with tests and audit coverage.

Expected canonical top-level analytics headline fields:

```text
analytics.expectancy
analytics.profit_factor
analytics.estimated_execution_cost
analytics.signal_quality
analytics.current_edge_estimate
analytics.drawdown_state
```

If analytics internals remain nested under `last_scan_results.analytics_summary`, a canonical adapter must lift the agreed headline fields to top-level `analytics` for dashboard/web consumption.

## PCNRASS implementation sequence

Before runtime code changes:

1. Confirm the authoritative branch and latest merged runtime files.
2. Compile all existing runtime files.
3. Map each builder and bridge to the canonical payload sections above.
4. Identify fields currently duplicated across `last_scan_results`, summary builders, payload adapters, and web expectations.
5. Add or update a single payload adapter that lifts normalized sections into the canonical shape.
6. Keep dashboard rendering read-only.
7. Add tests proving all top-level sections exist as dictionaries even when source inputs are missing.
8. Add tests proving analytics is available at top-level if the web app references `analytics.*` fields.
9. Run compile and smoke tests.
10. Commit only after PCNRASS validation passes.

## Non-regression rules

- Do not delete existing state builders until their replacement path is tested.
- Do not move financial truth into dashboard code.
- Do not let analytics become an execution gate without explicit governance review.
- Do not introduce a second PnL owner.
- Do not introduce broker-specific dashboard logic.
- Do not assume paper-mode capital when live broker mode is selected.
- Do not allow missing runtime sections to crash rendering; fail closed with safe defaults.

## Acceptance criteria for item 4 completion

Item 4 can be marked complete only when:

| Requirement | Completion standard |
|---|---|
| Canonical payload contract exists | This document or successor contract is present |
| Runtime ownership is mapped | Every major runtime field has an authority source |
| Dashboard is render-only | No execution/governance/accounting mutation in dashboard code |
| Analytics payload reconciled | Web-visible `analytics` section is explicitly produced |
| Builders are normalized | Missing inputs produce safe dictionary defaults |
| PnL source is canonical | PnL comes from accounting/PnL engine, not UI calculation |
| Governance source is canonical | Allow/block state comes from governance engines |
| Broker state is canonical | Live/paper broker state is normalized and visible |
| Tests pass | Compile and smoke tests pass locally or in CI |

## Immediate next coding task

Create or update a canonical runtime payload adapter that:

1. receives `DashboardState` or the existing runtime aggregation output;
2. emits the canonical top-level sections listed above;
3. lifts analytics headline values from `last_scan_results.analytics_summary.headline` into top-level `analytics`;
4. ensures every expected section is a dictionary;
5. never mutates broker, execution, accounting, or governance state.

## Current PCNRASS conclusion

Runtime state finalization is not yet fully complete, but the authority contract is now locked. The next safe step is implementation of the canonical payload adapter and corresponding tests from a full laptop/Codex environment.
