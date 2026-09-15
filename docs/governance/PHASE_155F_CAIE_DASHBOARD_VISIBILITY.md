# Phase 155F — CAIE Dashboard/API Visibility

## Status

IMPLEMENTED — READ-ONLY SHADOW VISIBILITY

## API surface

CAIE shadow state is exposed at:

`GET /api/v1/caie-shadow`

The route reads only from the canonical DashboardState
`last_scan_results["caie_shadow"]` projection.

## Safe fallback

If no CAIE shadow artifact is available, the endpoint returns an explicit
`UNAVAILABLE / NO_CAIE_SHADOW_DATA` payload with an empty allocation list.
Missing CAIE data therefore cannot crash the dashboard/API.

## Safety enforcement

The API projection force-sets:

- execution_allowed=false
- broker_execution_armed=false
- money_movement_allowed=false
- live_trading_authorized=false
- mode=SHADOW_ONLY

This remains true even if malformed upstream data attempts to set those fields
to true.

## Mobile boundary

No mobile dashboard clutter or trading control has been added. The API is
read-only and optional.

## Phase boundary

Phase 155F does not promote CAIE, change broker behavior, place orders, or alter
existing execution/gate behavior.
