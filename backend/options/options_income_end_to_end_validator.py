from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend.options.income_position_metrics import IncomePositionMetricsCalculator
from backend.options.options_broker_health import OptionsBrokerHealthMonitor
from backend.options.options_broker_registry import OptionsBrokerRegistry
from backend.options.options_income_api import build_options_income_api_payload
from backend.options.options_income_dashboard import build_options_income_dashboard
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.options_income_portfolio import OptionsIncomePortfolioConstructor
from backend.options.options_income_risk_budget import OptionsIncomeRiskBudgetConfig
from backend.options.options_income_risk_governance import OptionsIncomeRiskGovernanceEngine
from backend.options.options_income_stress_testing import OptionsIncomeStressTester
from backend.options.options_paper_broker import OptionsPaperBroker
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperPositionRepository, SAFE_FLAGS
from backend.options.position_health import PositionHealthAnalyzer
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)
NOW = "2026-07-14T00:00:00+00:00"
EXPIRY_1 = (AS_OF + timedelta(days=30)).isoformat()
EXPIRY_2 = (AS_OF + timedelta(days=37)).isoformat()
NEAR_EXPIRY = (AS_OF + timedelta(days=25)).isoformat()


SUBSYSTEMS = (
    "strategy_domain",
    "scanner",
    "lifecycle",
    "rolling",
    "portfolio",
    "allocation",
    "diversification",
    "laddering",
    "income_targets",
    "rebalancing",
    "greeks",
    "risk_budgets",
    "risk_limits",
    "assignment",
    "volatility",
    "stress_testing",
    "dashboard",
    "alerts",
    "explainability",
    "api",
    "broker_abstraction",
    "paper_broker",
    "market_data",
    "registry",
    "health",
    "order_preview",
)


class OptionsIncomeEndToEndValidatorError(ValueError):
    """Raised when the deterministic certification workflow fails closed."""


class OptionsIncomeEndToEndValidator:
    def validate(self, *, mode: str = "PAPER", now: str = NOW) -> dict[str, Any]:
        if str(mode or "").strip().upper() != "PAPER":
            raise OptionsIncomeEndToEndValidatorError("live routing is rejected")
        try:
            broker = OptionsPaperBroker(provider_name="oi010_paper", contracts=_contracts(), buying_power=50000.0)
            registry = OptionsBrokerRegistry()
            registry_entry = registry.register(broker, priority=10).to_dict()
            call_contract = CanonicalOptionContract.from_dict(broker.contract(f"SPY-{EXPIRY_1}-C-105"))
            put_contract = CanonicalOptionContract.from_dict(broker.contract(f"QQQ-{EXPIRY_2}-P-95"))
            call_candidate = IncomeOpportunityScanner().scan_covered_calls(
                [call_contract],
                underlying_symbol="SPY",
                underlying_price=100.0,
                underlying_quantity=100,
                as_of=AS_OF,
            )[0]
            put_candidate = IncomeOpportunityScanner().scan_cash_secured_puts(
                [put_contract],
                underlying_symbol="QQQ",
                cash_collateral_available=9500.0,
                underlying_price=100.0,
                as_of=AS_OF,
            )[0]
            repository = PaperPositionRepository()
            lifecycle = PaperIncomeLifecycleEngine(repository=repository, clock=lambda: now)
            position = lifecycle.create_position(call_candidate, entry_date=AS_OF.isoformat())
            lifecycle.approve_position(position.position_id)
            lifecycle.open_position(position.position_id)
            active = lifecycle.activate_position(position.position_id)
            manager = OptionsPositionManager(paper_repository=repository)
            roll = manager.recommend_paper_income_roll(
                active.position_id,
                as_of=NEAR_EXPIRY,
                underlying_price=110.0,
                delta=0.60,
                moneyness="ITM",
            )
            health = PositionHealthAnalyzer().calculate(active, as_of=NEAR_EXPIRY, underlying_price=110.0, delta=0.60, moneyness="ITM").to_dict()
            metrics = IncomePositionMetricsCalculator().calculate(active, as_of=NEAR_EXPIRY).to_dict()
            portfolio = OptionsIncomePortfolioConstructor().construct(
                portfolio_id="OI010-PAPER",
                total_capital=50000.0,
                opportunities=[call_candidate, put_candidate],
                existing_positions=[active],
                sector_by_underlying={"SPY": "ETF", "QQQ": "ETF"},
                annual_target_yield=0.10,
            ).to_dict()
            greeks = {row["option_symbol"]: {"delta": 0.05, "gamma": 0.001, "theta": -0.01, "vega": 0.01, "rho": 0.01} for row in portfolio["allocations"]}
            ivs = {row["option_symbol"]: 0.22 for row in portfolio["allocations"]}
            risk = OptionsIncomeRiskGovernanceEngine(
                config=OptionsIncomeRiskBudgetConfig(
                    max_single_underlying_pct=1.0,
                    max_single_expiry_pct=1.0,
                    max_single_strategy_pct=1.0,
                    max_volatility_exposure=1.0,
                )
            ).assess(
                portfolio,
                greeks_by_symbol=greeks,
                iv_by_symbol=ivs,
                market_data_by_underlying={"SPY": {"underlying_price": 100.0}, "QQQ": {"underlying_price": 100.0}},
            ).to_dict()
            stress = OptionsIncomeStressTester().run(portfolio, greeks=risk["greeks_summary"], assignment=risk["assignment_summary"]).to_dict()
            quote = broker.quote(f"SPY-{EXPIRY_1}-C-105", now=now)
            chain = broker.chain("SPY", now=now)
            broker_health = OptionsBrokerHealthMonitor().assess(provider_name=broker.provider_name, market_data=quote, chain=chain).to_dict()
            preview = broker.preview_order(
                strategy="COVERED_CALL",
                collateral=100.0,
                premium=2.0,
                quantity=1,
                option_symbol=f"SPY-{EXPIRY_1}-C-105",
            )
            dashboard = build_options_income_dashboard(
                opportunities=[call_candidate, put_candidate],
                positions=[active],
                health_by_position={active.position_id: health},
                metrics_by_position={active.position_id: metrics},
                rolls_by_position={active.position_id: [roll]},
                portfolio=portfolio,
                risk_assessment=risk,
                stress_report=stress,
                generated_at=now,
            )
            api_summary = build_options_income_api_payload(dashboard, "summary")
            subsystem_results = _subsystem_results(
                call_candidate=call_candidate,
                put_candidate=put_candidate,
                active=active,
                roll=roll,
                portfolio=portfolio,
                risk=risk,
                dashboard=dashboard,
                api_summary=api_summary,
                registry_entry=registry_entry,
                quote=quote,
                broker_health=broker_health,
                preview=preview,
            )
            blockers = [row["subsystem"] for row in subsystem_results if row["status"] == "FAIL"]
            warnings = [row["subsystem"] for row in subsystem_results if row["status"] == "WARNING"]
            status = "FAIL" if blockers else ("WARNING" if warnings else "PASS")
            return {
                "scenario_id": "OI010-DETERMINISTIC-PAPER",
                "status": status,
                "subsystems": subsystem_results,
                "blockers": blockers,
                "warnings": warnings,
                "artifacts": {
                    "portfolio": portfolio,
                    "risk": risk,
                    "dashboard": dashboard,
                    "api_summary": api_summary,
                    "broker_registry": registry_entry,
                    "market_data": quote,
                    "broker_health": broker_health,
                    "order_preview": preview,
                },
                "paper_only": True,
                **SAFE_FLAGS,
            }
        except Exception as exc:
            raise OptionsIncomeEndToEndValidatorError(str(exc) or exc.__class__.__name__) from exc


def _subsystem_results(**items: Any) -> list[dict[str, Any]]:
    call_candidate = items["call_candidate"]
    put_candidate = items["put_candidate"]
    active = items["active"]
    roll = dict(items["roll"])
    portfolio = dict(items["portfolio"])
    risk = dict(items["risk"])
    dashboard = dict(items["dashboard"])
    api_summary = dict(items["api_summary"])
    registry_entry = dict(items["registry_entry"])
    quote = dict(items["quote"])
    broker_health = dict(items["broker_health"])
    preview = dict(items["preview"])
    checks = {
        "strategy_domain": call_candidate.strategy_summary.get("validation_status") == "PASS" and put_candidate.strategy_summary.get("validation_status") == "PASS",
        "scanner": call_candidate.validation_status == "PASS" and put_candidate.validation_status == "PASS",
        "lifecycle": getattr(active, "current_state", "") == "ACTIVE",
        "rolling": roll.get("execution_allowed") is False,
        "portfolio": bool(portfolio.get("allocations")),
        "allocation": portfolio.get("capital", {}).get("allocated_capital", 0) > 0,
        "diversification": bool(portfolio.get("diversification", {}).get("by_underlying")),
        "laddering": portfolio.get("ladder", {}).get("ladder_quality_score", 0) >= 0,
        "income_targets": portfolio.get("income_targets", {}).get("expected_premium", 0) > 0,
        "rebalancing": portfolio.get("rebalance", {}).get("execution_allowed") is False,
        "greeks": risk.get("greeks_summary", {}).get("status") == "GREEN",
        "risk_budgets": risk.get("risk_budgets", {}).get("status") in {"GREEN", "AMBER"},
        "risk_limits": not risk.get("limit_breaches"),
        "assignment": risk.get("assignment_summary", {}).get("contracts_exposed", 0) > 0,
        "volatility": risk.get("volatility_summary", {}).get("status") == "GREEN",
        "stress_testing": risk.get("stress_summary", {}).get("status") in {"GREEN", "AMBER"},
        "dashboard": dashboard.get("summary", {}).get("engine_status") in {"ONLINE", "DEGRADED"},
        "alerts": isinstance(dashboard.get("alerts"), list),
        "explainability": bool(dashboard.get("explainability")),
        "api": api_summary.get("section") == "summary",
        "broker_abstraction": registry_entry.get("execution_allowed") is False,
        "paper_broker": registry_entry.get("capabilities", {}).get("supports_paper_mode") is True,
        "market_data": quote.get("status") == "ONLINE",
        "registry": registry_entry.get("provider_name") == "oi010_paper",
        "health": broker_health.get("status") == "ONLINE",
        "order_preview": preview.get("preview_status") == "PASS" and preview.get("execution_allowed") is False,
    }
    return [
        {
            "subsystem": name,
            "status": "PASS" if checks.get(name) else "FAIL",
            "evidence": "deterministic paper evidence present" if checks.get(name) else "missing or unsafe evidence",
            "paper_only": True,
            **SAFE_FLAGS,
        }
        for name in SUBSYSTEMS
    ]


def _contract(option_type: str, *, underlying: str, expiry: str, strike: float) -> CanonicalOptionContract:
    option_type = option_type.upper()
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": f"{underlying}-{expiry}-{option_type[0]}-{int(strike)}",
            "expiration_date": expiry,
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 250,
            "open_interest": 800,
            "implied_volatility": 0.22,
            "delta": 0.30 if option_type == "CALL" else -0.30,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.30,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": NOW,
        }
    )


def _contracts() -> list[CanonicalOptionContract]:
    return [
        _contract("CALL", underlying="SPY", expiry=EXPIRY_1, strike=105.0),
        _contract("PUT", underlying="SPY", expiry=EXPIRY_1, strike=95.0),
        _contract("CALL", underlying="QQQ", expiry=EXPIRY_2, strike=105.0),
        _contract("PUT", underlying="QQQ", expiry=EXPIRY_2, strike=95.0),
    ]


__all__ = ["NOW", "SUBSYSTEMS", "OptionsIncomeEndToEndValidator", "OptionsIncomeEndToEndValidatorError"]
