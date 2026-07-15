# Phase MC-002 - Mission Control Live Data Integration

## Scope

MC-002 converts the MC-001 Mission Control shell into a read-only
enterprise-integrated dashboard surface. It registers Mission Control with the
existing dashboard web host and adapts existing canonical dashboard/runtime
payloads into the stable `css.mission_control.state.v1` contract.

This phase does not deploy Desktop runtime changes and does not create a second
production server.

## Architecture Reviewed

The phase reviewed and reused:

- `dashboard.runtime.frontend_contract`
- `dashboard.runtime.api_bridge`
- `dashboard.web.web_app`
- `dashboard.runtime.dashboard_state`
- canonical broker runtime state and broker readiness payloads
- runtime certification snapshots
- portfolio, risk, Options Income, audit, learning, and governance dashboard
  payloads

Mission Control remains a presentation and normalization layer. It does not
duplicate accounting, broker, risk, certification, alert, audit, or learning
frameworks.

## Host Registration

Mission Control is registered through:

- `dashboard.mission_control.host_registration.register_mission_control`
- `dashboard.web.web_app.create_app`

The registration is idempotent and rejects conflicting existing
`/mission-control` routes. The router exposes only GET routes and does not
start background workers, create broker connections, mutate runtime state, or
register write-capable operations.

Primary routes:

- `/mission-control`
- `/mission-control/{section}`
- `/mission-control/api/state`
- `/mission-control/api/health`
- `/mission-control/api/navigation`
- `/mission-control/api/page-metadata`
- `/mission-control/api/brokers`
- `/mission-control/api/certification`

## Canonical Data Sources

Mission Control consumes existing CSS frontend/runtime payloads through
`dashboard.runtime.frontend_contract.build_frontend_payload`.

The MC-002 adapter preserves source metadata for:

- platform
- runtime
- trading
- portfolio
- market intelligence
- risk
- Options Income
- brokers
- alerts
- certification
- audit
- explainability
- learning
- governance
- configuration
- documentation
- permissions
- safety

## Source Registry

Each section exposes source and provenance metadata with one of:

- `LIVE`
- `RUNTIME`
- `CACHE`
- `HISTORICAL`
- `MOCK`
- `UNAVAILABLE`
- `UNKNOWN`

No unavailable canonical data is silently replaced with mock data. Mock data is
allowed only when explicitly requested and remains labeled `MOCK DATA - NOT
LIVE`.

## Freshness Model

MC-002 adds deterministic freshness metadata:

- `FRESH`
- `AGING`
- `STALE`
- `UNAVAILABLE`
- `UNKNOWN`

Each section reports source, generated timestamp, observed timestamp, age, and
stale reason. Mandatory stale or unavailable data downgrades the Mission
Control health summary.

## Health Model

Mission Control health is advisory and display-only. Possible values are:

- `GREEN`
- `AMBER`
- `RED`
- `UNAVAILABLE`
- `FAIL_CLOSED`

Unsafe safety flags or invalid contract validation produce fail-closed health.

## Read-Only Permissions

MC-002 adds explicit permissions metadata:

- `read_only=true`
- `can_execute=false`
- `can_arm_broker=false`
- `can_modify_limits=false`
- `can_modify_credentials=false`
- `can_restart_runtime=false`
- `can_shutdown_runtime=false`
- `can_change_broker=false`

Any write-capable permission fails validation.

## Safety Posture

Mission Control continues to preserve:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Mission Control may display execution readiness and broker state, but it never
derives, grants, or mutates execution authority.

## Page Integration

The existing fifteen Mission Control pages now consume the integrated state
contract. Available canonical data is displayed from runtime payloads.
Unavailable data remains explicitly unavailable.

Broker Management is read-only. Broker selection, credential entry, onboarding,
activation, execution arming, and live authorization remain disabled.

## Secret Redaction

Mission Control validates payloads for secret-bearing keys and fails closed if
unsafe values are present. The documentation index uses relative paths only and
does not expose arbitrary filesystem reads.

## Validation Evidence

MC-002 adds tests for:

- host registration
- idempotent registration
- route prefixes
- state, health, navigation, broker, and certification endpoints
- all fifteen pages
- live-state adapter
- canonical contract preservation
- source labeling
- freshness downgrade
- unavailable handling
- read-only permissions
- absence of write routes
- secret and non-finite rejection
- deterministic serialization

## Known Limitations

- MC-002 does not activate Desktop runtime deployment.
- Alerts, audit, explainability, and documentation indexing depend on existing
  runtime payload availability.
- No broker onboarding, credential entry, runtime restart, kill-switch action,
  or user-management write is implemented.

## Next Phases

Future Mission Control phases may add richer runtime-host activation,
role-aware display filtering, fuller alert/audit feeds, and approved
operator-workflow shells. Any future controls must remain subordinate to
existing RBAC, R7 gates, broker startup gates, NO-GO logic, execution firewall,
and broker readiness/certification.
