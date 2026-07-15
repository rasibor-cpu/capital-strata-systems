# Phase MC-001 - CSS Mission Control Foundation

## Scope

MC-001 establishes the initial read-only enterprise shell for CSS Mission
Control. The phase creates application navigation, page hierarchy, responsive
layout, canonical state contracts, read-only adapters, mock-data labeling, and
the Broker Management foundation.

This phase does not deploy to the Desktop runtime and does not create a new
runtime server, event bus, broker registry, authentication system, audit system,
or certification framework.

## Architecture Reviewed

The implementation reviewed and reuses the existing dashboard and runtime
architecture:

- `dashboard.runtime.frontend_contract`
- `dashboard.runtime.dashboard_state_factory`
- `dashboard.web.web_app`
- `dashboard.mobile.mobile_app`
- `launcher.css_mobile_launcher`
- canonical broker runtime state and certification snapshots
- broker readiness and operational status modules
- alert, audit, portfolio, risk, certification, and Options Income surfaces

## Existing Systems Reused

Mission Control consumes the existing frontend payload contract through a
read-only adapter. Runtime, broker, portfolio, risk, certification, and
governance information is adapted from existing CSS payloads where available.
Unavailable integrations are explicitly marked `UNAVAILABLE`.

## Application Shell

The shell provides:

- persistent left navigation
- top command/status bar
- main workspace
- breadcrumb context
- global mode, broker, health, platform, execution, and safety indicators
- responsive desktop/tablet/mobile layout

## Navigation

The initial shell registers all fifteen required sections:

1. Executive Overview
2. Runtime Operations
3. Trade Operations
4. Portfolio
5. Market Intelligence
6. Risk Command
7. Options Income
8. Broker Management
9. Alerts and Incidents
10. Certification and Readiness
11. Audit and Explainability
12. Learning and Performance
13. Users and Governance
14. System Configuration
15. Documentation / Runbooks

## Canonical Contract

Mission Control state is versioned as:

`css.mission_control.state.v1`

The contract contains stable top-level sections for platform, runtime, trading,
portfolio, market intelligence, risk, options income, brokers, alerts,
certification, audit, learning, governance, configuration, documentation, and
safety.

Serialization is deterministic with sorted keys.

## Broker Management

The Broker Management page includes:

- active broker summary
- broker list for Coinbase, OANDA, IBKR, and paper/mock
- capability and supported-asset summaries
- read-only broker selection preview
- onboarding shell
- broker safety panel

Broker selection and onboarding controls are disabled in MC-001. No credential
entry, credential storage, adapter activation, live mode activation, or broker
arming is implemented.

## Broker Onboarding Model

MC-001 only creates the onboarding structure. Future phases may add secure
workflows for provider selection, adapter capability discovery, credential
requirements, account requirements, market-data requirements, permission
requirements, and readiness checklists.

No credential values are stored in browser state or printed by Mission Control.

## Safety Posture

Mission Control always preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Mission Control may display execution state and readiness, but it cannot grant
execution authority.

## Mock Versus Live Data

When runtime data is unavailable, MC-001 uses deterministic mock data only for
shell rendering and tests. Mock data is explicitly labeled:

`MOCK DATA - NOT LIVE`

No mocked data is presented as live broker data.

## Fail-Closed Behavior

The contract validator fails closed for:

- missing or invalid safety flags
- invalid schema version
- malformed navigation
- secret-bearing payloads
- non-finite numeric values
- missing or unavailable mandatory sections

Unavailable data is represented as `UNAVAILABLE`, not fabricated live values.

## Responsive Design

The shell is CSS-native and responsive for desktop, tablet, and mobile browser
use. MC-001 avoids introducing a new frontend framework or asset pipeline.

## Validation Evidence

MC-001 adds deterministic tests for shell rendering, navigation, page
registration, canonical contract, mock labeling, safety banner, Broker
Management, onboarding shell, no secret exposure, no execution controls,
responsive contract, FastAPI routes, and documentation index safety.

## Known Limitations

- Mission Control is not yet mounted into Desktop runtime.
- Controls are disabled or shell-only.
- Documentation/runbook indexing is static.
- Options Income data is adapted when available and otherwise marked
  unavailable.
- Alert and audit pages are read-only foundations.

## Next Mission Control Phases

Future phases should add approved runtime mounting, richer live runtime
snapshots, secure broker onboarding workflows, role-aware visibility,
document-index discovery, operational alert integration, and eventually
approval-gated control-plane features that remain subordinate to R7/RBAC,
firewall, broker gates, and live execution authority.
