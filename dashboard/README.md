# CSS Dashboard Architecture

## Purpose

The CSS dashboard must become a disciplined rendering and runtime coordination layer.

It should not own trading logic, governance logic, broker logic, accounting logic, or risk logic.

## Core Principle

Modules compute.  
Adapters normalize.  
Summaries aggregate.  
Runtime coordinates.  
Rendering displays.

## Dashboard Folders

- `rendering/` — visual layout, tables, panels, display formatting
- `runtime/` — dashboard state, refresh cycles, runtime coordination
- `adapters/` — compatibility adapters between backend modules and dashboard payloads
- `summaries/` — aggregated PnL, risk, exposure, broker, and trade summaries
- `trade_warehouse/` — append-only categorized trade records and reports

## Required Future Runtime State Module

A dedicated dashboard runtime state module should be created:

`dashboard/runtime/dashboard_state.py`

This module should define the standard dashboard state payload.

## Dashboard State Fields

The dashboard state payload should eventually include:

- engine_mode
- broker_mode
- selected_broker
- live_or_paper
- mtm_enabled
- mtm_source
- mtm_frequency
- cycle_number
- session_id
- user_id
- role
- open_positions
- realized_pnl
- unrealized_pnl
- total_equity
- cash_balance
- risk_limits
- governance_status
- asset_class_summaries
- broker_status
- last_scan_results
- trade_warehouse_status
- audit_status

## Trade Warehouse Rule

The dashboard may render trade warehouse outputs, but it must not become the authority for trade records.

## Long-Term Target

The current `scripts/css_live_dashboard.py` should gradually shrink into a rendering shell that consumes structured outputs from backend modules.
## Market State Fields

The dashboard state payload should also include structured market-state outputs from intelligence modules:

- trend_state
- volatility_state
- liquidity_state
- mean_reversion_state
- probability_state
- velocity_state
- vwap_state
- vwap_distance
- vwap_elasticity
- momentum_state
- pressure_state
- acceleration_state
- regime_state
- spread_state
- execution_cost_state
- signal_confluence_state

## Rule

The dashboard must only render these values.

It must not calculate or override market-state decisions directly.