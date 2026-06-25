# CSS M3D - Trade Ticket Layout and Auto-Populated Order Fields

## Objective
Rearrange Trade tab ticket fields into the required order and pre-populate selectable fields from canonical universe plus opportunity context.

## Required Order Implemented
1. Instrument / Asset Class (`trade-asset-class`)
2. Symbol (`trade-symbol`)
3. Side (`trade-side`)
4. Tenor / Expiry (`trade-tenor`)
5. Price (`trade-price`)
6. Quantity (`trade-quantity`)

## Behavior Implemented
- Asset class dropdown drives symbol filtering by selected class.
- Symbol dropdown is pre-populated on server render and refreshed client-side from canonical grouped universe.
- Side defaults from opportunity recommendation when available; otherwise BUY.
- Tenor/Expiry shown and required for OPTIONS/FUTURES only.
  - OPTIONS default: `NEXT_MONTH`
  - FUTURES default: `FRONT`
- Price pre-populates from opportunity summary suggested price when available; otherwise blank with `MARKET` status.
- Quantity pre-populates from suggested quantity; fallback to canonical `min_order_size`; final fallback `1`.
- Top opportunity Use action populates all ticket fields without execution.
- Decision panel refreshes on asset/symbol selection.
- No selection action executes trade requests.

## Server-Side Fallback
First render includes complete ticket controls and values:
- asset class dropdown
- symbol dropdown
- side dropdown
- tenor/expiry control
- price input
- quantity input

## Safety Constraints Preserved
- No auto-submission.
- No RBAC bypass.
- No paper/live control bypass.
- No risk-gate bypass.
- No broker execution permission changes.
