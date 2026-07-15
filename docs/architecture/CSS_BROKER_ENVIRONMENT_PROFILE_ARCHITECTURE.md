# CSS Broker Environment Profile Architecture

## Overview

CSS broker credentials are now selected through an explicit canonical broker environment profile. The profile layer separates broker credential environment from engine mode and prevents paper/practice variables from contaminating live read-only or future execution processes.

The architecture is implemented in:

- `backend/runtime/broker_environment_profiles.py`
- `backend/runtime/live_environment_loader.py`
- `backend/app/brokers/credential_loader.py`
- `backend/app/brokers/broker_bootstrap.py`
- `backend/runtime/canonical_broker_state_builder.py`
- `dashboard/runtime/frontend_contract.py`
- `dashboard/mission_control/state_adapter.py`
- `dashboard/mission_control/broker_registry.py`

## Profile Enum

```python
BrokerEnvironmentProfile.PAPER
BrokerEnvironmentProfile.LIVE_READ_ONLY
BrokerEnvironmentProfile.LIVE_EXECUTION
```

The selected profile is never inferred from:

- `ENGINE_MODE`
- `SAFE`
- `BALANCED`
- `AGGRESSIVE`
- `EXPANSION`

## Selection Flow

Profile selection precedence:

1. Explicit startup profile.
2. Explicit CLI profile.
3. Explicit approved environment variable.
4. Fail closed.

Approved environment variables:

- `CSS_BROKER_ENVIRONMENT_PROFILE`
- `BROKER_ENVIRONMENT_PROFILE`
- `CSS_BROKER_PROFILE`

If multiple profiles conflict, startup fails closed.

## File Loading Flow

The loader performs:

1. Select broker environment profile.
2. Remove inherited Coinbase/OANDA profile-specific variables.
3. Load `.env.shared`.
4. Load exactly one selected profile file.
5. Apply legacy compatibility rules.
6. Remove incompatible variables introduced by compatibility files.
7. Validate contamination and authority flags.
8. Build immutable canonical credential object.
9. Publish redacted diagnostics and profile fingerprint.

## Profile File Rules

| Profile | Canonical files | Legacy files | Notes |
| --- | --- | --- | --- |
| `PAPER` | `.env.shared`, `.env.paper` | `.env`, `.env.practice` | Paper/test variables allowed; live credentials rejected. |
| `LIVE_READ_ONLY` | `.env.shared`, `.env.live_read_only` | `.env` only | `.env.practice` skipped; test/sandbox/practice variables removed and reported. |
| `LIVE_EXECUTION` | `.env.shared`, `.env.live_execution` | `.env` only | Execution remains blocked in BR-001. |

## Canonical Object

`BrokerEnvironmentCredentials` is the canonical object. It is immutable and contains:

- profile identity
- broker
- environment
- credential source
- key/private key presence
- permission classification
- base URL
- read-only allowance
- execution requested/authorized
- fingerprint
- validation status
- loaded/skipped files
- removed inherited variables
- contamination keys
- advisory safety flags

Server-side credential consumers can request env-shaped credentials through `credentials_for_broker()`. Browser-facing and diagnostic consumers receive `redacted_diagnostics()`.

## Consumer Migration

Consumers should not call `load_dotenv()` or independently read raw broker profile variables. They should receive:

- canonical credential object diagnostics for display
- env-shaped credentials from the canonical object for server-side adapter construction
- canonical broker runtime state for readiness, Mission Control, and dashboard display

Updated consumers:

- Runtime environment loader.
- Broker credential fallback loader.
- Broker bootstrap self-test.
- Canonical broker runtime state.
- Dashboard broker section.
- Mission Control broker registry.

## Coinbase Read-Only Profile

`LIVE_READ_ONLY` supports Coinbase read-only credentials for:

- account access
- balances
- portfolio access
- products
- market data

Permissions are classified as:

- `READ_ONLY`
- `ORDER_CAPABLE`
- `UNKNOWN`
- `PAPER_NOT_REQUIRED`

Unknown permissions do not authorize execution.

## Live Execution Safeguard

`LIVE_EXECUTION` is modeled for future governance only. In BR-001:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `execution_authorized=false`

Any order-capable test must be mocked. No live order path is enabled.

## Diagnostics

Diagnostics include:

- selected profile
- loaded files
- skipped files
- removed inherited variables
- validation status
- failure reasons
- warnings
- credential source
- permissions classification
- profile fingerprint
- contamination keys
- execution posture

Diagnostics redact credential values, private keys, account identifiers, JWTs, tokens, and PEM content.

## Mission Control

Mission Control receives profile metadata through the frontend broker section and broker registry projection:

- profile
- environment
- permissions classification
- profile fingerprint
- contamination status
- contamination keys
- execution posture

Mission Control remains read-only and cannot modify broker profile, credentials, permissions, or execution state.

## Failure Behavior

All profile validation failures preserve fail-closed posture. Failures are evidence for diagnostics and readiness only; they do not bypass R7, RBAC, NO-GO, broker startup gates, live execution firewall, credential diagnostics, or execution boundary validation.
