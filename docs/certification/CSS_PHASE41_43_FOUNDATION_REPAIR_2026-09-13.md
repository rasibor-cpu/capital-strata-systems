# CSS Phase 41-43 Foundation Repair

## Reason for repair

The institutional backlog described Phase 41-43 foundations as implemented, but
the current certified integration tree did not contain the three named dashboard
runtime modules or their API surfaces. This repair makes the repository match
the documented backlog while preserving fail-closed behavior.

## Phase 41 — Broker Live Dry-Run Certification

Added a sanitized certification projection that requires:

- selected live broker;
- broker connectivity/readiness;
- broker/CSS reconciliation;
- credential attestation readiness;
- explicit non-submitting dry-run probe.

A PASS means evidence is complete for review only. It always returns:

- execution_allowed=false
- broker_execution_armed=false
- live_trading_authorized=false

## Phase 42 — Broker Adapter Conformance

Added registry-driven, non-networking conformance checks for:

- paper/live mode metadata;
- asset-class metadata;
- adapter availability;
- account snapshot method contract;
- position snapshot method contract;
- order-intent validation method contract.

Unsupported or incomplete adapters fail closed. The suite does not instantiate
network clients and does not submit orders.

## Phase 43 — Live Credential Readiness Attestation

Added local-only attestation that returns only booleans/status/warnings.

It checks:
- broker-specific required credential groups;
- path/PEM existence where path metadata is present;
- optional expiry metadata;
- optional rotation metadata.

Secret values and local paths are never returned.

## API surfaces

Read-only GET projections:

- /api/v1/broker-live-dry-run-certification
- /api/v1/broker-adapter-conformance
- /api/v1/live-credential-attestation

No route accepts or performs broker mutation.
