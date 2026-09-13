# CSS Simulator Academy — Commercialization Safety Hardening

The Simulator/Academy presentation contracts now make three additional safety boundaries explicit:

- `commercialization_attribution_allowed = false`
- `fee_entitlement_allowed = false`
- `live_trading_eligible = false`

These are additive to the existing fail-closed controls:

- `execution_allowed = false`
- `broker_execution_armed = false`
- `money_movement_allowed = false`
- `live_execution_authorized = false`

Simulation P&L, replay scores, learner readiness, forecasts, challenges, badges, and debrief outputs therefore cannot by themselves establish CSS economic attribution, fee entitlement, broker authority, live-trading eligibility, or money-movement authority.

This hardening does not enable any broker action and does not change the simulator from SIMULATION mode.
