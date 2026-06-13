# ARP-006 Runtime Import Map

## 1. Purpose

This document maps the current CSS runtime import and decision paths discovered during ARP-006. It complements `ARP_006_CANONICAL_AUTHORITY_MAP.md` by showing how the authoritative modules connect during runtime.

This phase is documentation-only. No runtime behavior was changed.

## 2. Pre-Check

Repository remote:

```text
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (fetch)
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (push)
```

Branch:

```text
css-evening-consolidation-2026-06-09
```

HEAD before ARP-006 documentation changes:

```text
82e6fde89e57cef654e8ecc0883e78be07b4eda9
```

## 3. Primary Engine Runtime Path

The primary engine loop imports:

```text
engine/engine_loop.py
  imports engine.execution.execution_gate.ExecutionGate
  imports engine.performance.pnl_tracker.PnLTracker
  imports engine.strategy.signal_engine.SignalEngine
  imports engine.core.position_book.PositionBook
  imports engine.portfolio.portfolio_capital_controller.PortfolioCapitalController
  imports engine.risk.margin_engine.MarginEngine
```

Observed decision flow:

```text
EngineLoop.step(...)
  -> SignalEngine
  -> regime/threshold/no-pyramiding checks
  -> MarginEngine.calculate(...)
  -> ExecutionGate.evaluate_trade(...)
       -> AntiBleedGuard.evaluate(...)
       -> MarginTradeGate.evaluate(...)
       -> CompoundingEngine.compute_dynamic_risk(...)
       -> VolatilityPositionSizer
       -> DrawdownScaler.scale(...)
       -> RiskGovernor.validate_trade(...)
  -> PortfolioCapitalController
  -> PositionBook
  -> PnLTracker
```

### Primary Engine Runtime Table

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Engine loop | `engine/engine_loop.py` | Simulation/replay entry points | Yes | CANONICAL |
| Execution gate | `engine/execution/execution_gate.py` | `engine/engine_loop.py`; adapters/tests | Yes | CANONICAL |
| AntiBleedGuard | `backend/app/risk/anti_bleed_guard.py` | `engine/execution/execution_gate.py` | Yes | CANONICAL |
| MarginTradeGate | `engine/risk/margin_trade_gate.py` | `engine/execution/execution_gate.py` | Yes | CANONICAL |
| MarginEngine | `engine/risk/margin_engine.py` | `engine/engine_loop.py` | Yes | CANONICAL |
| RiskGovernor | `engine/risk/risk_governor.py` | `engine/execution/execution_gate.py` | Yes | CANONICAL |
| PnLTracker | `engine/performance/pnl_tracker.py` | `engine/engine_loop.py` | Yes | CANONICAL |
| PortfolioCapitalController | `engine/portfolio/portfolio_capital_controller.py` | `engine/engine_loop.py` | Yes | CANONICAL |

## 4. ExecutionGate Internal Runtime Path

`ExecutionGate` intentionally imports dependencies inside `__init__` to reduce import-order traps:

```text
ExecutionGate.__init__
  -> backend.app.risk.anti_bleed_guard.AntiBleedGuard
  -> engine.capital.compounding_engine.CompoundingEngine
  -> engine.risk.drawdown_scaler.DrawdownScaler
  -> engine.risk.margin_trade_gate.MarginTradeGate
  -> engine.risk.risk_governor.RiskGovernor
  -> engine.risk.volatility_position_sizer.VolatilityPositionSizer
```

Enforced order inside `ExecutionGate.evaluate_trade(...)`:

```text
Trade request
  -> _evaluate_anti_bleed(...)
       -> BLOCK if missing/invalid inputs
       -> BLOCK if AntiBleedGuard rejects
  -> _evaluate_margin_trade(...)
       -> BLOCK if margin snapshot missing
       -> BLOCK if MarginTradeGate rejects
  -> CompoundingEngine
  -> VolatilityPositionSizer
  -> DrawdownScaler
  -> RiskGovernor.validate_trade(...)
       -> BLOCK if RiskGovernor rejects
  -> ALLOW
```

This means AntiBleedGuard and MarginTradeGate are enforced before final RiskGovernor approval in the canonical `ExecutionGate` path.

## 5. Backend Trade Decision Path

Backend intelligence imports:

```text
backend/intelligence/trade_decision_orchestrator.py
  imports backend.governance.css_unified_trade_gate.CSSUnifiedTradeGate
  imports backend.app.persistence.services.persistence_service.PersistenceService
  imports backend.app.persistence.services.session_runtime_service.SessionRuntimeService
  imports backend.app.persistence.services.trade_runtime_service.TradeRuntimeService
  imports backend.app.persistence.services.pnl_runtime_service.PnlRuntimeService
```

Backend trade decision flow:

```text
TradeDecisionOrchestrator
  -> CSSUnifiedTradeGate.approve_trade(...)
  -> persistence/session/trade/PnL runtime services
```

Backend canonical unified trade gate:

```text
backend/governance/css_unified_trade_gate.py
```

## 6. Live Readiness and Broker Boundary Path

Live readiness imports:

```text
backend/app/brokers/live_readiness_certifier.py
  imports backend.app.brokers.execution_boundary.validate_execution_boundary
  imports backend.governance.css_unified_trade_gate.CSSUnifiedTradeGate
```

Observed readiness flow:

```text
Live readiness certification
  -> validate_execution_boundary(...)
  -> CSSUnifiedTradeGate.approve_trade(...)
  -> readiness PASS/BLOCK evidence
```

Broker execution boundary authority:

```text
backend/app/brokers/execution_boundary.py
```

This path is separate from dashboard display and should remain the broker boundary authority unless superseded by a future approved remediation.

## 7. Dashboard Runtime Path

Current dashboard authority:

```text
scripts/css_live_dashboard.py
```

Dashboard startup/session flow:

```text
scripts/css_live_dashboard.py
  -> authenticate_startup_user()
  -> SESSION_USER_CTX
  -> session_manager fallback or available session manager
  -> enforce_execution_boundary()
  -> dashboard loop
```

Dashboard trade opening flow observed in `scripts/css_live_dashboard.py`:

```text
dashboard candidate
  -> approve_trade_before_register(...)
       -> dashboard-local CSSUnifiedTradeGate.approve_trade(...)
  -> optional broker test/load path
  -> MarkToMarketEngine.register_position(...)
  -> Portfolio / Position accounting observer path
  -> PnLTracker/dashboard state
```

Dashboard close/PnL ledger flow:

```text
open position dict
  -> MarkToMarketEngine close/update behavior
  -> append_closed_trade_ledger(...)
  -> closed trade ledger record
  -> dashboard summaries/reporting support
```

Dashboard margin visibility flow:

```text
margin_dashboard_lines(...)
  -> selected broker context
  -> OandaMarginAdapter or CoinbaseMarginAdapter or simulated fallback
  -> MarginEngine
  -> MarginTradeGate
  -> printed dashboard panel
```

Important boundary:

The dashboard margin panel is display-only. It does not enforce trades. Enforcement in the canonical execution path occurs through `engine/execution/execution_gate.py`.

## 8. Dashboard Import Concern Path

Current dashboard fallback:

```text
scripts/css_live_dashboard.py
  try imports backend.data.coinbase_historical_downloader.load_runtime_asset
  except ModuleNotFoundError defines safe fallback load_runtime_asset(...)
```

Scanner fallback:

```text
backend/scanner/unified_market_scanner.py
  try imports backend.data.coinbase_historical_downloader.load_runtime_asset
  except Exception sets self._load_runtime_asset = None
```

Risk surfaces:

```text
css_live_dashboard_v5.py
  direct import backend.data.coinbase_historical_downloader.load_runtime_asset
  no fallback

scripts/css_extended_paper_test.py
  direct import backend.data.coinbase_historical_downloader
  no fallback
```

The ignored/non-tracked `backend/data/coinbase_historical_downloader.py` dependency remains a concern for root/legacy direct-import consumers, not for the current canonical dashboard path.

## 9. PnL Runtime Paths

### Engine PnL

```text
engine/engine_loop.py
  -> engine.performance.pnl_tracker.PnLTracker
```

### Dashboard PnL

```text
scripts/css_live_dashboard.py
  -> MarkToMarketEngine.self.positions
  -> append_closed_trade_ledger(...)
  -> backend.app.accounting.pnl_engine.Portfolio / Position / NewPosition
  -> engine.performance.pnl_tracker.PnLTracker
```

### Durable PnL Persistence

```text
backend/app/persistence/services/pnl_runtime_service.py
  -> backend.app.persistence.services.persistence_service.PersistenceService
  -> backend.app.persistence.repositories.pnl_snapshot_repository.PnlSnapshotRepository
```

### Reporting PnL

```text
engine/reporting/pnl_ledger.py
engine/reporting/pnl_report.py
scripts/css_trade_attribution.py
scripts/css_session_analyzer.py
scripts/css_live_monitor.py
```

PnL authority is intentionally domain-specific: runtime equity, dashboard open positions, accounting snapshots, durable persistence, and reporting serve different operational purposes.

## 10. Session and Legal Acceptance Runtime Paths

### Dashboard Session Path

```text
scripts/css_live_dashboard.py
  -> authenticate_startup_user()
  -> SESSION_USER_CTX
  -> session_manager.get_session_status(...)
  -> session_manager.touch_session(...)
  -> session_manager.destroy_session(...)
  -> SessionRecoveryEngine.save_state(...)
  -> SessionRecoveryEngine.load_state(...)
```

### Backend/App Session Persistence Path

```text
backend/app/persistence/services/session_runtime_service.py
  -> backend.app.persistence.repositories.session_repository.SessionRepository
```

### Engine Security Session Path

```text
engine/security/session_manager.py
  -> engine/security/security_context.py
  -> engine/security/access_control.py
```

### Legal Acceptance Path

```text
backend/app/compliance/legal_acceptance.py
  -> backend.app.compliance.legal_acceptance_service.LegalAcceptanceService
  -> backend.app.compliance.legal_acceptance_enforcement.enforce_trading_session_acceptance(...)
  -> backend.app.persistence.repositories.legal_acceptance_repository.LegalAcceptanceRepository
```

ARP-005 remediated the compliance package-root circular import by making the package-root `LegalAcceptanceRepository` export lazy while preserving legal acceptance controls.

## 11. Live Authorization Path

Current live authorization components:

```text
backend/app/security/live_toggle.py
  -> backend.app.ops.live_arm.live_armed()
  -> RBAC/permission checks
```

Live authorization flow:

```text
User context
  -> live_toggle authorization
       -> fail closed if context/role/permission missing
       -> require SUPER_USER or explicit live permission
  -> live_arm state
       -> fail closed if not armed
  -> broker/execution boundary remains separate
```

This path is not a dashboard display path and should not be bypassed by dashboard code.

## 12. High-Level Runtime Diagram

```text
Engine / Strategy Candidate
  -> EngineLoop regime, threshold, no-pyramiding checks
  -> MarginEngine.calculate(...)
  -> ExecutionGate.evaluate_trade(...)
       -> AntiBleedGuard
       -> MarginTradeGate
       -> CompoundingEngine
       -> VolatilityPositionSizer
       -> DrawdownScaler
       -> RiskGovernor
  -> PortfolioCapitalController
  -> PositionBook
  -> PnLTracker
```

Backend governance path:

```text
TradeDecisionOrchestrator
  -> backend.governance.CSSUnifiedTradeGate
  -> runtime persistence services
```

Dashboard visibility / dashboard-local position path:

```text
scripts/css_live_dashboard.py
  -> authenticate_startup_user
  -> dashboard-local CSSUnifiedTradeGate
  -> MarkToMarketEngine.register_position
  -> accounting observer / PnLTracker
  -> dashboard summaries
```

Live broker readiness path:

```text
Live readiness request
  -> validate_execution_boundary
  -> backend.governance.CSSUnifiedTradeGate
  -> broker readiness decision
```

## 13. Documentation-Only Validation

ARP-006 validation assertions:

* No runtime files were intentionally changed.
* No execution files were intentionally changed.
* No dashboard behavior was intentionally changed.
* No tests were changed.
* No broker adapters were changed.
* No credentials were changed.
* No risk, margin, security, live trading, strategy, or credential logic was changed.
