# CSS Simulator & Academy — Phase 4

Phase 4 turns the simulator into a structured decision-replay and readiness experience that can be rendered by a phone client without introducing broker execution authority.

## Delivered

- recommendation replay engine;
- scenario decision checkpoints;
- weighted replay scoring;
- training readiness levels;
- explicit fail-closed live-execution boundary;
- stable phone-preview API contract.

## Recommendation replay

Scenario checkpoints define the expected learner action and eventual outcome evidence. The replay engine classifies each checkpoint as PENDING, CORRECT, PARTIAL, or INCORRECT.

It scores only historical or simulated learning behavior. It has no broker-order capability.

## Readiness levels

The academy exposes FOUNDATION, PRACTICE, BROKER_READONLY_READY, ADVISORY_READY, and CONTROLLED_LIVE_REVIEW.

CONTROLLED_LIVE_REVIEW is intentionally not live-trading authorization. Even when the learner meets the strongest training threshold, live_execution_authorized remains false.

Separate broker activation, operational certification, compliance controls, and explicit human authorization remain mandatory.

## Phone-preview contract

The stable preview schema is simulator-preview.v1.

Every payload explicitly carries mode SIMULATION, execution_allowed false, broker_execution_armed false, money_movement_allowed false, and live_execution_authorized false.

The contract includes session state, readiness state, checkpoint outcomes, and replay score where available.

## Boundary

Phase 4 introduces no order submission, order cancellation, transfer, withdrawal, deposit, funding, credentials, or live Questrade dependency.
