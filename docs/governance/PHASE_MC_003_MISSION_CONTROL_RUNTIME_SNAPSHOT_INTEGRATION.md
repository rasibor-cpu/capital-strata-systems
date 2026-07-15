# Phase MC-003 - Mission Control Runtime Snapshot Integration

## Scope

MC-003 connects Mission Control to the current read-only CSS runtime snapshot
evidence used by the Desktop/mobile launcher host. The goal is to display
authoritative runtime evidence when available and fail closed to unavailable
state when runtime evidence is absent or stale.

This phase remains read-only. It does not add runtime controls, broker writes,
order submission, broker arming, credential mutation, or limit mutation.

## Architecture Reviewed

The phase reviewed:

- `dashboard/mission_control`
- `dashboard/web/web_app.py`
- `launcher/css_mobile_launcher.py`
- `dashboard/runtime/frontend_contract.py`
- `dashboard/runtime/api_bridge.py`
- runtime certification snapshots
- launcher supervisor/session/account artifact readers
- runtime health, artifact freshness, session continuity, and validation feeds

## Authoritative Runtime Source

The canonical source for the Desktop host is the existing mobile launcher
runtime bridge:

`launcher.css_mobile_launcher.build_launcher_frontend_state`

That function already consumes current runtime artifacts, supervisor state,
account state, broker startup evidence, runtime health, validation readiness,
and certification evidence before projecting the canonical frontend contract.

Mission Control does not create a new runtime store.

## Provider Precedence

Runtime snapshot resolution follows:

1. In-process runtime frontend payload when the host shares process with the
   runtime bridge.
2. Existing runtime artifact evidence.
3. Explicit cache-labeled artifact snapshot.
4. `UNAVAILABLE`/offline fail-closed snapshot.

Demo/default dashboard state is not treated as current runtime evidence unless
explicitly labeled as demo/mock.

## Runtime Bridge

New read-only modules:

- `dashboard.mission_control.runtime_snapshot_provider`
- `dashboard.mission_control.runtime_snapshot_normalizer`
- `dashboard.mission_control.runtime_bridge`

The mobile launcher registers Mission Control with
`build_launcher_frontend_state`, so `/mission-control` on the launcher host uses
the same runtime evidence as the existing Desktop dashboard APIs.

## Demo Isolation

When no runtime provider is available, Mission Control reports runtime offline
and uses `UNAVAILABLE` for broker, account, portfolio, alert, risk, market, and
certification values.

Demo/mock values must carry `MOCK` or `DEMO` source labels and may not
masquerade as runtime data.

## Online Behavior

When runtime evidence is fresh, Mission Control displays:

- runtime/session/cycle/engine mode
- heartbeat status and age
- broker readiness and provenance
- account and portfolio metrics
- risk and market state
- alerts
- certification and blockers
- deterministic runtime state hash

## Offline Behavior

When runtime evidence is unavailable:

- runtime status is `OFFLINE`
- heartbeat is `UNAVAILABLE`
- broker/account/portfolio values are `UNAVAILABLE`
- alert count is `UNAVAILABLE`
- execution remains blocked
- safety remains fail-closed/read-only
- Executive Overview displays a runtime-offline banner

## Freshness And Heartbeat

Heartbeat freshness is mandatory. Stale, unavailable, or unknown heartbeat
state downgrades Mission Control health and adds an explicit health reason.

## API Endpoints

MC-003 adds:

- `/mission-control/api/runtime`
- `/mission-control/api/heartbeat`

All Mission Control routes are GET-only and read-only.

## State Consistency

State, runtime, and heartbeat endpoints derive from the same cached runtime
snapshot during a refresh window. Runtime and heartbeat endpoints expose the
same runtime `state_hash` as the full Mission Control state.

## Fail-Closed Behavior

Mission Control fails closed for:

- missing runtime provider
- unavailable runtime source
- stale heartbeat
- secret-bearing payloads
- non-finite values
- unsafe execution flags
- demo/runtime source mixing
- runtime offline with fabricated live/account values

## Safety Confirmation

Mission Control preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

## Validation Evidence

MC-003 adds deterministic tests for runtime provider normalization, runtime
snapshot API behavior, heartbeat API behavior, stale heartbeat downgrade,
offline/demo isolation, artifact cache fallback, route read-only enforcement,
and mobile launcher host registration.

## Known Limitations

Desktop runtime synchronization and live runtime validation remain approval
gated. MC-003 does not add runtime restart/shutdown controls, broker
onboarding, credential entry, or any write workflow.

## Next Phases

Future phases may deepen source-specific runtime evidence and page-level
drilldowns. Any future operator actions must remain subordinate to existing
R7/RBAC, broker startup gates, live execution firewall, NO-GO protections, and
manual approval controls.
