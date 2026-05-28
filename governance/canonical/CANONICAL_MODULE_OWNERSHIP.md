# CSS Canonical Module Ownership

## Purpose
Defines the official ownership boundaries for CSS modules.

| Path | Authority |
|---|---|
| backend/runtime/ | Runtime lifecycle, cycles, state, orchestration |
| backend/governance/ | Risk, gates, permissions, policy, exposure |
| backend/accounting/ | Realized PnL, unrealized PnL, costs, reconciliation |
| backend/execution/ | Broker routing, adapters, fills, confirmations |
| backend/intelligence/ | Scanners, normalization, regime, scoring, analytics |
| dashboard/web/ | Render-only dashboard display |
| tests/ | Validation and non-regression authority |

## Rule
No module may assume authority belonging to another module without explicit governance approval.
