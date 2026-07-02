# Phase 140B Trade Summary Dashboard Restoration

Phase 140B restores a compact Trade Summary for desktop and mobile dashboards.

The summary includes date/time, mode, broker, engine mode, account balance, equity, open positions, realized PnL, unrealized PnL, last cycle/update, and execution status.

Canonical dashboard artifacts are preferred through the frontend contract. Missing values render as `DATA UNAVAILABLE`.

Read-only API:

- `GET /api/v1/trade-summary`
- `GET /api/trade-summary` on the authenticated mobile surface

This phase is display-only and exposes no live-trading action.
