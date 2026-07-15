# Phase BR-001 Strict Broker Environment Profile Separation

## Purpose

BR-001 eliminates recurring LIVE/PRACTICE contamination and broker credential ambiguity by introducing explicit broker environment profiles:

- `PAPER`
- `LIVE_READ_ONLY`
- `LIVE_EXECUTION`

Broker environment selection is independent from engine mode. `SAFE`, `BALANCED`, `AGGRESSIVE`, and `EXPANSION` never select a broker credential profile.

## Safety Boundary

BR-001 preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

No live orders are submitted. No broker writes occur. No execution authority is granted. `LIVE_EXECUTION` can be represented for future governance validation, but in BR-001 it remains disabled, disarmed, unauthorized, and blocked.

## Profile Model

The canonical enum is `BrokerEnvironmentProfile` in `backend/runtime/broker_environment_profiles.py`.

Profile meanings:

| Profile | Purpose | Execution posture |
| --- | --- | --- |
| `PAPER` | Paper and practice-only simulation support. | No live credentials, no live authority flags. |
| `LIVE_READ_ONLY` | Authenticated broker account, balance, portfolio, product, and market-data reads. | Read-only access only; execution flags fail closed. |
| `LIVE_EXECUTION` | Future execution-capable profile model. | Modeled only; execution remains blocked in BR-001. |

## Environment File Model

Supported profile files:

- `.env.shared`
- `.env.paper`
- `.env.live_read_only`
- `.env.live_execution`

Legacy compatibility files may be read only through the canonical profile loader:

- `.env`
- `.env.practice`

Profile behavior:

| Profile | Files loaded | Legacy compatibility | Rejected evidence |
| --- | --- | --- | --- |
| `PAPER` | `.env.shared`, `.env.paper` | `.env`, `.env.practice` | Live credentials and live authority flags. |
| `LIVE_READ_ONLY` | `.env.shared`, `.env.live_read_only` | `.env`; `.env.practice` is skipped | Test/practice/sandbox variables and execution authority flags. |
| `LIVE_EXECUTION` | `.env.shared`, `.env.live_execution` | `.env`; `.env.practice` is skipped | Test/practice/sandbox variables; execution remains blocked. |

No unknown profile defaults to paper or live. Unknown selection fails closed.

## Process Environment Sanitization

Before loading a profile, the canonical loader removes known Coinbase and OANDA profile-specific variables from the target process environment. It then loads exactly the selected profile files and removes incompatible variables introduced by legacy files.

This includes inherited Windows and PowerShell variables passed through `os.environ`.

`COINBASE_TEST_ORDER_USD` is PAPER-only. It cannot remain present after `LIVE_READ_ONLY` or `LIVE_EXECUTION` sanitization.

## Canonical Credential Object

`BrokerEnvironmentCredentials` is immutable and redacted by default. It contains:

- profile
- broker
- environment
- credential source
- key identifier presence
- private key presence
- permissions classification
- base URL
- read-only permission posture
- execution requested
- execution authorized
- profile fingerprint
- validation status
- failure reasons
- warnings
- loaded files
- skipped files
- removed inherited variables
- contamination keys
- safety flags

Secret values are available only to server-side credential consumers through `credentials_for_broker()`. Browser and diagnostics payloads use `redacted_diagnostics()`.

## Profile Precedence

Selection precedence is:

1. Explicit startup selection.
2. Explicit CLI argument.
3. Explicit approved environment profile variable:
   - `CSS_BROKER_ENVIRONMENT_PROFILE`
   - `BROKER_ENVIRONMENT_PROFILE`
   - `CSS_BROKER_PROFILE`
4. Fail closed.

Engine mode is not part of the precedence chain.

## Legacy Migration

| Legacy variable/file | Classification | Migration target | Rule |
| --- | --- | --- | --- |
| `COINBASE_TEST_ORDER_USD` | PAPER-only legacy test notional | `.env.paper` | Removed from live profiles. |
| `COINBASE_ENABLE_LIVE_ORDERS` | Unsafe legacy authority flag | Future governed execution approval | Rejected in read-only profile; execution remains blocked. |
| `COINBASE_KEY_NAME` | Compatibility alias | `COINBASE_CDP_KEY_NAME` | Allowed as compatibility metadata in selected profile files. |
| `.env.practice` | Legacy practice file | `.env.paper` | Never loaded by live profiles. |

## Mission Control Exposure

Mission Control and dashboard payloads receive redacted profile metadata only:

- profile
- environment
- readiness
- permissions classification
- profile fingerprint
- contamination status
- contamination keys
- execution posture

No credential values, account IDs, private keys, JWTs, PEM material, or tokens are exposed.

## Fail-Closed Behavior

BR-001 fails closed for:

- no explicit profile
- multiple conflicting profiles
- unknown profile
- engine mode used as broker profile
- mixed profile variables
- test/practice/sandbox variables in live profiles
- live credentials in paper profile
- unknown credential source
- invalid base URL
- execution authorization in read-only profile
- unsafe execution flags

## Validation

Primary BR-001 tests:

- `tests/test_br001_broker_environment_profiles.py`

Relevant regression slices:

- Phase166A
- Phase166B
- Phase166C
- Phase166D
- Coinbase authentication
- Coinbase readiness
- broker bootstrap
- credential loader
- Mission Control broker state
- runtime smoke
- dashboard smoke

## Governance Outcome

BR-001 creates the broker environment architecture required for reliable read-only live validation and future governed execution planning. It does not authorize live execution.
