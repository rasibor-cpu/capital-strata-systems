# CSS Mission Control Architecture

## Product Vision

CSS Mission Control is the enterprise command, monitoring, governance, and
operational-intelligence interface for Capital Strata Systems. It is intended
to consolidate runtime, broker, portfolio, risk, certification, audit,
learning, and governance visibility into one institutional shell.

MC-001 is the foundation phase. It is read-only and does not become an
execution control plane.

## Component Architecture

Mission Control is implemented as an additive dashboard package:

- `dashboard.mission_control.contracts`
- `dashboard.mission_control.state_adapter`
- `dashboard.mission_control.navigation`
- `dashboard.mission_control.layout`
- `dashboard.mission_control.routes`
- `dashboard.mission_control.app`
- `dashboard.mission_control.pages`

The package can be mounted into existing FastAPI surfaces in future phases, but
MC-001 does not modify Desktop runtime or launcher behavior.

## State Flow

State flow:

1. Existing runtime/dashboard payloads are provided to Mission Control.
2. `dashboard.runtime.frontend_contract.build_frontend_payload` normalizes the
   CSS frontend contract.
3. `dashboard.mission_control.state_adapter` adapts the frontend payload.
4. `dashboard.mission_control.contracts` builds
   `css.mission_control.state.v1`.
5. The shell renders all pages from the canonical Mission Control state.

Unavailable live data remains `UNAVAILABLE`. Mock data is explicitly labeled.

## Runtime Integration

Mission Control reuses existing runtime snapshots, frontend contracts,
certification snapshots, broker readiness state, and governance state. It does
not start a competing runtime server, event bus, supervisor, or persistence
loop.

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

## RBAC Boundaries

MC-001 displays current user, role, unit, session, and permissions summaries
where available. It does not add user-management writes, role changes,
permission changes, or credential workflows.

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
