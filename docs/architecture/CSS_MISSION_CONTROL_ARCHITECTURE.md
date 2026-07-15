# CSS Mission Control Architecture

## Product Vision

CSS Mission Control is the enterprise command, monitoring, governance, and
operational-intelligence interface for Capital Strata Systems. It is intended
to consolidate runtime, broker, portfolio, risk, certification, audit,
learning, and governance visibility into one institutional shell.

MC-001 is the foundation phase. It is read-only and does not become an
execution control plane.

MC-002 registers Mission Control with the existing dashboard web host and
connects the shell to canonical read-only runtime/dashboard payloads. It does
not create a second production server or change Desktop-specific runtime
behavior.

MC-003 connects Mission Control to the Desktop/mobile launcher runtime bridge
so the shell consumes actual runtime snapshot evidence when available and
fails closed to offline/unavailable state when the runtime is not active.

## Component Architecture

Mission Control is implemented as an additive dashboard package:

- `dashboard.mission_control.contracts`
- `dashboard.mission_control.state_adapter`
- `dashboard.mission_control.navigation`
- `dashboard.mission_control.layout`
- `dashboard.mission_control.routes`
- `dashboard.mission_control.app`
- `dashboard.mission_control.pages`
- `dashboard.mission_control.host_registration`
- `dashboard.mission_control.live_state_adapter`
- `dashboard.mission_control.source_registry`
- `dashboard.mission_control.freshness`
- `dashboard.mission_control.health`
- `dashboard.mission_control.permissions`
- `dashboard.mission_control.serializers`
- `dashboard.mission_control.runtime_snapshot_provider`
- `dashboard.mission_control.runtime_snapshot_normalizer`
- `dashboard.mission_control.runtime_bridge`

The package is mounted into `dashboard.web.web_app.create_app` through an
idempotent registration helper. The helper rejects conflicting
`/mission-control` routes and rejects write-capable methods.

The Desktop launcher host mounts Mission Control through
`launcher.css_mobile_launcher` with
`build_launcher_frontend_state` as the authoritative in-process runtime source.

## State Flow

State flow:

1. Existing runtime/dashboard payloads are provided to Mission Control.
2. `dashboard.runtime.frontend_contract.build_frontend_payload` normalizes the
   CSS frontend contract.
3. `dashboard.mission_control.state_adapter` adapts the frontend payload.
4. `dashboard.mission_control.contracts` builds
   `css.mission_control.state.v1`.
5. `dashboard.mission_control.source_registry` labels each section source and
   provenance.
6. `dashboard.mission_control.runtime_snapshot_provider` resolves the current
   runtime snapshot.
7. `dashboard.mission_control.runtime_snapshot_normalizer` creates a
   canonical runtime snapshot with heartbeat and state hash.
8. `dashboard.mission_control.freshness` calculates deterministic freshness.
9. `dashboard.mission_control.health` derives display-only health.
10. The shell renders all pages from the canonical Mission Control state.

Unavailable live data remains `UNAVAILABLE`. Mock data is explicitly labeled.

## Route Architecture

Mission Control exposes only read-only GET routes:

- `/mission-control`
- `/mission-control/{section}`
- `/mission-control/api/state`
- `/mission-control/api/health`
- `/mission-control/api/navigation`
- `/mission-control/api/page-metadata`
- `/mission-control/api/brokers`
- `/mission-control/api/certification`
- `/mission-control/api/runtime`
- `/mission-control/api/heartbeat`

There are no POST, PUT, PATCH, or DELETE operational routes in MC-002.

MC-003 preserves this GET-only route architecture.

## Runtime Snapshot Architecture

Mission Control runtime snapshot precedence is:

1. In-process runtime source when the host shares process with the runtime
   bridge.
2. Existing runtime artifact evidence.
3. Explicit cache-labeled artifact snapshot.
4. Offline/unavailable fail-closed snapshot.

The canonical Desktop source is
`launcher.css_mobile_launcher.build_launcher_frontend_state`, which already
bridges supervisor, session, account, broker, runtime health, artifact
freshness, validation, and certification evidence into the frontend contract.

## Runtime/Web-Host Separation

The web dashboard host may remain available when the trading runtime is offline.
In that condition Mission Control displays runtime offline and does not
substitute demo account, broker, portfolio, or market values.

## Demo Isolation

Demo/default dashboard values are accepted only when explicitly labeled as mock
or demo. Missing runtime data remains unavailable. The Executive Overview shows
a runtime-offline banner when current runtime evidence is absent.

## State Hash Consistency

Mission Control state, runtime API, and heartbeat API derive from the same
runtime snapshot during a refresh window. Runtime and heartbeat endpoints expose
the same runtime snapshot hash as the full state payload.

## Runtime Integration

Mission Control reuses existing runtime snapshots, frontend contracts,
certification snapshots, broker readiness state, and governance state. It does
not start a competing runtime server, event bus, supervisor, or persistence
loop.

## Source Registry

Each top-level Mission Control section exposes source metadata using:

- `LIVE`
- `RUNTIME`
- `CACHE`
- `HISTORICAL`
- `MOCK`
- `UNAVAILABLE`
- `UNKNOWN`

The registry preserves source module, generated timestamp, observed timestamp,
provenance, and unavailable reason where known.

## Freshness Model

Freshness statuses are:

- `FRESH`
- `AGING`
- `STALE`
- `UNAVAILABLE`
- `UNKNOWN`

Mandatory stale or unavailable runtime, broker, certification, platform, or
safety data downgrades Mission Control health.

Runtime heartbeat freshness is mandatory. Stale or unavailable heartbeat state
downgrades Mission Control health.

## Health Model

Mission Control health is display-only and may be:

- `GREEN`
- `AMBER`
- `RED`
- `UNAVAILABLE`
- `FAIL_CLOSED`

Unsafe safety flags or invalid contracts fail closed.

## Broker Integration

Broker Management consumes canonical broker runtime state, broker readiness,
status provenance, execution scope, failure reasons, and safety flags where
available.

Broker list support is a read-only foundation for:

- Coinbase
- OANDA
- IBKR
- paper/mock broker
- future adapters

Broker selection is preview-only in MC-001. Onboarding is a shell only.

MC-002 continues the same posture while displaying canonical broker readiness,
authentication, account, balance, buying power, market-data, latency,
provenance, and warning summaries when those fields are available upstream.

## Security Boundaries

Mission Control must not expose:

- secrets
- tokens
- PEM material
- private key paths
- JWT values
- broker credentials
- account identifiers unless explicitly redacted by upstream contracts

The state validator scans for secret-bearing payloads and fails closed.

MC-002 adds deterministic safe serialization and state hashing. Non-finite
numeric values and unsafe secret-bearing fields are rejected.

## RBAC Boundaries

MC-001 displays current user, role, unit, session, and permissions summaries
where available. It does not add user-management writes, role changes,
permission changes, or credential workflows.

MC-002 adds an explicit read-only permissions model:

- `read_only=true`
- `can_execute=false`
- `can_arm_broker=false`
- `can_modify_limits=false`
- `can_modify_credentials=false`
- `can_restart_runtime=false`
- `can_shutdown_runtime=false`
- `can_change_broker=false`

Future write workflows must remain subordinate to the existing RBAC,
live-operator wizard, R7 execution gates, execution firewall, and broker
authority layers.

## Responsive Architecture

The shell uses CSS-native responsive layout:

- persistent left navigation on desktop
- stacked navigation on tablet/mobile
- responsive metric grids
- responsive panel grids
- accessible landmarks and labels

No heavy frontend framework is introduced in MC-001.

## Future Control-Plane Design

Future control-plane features may include approval-gated runtime actions,
broker onboarding, incident workflows, and operator runbooks. These features
must be implemented only after explicit approval and must never bypass:

- R7 execution gates
- RBAC
- broker startup gates
- NO-GO logic
- live execution firewall
- execution boundary validation
- broker readiness/certification

## Future Secure Broker Onboarding

Future onboarding should separate:

- provider selection
- adapter type
- environment
- credential requirements
- permissions
- account requirements
- market-data requirements
- readiness checklist
- certification evidence

Credential entry and storage must use a secure future workflow. Browser state
must not store raw credential values.

## Future Deployment Strategy

MC-001 is developed on Laptop1. Desktop runtime deployment requires explicit
approval. Future phases should mount Mission Control into the approved runtime
surface only after regression, security, and governance validation.

MC-002 remains a Laptop1 host-registration and read-only integration phase.
Desktop synchronization and runtime validation remain separate approval-gated
steps.
