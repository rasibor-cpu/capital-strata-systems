# Micro-Live Pilot Authorization

## Pilot Name
OANDA Micro-Live Pilot 1

## Pilot Scope
This pilot authorizes the Capital Strata Systems (CSS) engine to execute live trades against the OANDA live environment using real capital, strictly bounded by the constraints defined below.

## Pilot Objectives
1. Validate live OANDA execution pathways.
2. Validate continuous reconciliation heartbeat under live execution conditions.
3. Validate institutional slippage controls (`priceBound`).
4. Validate live broker resilience handling (rate limit handling and degraded health backoffs).
5. Expose any unhandled live data anomalies.

## Pilot Start Authorization
Authorized to begin upon full validation of Phase 119A and explicit operator initiation.

## Pilot End Criteria
1. Completion of 5 Active Trading Days.
2. Total Loss exceeds $50.
3. Daily Loss exceeds $20.
4. Unhandled `GHOST_LOCAL_POSITION` or critical divergence occurs.
5. Operator manual abort.

## Approved Broker
OANDA

## Approved Asset Classes
FX (Forex pairs supported by OANDA margin account).

## Approved Capital Limits
* **Maximum Capital:** $1,000 USD
* **Maximum Daily Loss:** $20
* **Maximum Total Loss:** $50
* **Maximum Open Positions:** 3
