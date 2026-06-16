# Phase 108D Capital Limits and Production Configuration Framework

## A. Production Capital Governance Objectives
The objective of Phase 108D is to formally ratify the structural risk boundaries, limit frameworks, and operational configurations required for live-capital deployment. This framework explicitly ensures that the Capital Strata Systems (CSS) execution planes cannot exceed mathematically proven safety bounds, regardless of the trading signal logic, closing GAP-108-04.

## B. Capital Limit Inventory
CSS execution operations are strictly bound by the following hard-coded, cascading limits. *No real dollar amounts are committed; limits represent percentage bounds.*

- **Account-Level Limits**: Hard ceiling on the total percentage of principal capital deployed across all active regimes.
- **Portfolio-Level Limits**: Total aggregate exposure bounds across all independent trading strategies.
- **Asset-Class Limits**: Specific exposure caps separating foreign exchange, crypto, equities, and derivatives bounds.
- **Broker-Level Limits**: Margin-to-equity ratio maximums enforced before external adapter payload delivery.
- **Daily Loss Limits**: Hard-stop logic triggering an immediate `AntiBleedGuard` liquidation/halt if intra-day PnL reaches maximum tolerable drawdown.
- **Drawdown Limits**: Total peak-to-trough limits that trigger strategy de-allocation independent of daily PnL velocity.
- **Exposure Limits**: Per-instrument margin caps preventing concentration risk.

## C. Production Deployment Profiles

### Development
- **Purpose**: Local feature testing and telemetry integration.
- **Capital**: `$0` (Isolated dummy structures).
- **Execution**: Terminal only (no broker access).

### Simulation
- **Purpose**: Long-running historical backtests and predictive dry-runs.
- **Capital**: Synthetic historical ledgers.
- **Execution**: Engine intrinsic; `OANDA_ENABLE_LIVE_TRADING=False`.

### Paper Trading
- **Purpose**: Forward-testing predictive yields against live API prices.
- **Capital**: Synthetic "practice" capital provided by broker staging environments.
- **Execution**: Forwarded via restricted adapters pointing exclusively to practice endpoints (e.g., `fxpractice`).

### Production
- **Purpose**: Live institutional portfolio management.
- **Capital**: Real institutional limits governed by dual-key arming checks.
- **Execution**: Live egress pathways with live-armed margin checks and P0 paging hooks.

## D. Production Configuration Matrix

| Profile | Execution Permissions | Capital Permissions | Broker Permissions | Monitoring Requirements | Approval Requirements |
|---|---|---|---|---|---|
| **Development** | Native Only | $0 dummy | `NotImplemented` | Local stdout/SQLite | Developer |
| **Simulation** | Engine Only | Synthetically Infinite | Intrinsic Logic | Local Dashboard | Developer |
| **Paper** | OANDA Practice | Practice Sub-accounts | Practice URI | Telemetry Logs | Engineering Lead |
| **Production** | Armed Adapters | Enforced Margin Ceiling | Live URI | Remote PagerDuty/Observability | Executive Risk Officer |

## E. Live Capital Activation Requirements
Before moving an environment from Paper to Production, the following explicit conditions must be met:
- **Required Approvals**: Sign-off from the Lead Engineer and the Chief Risk Officer.
- **Required Certifications**: 100% pass-rate on the CSS test suite (342+ tests), explicit proof of active `AntiBleedGuard` testing, and validated broker adapter ping metrics.
- **Required Operational Checks**: Network egress rules verified; remote PagerDuty integrations confirmed active; Production database schema parity matched.
- **Rollback Requirements**: The `REA_ENGINE_MODE` kill-switch must be demonstrably tested on the target hardware before activating capital.

## F. Production Safety Controls
Live operations are natively constrained by:
- **AntiBleedGuard**: Halts the execution loop intrinsically if rapid successive losses violate the Daily Loss Limits.
- **Margin Controls**: Evaluates available purchasing power directly from the broker's snapshot prior to orchestrating size.
- **Risk Controls**: Prevents concentration via hard asset-class boundary checks.
- **RBAC Controls**: Demands authenticated Session keys mapped strictly to `can_execute_live_trading`.
- **Broker Controls**: Specific `LIVE` keys must match specific broker URI endpoints to prevent test-capital logic from bleeding to live accounts.
- **Capital Controls**: The core `TradeRuntimeService` ensures sizing ratios never mathematically exceed the total account equity bound.

## G. Production Change Management Rules
1. Core logic bounds (e.g., limits arrays, adapter APIs) cannot be modified without re-running the complete Phase 107/108 Certification Test Matrix.
2. Production configuration patches (e.g., changing margin tolerance from 2% to 3%) require an explicit audit branch and dual-approval PR.

## H. Remaining Production Risks
- Operational Drift: The operator failing to sync the production database with correct margin configuration limits prior to execution. Mitigated by `AntiBleedGuard` failing closed on unknown inputs.
- With this framework complete, the formal code and configuration boundaries of CSS are entirely resolved for production operations.

## I. Final Framework Certification
The CSS Capital Limits and Production Configuration Framework formally certifies the structural and limit boundaries necessary to support live institutional execution safely and responsibly.
