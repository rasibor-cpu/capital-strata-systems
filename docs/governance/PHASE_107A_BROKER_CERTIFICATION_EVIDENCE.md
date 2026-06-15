# Phase 107A Broker Certification Evidence

## A. Broker Inventory

The Capital Strata Systems (CSS) platform currently interacts with or contains legacy dependencies for the following brokers:
1. **OANDA** (Canonical, Integrated)
2. **Coinbase** (Canonical, Integrated)
3. **Alpaca** (Registered, Disconnected Adapter)
4. **IBKR** (Unregistered, Isolated Codebase)

## B. Certification Status Per Broker

### 1. OANDA
- **Supported Modes**: Paper, Live
- **Asset Classes**: `fx`, `forex`
- **Live Execution Status**: Supported, secured behind `OANDA_ENABLE_LIVE_TRADING` toggle.
- **Paper/Practice Status**: Supported via environment configuration (`OANDA_ENV`).
- **Read-Only Status**: Fully supported (`get_account_summary`, `get_open_positions`).
- **Credential Handling**: Loaded via environment variables (`OANDA_API_KEY`, `OANDA_ACCOUNT_ID`).
- **Fail-Closed Behavior**: If credentials are missing, `is_configured()` returns `False` and any API requests safely raise `RuntimeError`. Live orders are rejected if live execution is not explicitly armed.

### 2. Coinbase
- **Supported Modes**: Paper, Live
- **Asset Classes**: `crypto`, `spot_crypto`
- **Live Execution Status**: Supported.
- **Paper/Practice Status**: Supported.
- **Read-Only Status**: Supported.
- **Credential Handling**: Expects CDP API key JSON formats (e.g., `cdp_api_key.json`). SEC-05 verified credential is not tracked in git history.
- **Fail-Closed Behavior**: Gated by execution engine configuration. 

### 3. Alpaca
- **Supported Modes**: Defined in registry for Paper and Live.
- **Asset Classes**: `equities`, `stocks`, `crypto`
- **Live Execution Status**: Not integrated into canonical paths.
- **Paper/Practice Status**: Legacy files (`alpaca_paper_broker.py`) exist but are not canonically invoked.
- **Fail-Closed Behavior**: Safely fails. Calling `get_adapter("alpaca")` raises `KeyError` enforcing non-execution.

### 4. IBKR
- **Status**: Unregistered. Isolated files (`ibkr_adapter.py`, `ibkr_paper_broker.py`) and UI shadows exist, but IBKR is completely omitted from `BROKER_REGISTRY`. It cannot be executed by the canonical engine.

## C. Broker Safety Boundary

- **Live Execution Arming Requirements**: Live execution requires the broker adapter to be instantiated with explicit environment configuration (e.g., `OANDA_ENABLE_LIVE_TRADING=true`). 
- **RBAC Requirements**: Trade decisions routed to the broker must originate from authenticated sessions mapped to `TRADER`, `ADMIN`, or `SUPER_USER` roles as verified in Phase 106B.
- **Paper/Live Separation**: Guaranteed by adapter URL routing and distinct execution gate validations.
- **Credential Non-Commitment**: Validated. The global `.gitignore` enforces rejection of all `.env`, `keys/`, `*.pem`, and `*.json` key files.
- **Current Limitations**: The platform does not currently support multi-broker parallel execution gracefully due to missing adapter registrations for Alpaca and IBKR.

## D. Evidence Mapping

| Broker / Capability | Evidence Files / Certifications |
|---------------------|--------------------------------|
| Broker Registry | `backend/app/brokers/broker_registry.py` |
| OANDA Adapter | `backend/app/brokers/oanda_adapter.py` |
| Coinbase Adapter | `backend/broker/coinbase_adapter.py` |
| Execution Boundaries | `PHASE_106B_SECURITY_AUDIT_RECERTIFICATION_REPORT.md` |
| Execution Governance | `PHASE_106C_GOVERNANCE_AUTHORITY_REGISTER.md` |

## E. Open Broker Gaps

1. **Alpaca Adapter Disconnection**: Alpaca is listed in the `BROKER_REGISTRY` but is not wired into `get_adapter()`. Any attempt to resolve it throws a `KeyError`.
2. **IBKR Shadow Code**: The repository contains legacy `ibkr/` code paths and shadow UI files that are completely unregistered and serve no production purpose. These should be purged or formally integrated.
