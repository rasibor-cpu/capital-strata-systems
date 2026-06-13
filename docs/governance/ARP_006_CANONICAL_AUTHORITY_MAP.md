# ARP-006 Canonical Authority Map

## 1. Purpose

This document is the ARP-006 canonical CSS authority map. It identifies which implementations are authoritative for runtime behavior and which implementations are active support, legacy, archive, or retirement candidates.

This phase is documentation-only. No runtime behavior, broker adapter, dashboard behavior, risk rule, margin rule, security control, live-trading control, AntiBleedGuard, MarginTradeGate, live_toggle, live_arm, strategy logic, or credential handling was changed.

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

## 3. Classification Model

| Classification | Meaning |
| --- | --- |
| CANONICAL | Current authoritative implementation for primary runtime behavior. |
| ACTIVE_SUPPORT | Active helper, adapter, dashboard-local, or test-facing implementation used by a supported runtime path but not the primary authority. |
| LEGACY | Tracked older implementation retained in the repository with limited or unclear current runtime authority. |
| ARCHIVE | Historical implementation in archive paths or version snapshots. |
| RETIREMENT_CANDIDATE | Duplicate or generated implementation that should be retired, renamed, or quarantined after review. |

## 4. CSSUnifiedTradeGate Authority Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Backend unified trade gate | `backend/governance/css_unified_trade_gate.py` | `backend/intelligence/trade_decision_orchestrator.py`; `backend/app/brokers/live_readiness_certifier.py`; `tests/test_security_phase_alpha.py` | Yes | CANONICAL |
| Dashboard-local pre-register gate | `scripts/css_live_dashboard.py` | Local `css_unified_trade_gate` instance and `approve_trade_before_register(...)` | Yes, inside dashboard script only | ACTIVE_SUPPORT |
| R7 build insertion script | `scripts/build_r7_unified_trade_gate.py` | Build-time script references | No current runtime authority | RETIREMENT_CANDIDATE |
| Dashboard backup gate | `scripts/css_live_dashboard_PRE_J7_BACKUP.py` | Local backup script only | Not canonical | LEGACY |
| Dashboard backup gate | `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | Local backup script only | Not canonical | LEGACY |
| Archived dashboard gate copies | `archive/dashboard_versions/...` | Archive copies | No | ARCHIVE |

### CSSUnifiedTradeGate Determination

The backend canonical implementation is:

```text
backend/governance/css_unified_trade_gate.py
```

It governs backend trade decision authorization through `TradeDecisionOrchestrator` and live readiness certification. The dashboard-local `CSSUnifiedTradeGate` in `scripts/css_live_dashboard.py` is active support for dashboard pre-position registration and does not replace the backend authority.

Duplicate implementations affect runtime only when their owning script is executed. The backend execution decision path imports the canonical backend gate.

## 5. RiskGovernor Authority Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Execution risk governor | `engine/risk/risk_governor.py` | `engine/execution/execution_gate.py`; `engine/engine_loop.py` indirectly; `backend/app/run_live_guarded.py`; `run_sim_close.py`; `tests/engine/test_risk_governor.py` | Yes | CANONICAL |
| Legacy backend app risk governor | `backend/app/risk_governor.py` | No current canonical import found | Unclear / not canonical | LEGACY |
| Legacy nested backend app risk governor | `backend/app/risk/risk_governor.py` | No current canonical import found | Unclear / not canonical | LEGACY |
| Legacy engine risk module | `backend/app/engine_risk.py` | No current canonical import found | Unclear / not canonical | LEGACY |
| Portfolio risk governor | `backend/risk/portfolio_risk_governor.py` | `backend/engine/css_trading_engine_before_range_upgrade.py` | Only in older backend engine path | LEGACY |
| Dashboard cluster saturation governor | `scripts/css_live_dashboard.py` | Local dashboard cluster exposure logic | Yes, dashboard support only | ACTIVE_SUPPORT |

### RiskGovernor Determination

The canonical runtime `RiskGovernor` is:

```text
engine/risk/risk_governor.py
```

`ExecutionGate` imports this module inside its constructor and uses it for final `validate_trade(...)` approval after AntiBleedGuard, MarginTradeGate, compounding, volatility sizing, and drawdown scaling.

The duplicate `backend/app/...` governors do not currently govern the canonical `ExecutionGate` path. They remain legacy authority-surface risks because future imports could accidentally select the wrong implementation.

## 6. Dashboard Authority Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Current live dashboard | `scripts/css_live_dashboard.py` | Dashboard tests load this path directly; operator script path references itself in runtime metadata | Yes | CANONICAL |
| Margin dashboard helper | `scripts/css_live_dashboard.py` | `tests/test_margin_dashboard_integration.py`; dashboard runtime print path | Yes, display only | ACTIVE_SUPPORT |
| Greeks/options dashboard helpers | `scripts/css_live_dashboard.py` | `tests/test_options_greeks_dashboard.py`; options/greeks tests | Yes | ACTIVE_SUPPORT |
| Root legacy dashboard | `css_live_dashboard_v5.py` | Direct script execution only; has duplicate `display_dashboard` and `execute_trade` definitions | Not canonical | RETIREMENT_CANDIDATE |
| Dashboard backups | `scripts/css_live_dashboard_PRE_J7_BACKUP.py`; `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | Backup script execution only | Not canonical | LEGACY |
| Dashboard build scripts | `scripts/build_r*.py` | Build/version-generation scripts | No runtime dashboard authority | RETIREMENT_CANDIDATE |
| Archived dashboards | `archive/dashboard_versions/...` | Archive only | No | ARCHIVE |

### Dashboard Import Concern Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Current dashboard Coinbase data fallback | `scripts/css_live_dashboard.py` | Local `safe_load_runtime_asset(...)` | Yes, fallback-safe | CANONICAL |
| Scanner Coinbase data fallback | `backend/scanner/unified_market_scanner.py` | Scanner enrichment path | Yes, fallback-safe | ACTIVE_SUPPORT |
| Root dashboard direct import | `css_live_dashboard_v5.py` | Direct root dashboard execution | Risk if executed | RETIREMENT_CANDIDATE |
| Extended paper test direct import | `scripts/css_extended_paper_test.py` | Direct script execution | Risk if executed | ACTIVE_SUPPORT / RETIREMENT_CANDIDATE |

The canonical dashboard path is `scripts/css_live_dashboard.py`. It wraps `backend.data.coinbase_historical_downloader.load_runtime_asset` in a `ModuleNotFoundError` fallback. The root `css_live_dashboard_v5.py` remains a clean-clone risk because it imports the ignored/non-tracked module directly.

## 7. PnL Authority Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Engine loop equity/PnL tracking | `engine/performance/pnl_tracker.py` | `engine/engine_loop.py`; `scripts/css_live_dashboard.py`; tests and simulation helpers | Yes | CANONICAL |
| Dashboard open-position MTM authority | `scripts/css_live_dashboard.py` (`MarkToMarketEngine`) | Local dashboard runtime | Yes, dashboard runtime | CANONICAL for dashboard open positions |
| Dashboard closed-trade ledger append | `scripts/css_live_dashboard.py` (`append_closed_trade_ledger(...)`) | Local dashboard close path | Yes, dashboard ledger support | ACTIVE_SUPPORT |
| Dashboard accounting observer | `backend/app/accounting/pnl_engine.py` | `scripts/css_live_dashboard.py` imports `Portfolio`, `Position`, `NewPosition`; accounting tests | Yes, observer/support path | ACTIVE_SUPPORT |
| Durable PnL snapshot persistence | `backend/app/persistence/repositories/pnl_snapshot_repository.py`; `backend/app/persistence/services/pnl_runtime_service.py` | `PersistenceService`; runtime persistence service | Yes for persistence | ACTIVE_SUPPORT |
| Reporting PnL ledger | `engine/reporting/pnl_ledger.py`; `engine/reporting/pnl_report.py` | Structured test harness and reporting scripts | Yes for reporting/testing | ACTIVE_SUPPORT |
| Legacy backend PnL module | `backend/app/pnl/...` | Local legacy tests/imports | Not canonical | LEGACY |

### PnL Determination

There are multiple valid PnL surfaces by domain:

* Engine loop equity tracking is owned by `engine/performance/pnl_tracker.py`.
* Live dashboard open-position authority is `scripts/css_live_dashboard.py` `MarkToMarketEngine.self.positions`.
* Accounting snapshot/observer calculations are owned by `backend/app/accounting/pnl_engine.py`.
* Durable PnL persistence is owned by `backend/app/persistence/...`.
* Reporting ledgers are owned by `engine/reporting/...`.

These are not all competing authorities; they serve distinct runtime, dashboard, accounting, persistence, and reporting roles.

## 8. Session and Acceptance Authority Mapping

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Backend authentication | `backend/security/user_auth.py`; `backend/app/security/auth_gate.py`; `backend/app/security/user_registry.py` | Auth flows, security tests, dashboard startup wrapper where available | Yes | CANONICAL / ACTIVE_SUPPORT by runtime |
| Engine session manager | `engine/security/session_manager.py` | Engine security context and session tests | Yes for engine security flows | CANONICAL |
| Backend simple session manager | `backend/security/session_manager.py` | Backend security flows | Yes where backend security path is used | ACTIVE_SUPPORT |
| Dashboard startup/session context | `scripts/css_live_dashboard.py` | Local dashboard `authenticate_startup_user()`, session manager fallback, `SESSION_USER_CTX` | Yes, dashboard runtime | CANONICAL for dashboard session |
| Durable session persistence | `backend/app/persistence/repositories/session_repository.py`; `backend/app/persistence/services/session_runtime_service.py` | `PersistenceService`, runtime persistence consumers | Yes for persistence | ACTIVE_SUPPORT |
| Dashboard session recovery | `scripts/css_live_dashboard.py` (`SessionRecoveryEngine`) | Local dashboard save/load path | Yes, dashboard runtime | ACTIVE_SUPPORT |
| Legal acceptance model/service | `backend/app/compliance/legal_acceptance.py`; `backend/app/compliance/legal_acceptance_service.py`; `backend/app/compliance/legal_acceptance_enforcement.py` | Governance tests, compliance enforcement | Yes | CANONICAL |
| Legal acceptance repository | `backend/app/persistence/repositories/legal_acceptance_repository.py` | `PersistenceService`; lazy compliance package export | Yes for durable acceptance | ACTIVE_SUPPORT |
| live_toggle authorization | `backend/app/security/live_toggle.py` | Live authorization path and tests | Yes | CANONICAL |
| live_arm state | `backend/app/ops/live_arm.py` | `backend/app/security/live_toggle.py` | Yes | CANONICAL |

### Session Determination

Session authority is runtime-specific:

* Dashboard sessions are owned by `scripts/css_live_dashboard.py` startup/session context.
* Engine security sessions are owned by `engine/security/session_manager.py`.
* Backend authentication and app session support are split across backend security/auth modules.
* Durable session evidence is owned by persistence repositories/services.
* Legal acceptance authority is owned by compliance models/services/enforcement, with durable persistence through the repository.

## 9. Runtime Authority Summary

| Domain | Canonical File | Imported By | Runtime Active | Classification |
| ------ | -------------- | ----------- | -------------- | -------------- |
| Engine execution gate | `engine/execution/execution_gate.py` | `engine/engine_loop.py`; guarded/headless/live adapters; tests | Yes | CANONICAL |
| Anti-bleed safety | `backend/app/risk/anti_bleed_guard.py` | `engine/execution/execution_gate.py`; tests | Yes | CANONICAL |
| Margin trade gate | `engine/risk/margin_trade_gate.py` | `engine/execution/execution_gate.py`; dashboard display helper; tests | Yes | CANONICAL |
| Margin engine | `engine/risk/margin_engine.py` | `engine/engine_loop.py`; margin adapters/gate tests | Yes | CANONICAL |
| Broker execution boundary | `backend/app/brokers/execution_boundary.py` | `backend/app/brokers/live_readiness_certifier.py`; broker safety paths | Yes | CANONICAL |
| OANDA adapter | `backend/app/brokers/oanda_adapter.py`; `engine/risk/oanda_margin_adapter.py` | Dashboard/live paths; margin stack | Yes where selected | CANONICAL / ACTIVE_SUPPORT |
| Coinbase margin adapter | `engine/risk/coinbase_margin_adapter.py` | Margin stack and dashboard visibility | Yes where selected | ACTIVE_SUPPORT |
| Paper broker submit order interface | `engine/brokers/*_paper_broker.py`; `engine/brokers/base_broker.py` | Simulation/paper broker flows | Yes for paper | ACTIVE_SUPPORT |

## 10. Consolidation Recommendations

1. Declare `backend/governance/css_unified_trade_gate.py` the only canonical backend unified trade gate.
2. Declare `engine/risk/risk_governor.py` the only canonical execution RiskGovernor.
3. Keep `scripts/css_live_dashboard.py` as the canonical current dashboard, but document its local support authorities as dashboard-local.
4. Retire or quarantine `css_live_dashboard_v5.py`, dashboard backup files, and build-generated dashboard lineage scripts after Robert review.
5. Add lightweight governance checks to prevent new duplicate authority class names in active paths.
6. Preserve separate PnL authorities by domain instead of forcing all PnL surfaces into one module.

## 11. Documentation-Only Confirmation

Validation assertions for ARP-006:

* No runtime files were intentionally changed.
* No execution files were intentionally changed.
* No dashboard behavior was intentionally changed.
* No tests were changed.
* No broker adapters were changed.
* No credentials were changed.
* No risk, margin, security, live trading, strategy, or credential logic was changed.
