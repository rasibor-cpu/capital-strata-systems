from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

from backend.options.income_position_metrics import IncomePositionMetricsCalculator
from backend.options.options_income_api import OPTIONS_INCOME_API_ROUTES, build_options_income_api_payload, create_options_income_router
from backend.options.options_income_dashboard import OptionsIncomeDashboardBuilder, build_options_income_dashboard
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.options_income_portfolio import OptionsIncomePortfolioConstructor
from backend.options.options_income_risk_governance import OptionsIncomeRiskGovernanceEngine
from backend.options.options_income_stress_testing import OptionsIncomeStressTester
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperPositionRepository
from backend.options.position_health import PositionHealthAnalyzer
from backend.trading.option_contract import CanonicalOptionContract

import backend.options.options_income_api as api_module
import backend.options.options_income_dashboard as dashboard_module


AS_OF = date(2026, 7, 14)
ENTRY_DATE = AS_OF.isoformat()
NEAR_EXPIRY = (AS_OF + timedelta(days=25)).isoformat()
EXPIRY_1 = (AS_OF + timedelta(days=30)).isoformat()
EXPIRY_2 = (AS_OF + timedelta(days=37)).isoformat()
EXPIRY_3 = (AS_OF + timedelta(days=17)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(option_type: str, *, underlying: str, expiry: str, strike: float | None = None, volume: int = 200) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
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
            "volume": volume,
            "open_interest": 700,
            "implied_volatility": 0.20,
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


def _call_candidate(underlying: str = "SPY", expiry: str = EXPIRY_1, *, include_rejected: bool = False):
    return IncomeOpportunityScanner().scan_covered_calls(
        [
            _contract("CALL", underlying=underlying, expiry=expiry),
            _contract("CALL", underlying=underlying, expiry=expiry, strike=130.0, volume=1),
        ],
        underlying_symbol=underlying,
        underlying_price=100.0,
        underlying_quantity=100,
        as_of=AS_OF,
        include_rejected=include_rejected,
    )


def _put_candidate(underlying: str = "QQQ", expiry: str = EXPIRY_2):
    return IncomeOpportunityScanner().scan_cash_secured_puts(
        [_contract("PUT", underlying=underlying, expiry=expiry)],
        underlying_symbol=underlying,
        cash_collateral_available=9500.0,
        underlying_price=100.0,
        as_of=AS_OF,
    )[0]


def _active_position(repository: PaperPositionRepository, *, candidate=None):
    engine = PaperIncomeLifecycleEngine(repository=repository, clock=_clock)
    position = engine.create_position(candidate or _call_candidate("AAPL", EXPIRY_3)[0], entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    engine.open_position(position.position_id)
    return engine, engine.activate_position(position.position_id)


def _dashboard_fixture():
    repository = PaperPositionRepository()
    engine, active = _active_position(repository)
    completed_seed = _put_candidate("MSFT", EXPIRY_2)
    completed_engine = PaperIncomeLifecycleEngine(repository=repository, clock=_clock)
    completed_created = completed_engine.create_position(completed_seed, entry_date=ENTRY_DATE)
    completed_engine.approve_position(completed_created.position_id)
    completed_engine.open_position(completed_created.position_id)
    completed_active = completed_engine.activate_position(completed_created.position_id)
    completed = completed_engine.process_expiration(completed_active.position_id, underlying_price=100.0, as_of=EXPIRY_2)
    manager = OptionsPositionManager(paper_repository=repository)
    roll = manager.recommend_paper_income_roll(active.position_id, as_of=NEAR_EXPIRY, underlying_price=110.0, delta=0.60, moneyness="ITM")
    health = PositionHealthAnalyzer().calculate(active, as_of=NEAR_EXPIRY, underlying_price=110.0, delta=0.60, moneyness="ITM").to_dict()
    metrics = IncomePositionMetricsCalculator().calculate(active, as_of=NEAR_EXPIRY).to_dict()
    opportunities = _call_candidate(include_rejected=True) + [_put_candidate()]
    portfolio = OptionsIncomePortfolioConstructor().construct(
        portfolio_id="OI008-PAPER",
        total_capital=60000,
        opportunities=[_call_candidate()[0], _put_candidate()],
        existing_positions=[active],
        sector_by_underlying={"SPY": "ETF", "QQQ": "ETF", "AAPL": "TECH"},
        annual_target_yield=0.10,
    ).to_dict()
    symbols = [row["option_symbol"] for row in portfolio["allocations"]]
    greeks = {symbol: {"delta": 0.05, "gamma": 0.001, "theta": -0.01, "vega": 0.01, "rho": 0.01} for symbol in symbols}
    ivs = {symbol: 0.22 for symbol in symbols}
    market = {
        "SPY": {"underlying_price": 100.0, "near_expiry_cutoff": EXPIRY_3},
        "QQQ": {"underlying_price": 100.0, "near_expiry_cutoff": EXPIRY_3},
        "AAPL": {"underlying_price": 110.0, "near_expiry_cutoff": EXPIRY_3},
    }
    assessment = OptionsIncomeRiskGovernanceEngine().assess(
        portfolio,
        greeks_by_symbol=greeks,
        iv_by_symbol=ivs,
        market_data_by_underlying=market,
    ).to_dict()
    stress = OptionsIncomeStressTester().run(
        portfolio,
        greeks=assessment["greeks_summary"],
        assignment=assessment["assignment_summary"],
    ).to_dict()
    payload = build_options_income_dashboard(
        opportunities=opportunities,
        positions=[active, completed],
        health_by_position={active.position_id: health},
        metrics_by_position={active.position_id: metrics},
        rolls_by_position={active.position_id: [roll]},
        portfolio=portfolio,
        risk_assessment=assessment,
        stress_report=stress,
        generated_at=NOW,
    )
    return payload, active, completed


def test_top_level_summary_and_paper_only_flags():
    payload, _, _ = _dashboard_fixture()

    assert payload["summary"]["engine_name"] == "CSS Options Income Engine"
    assert payload["summary"]["engine_version"] == "OI-008"
    assert payload["paper_only"] is True
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["summary"]["engine_status"] in {"ONLINE", "DEGRADED"}


def test_opportunity_payload_contains_accepted_and_rejected_candidates_stably():
    payload, _, _ = _dashboard_fixture()
    opportunities = payload["opportunities"]

    assert opportunities["accepted_opportunity_count"] >= 2
    assert opportunities["rejected_opportunity_count"] == 1
    assert opportunities["accepted_candidates"] == sorted(
        opportunities["accepted_candidates"],
        key=lambda row: (-row["ranking_score"], row["underlying"], row["expiry"], row["strike"], row["option_symbol"]),
    )
    assert opportunities["rejected_candidates"][0]["rejection_reasons"]


def test_position_payload_separates_active_and_completed_lifecycle_rows():
    payload, active, completed = _dashboard_fixture()

    assert [row["position_id"] for row in payload["positions"]["active_positions"]] == [active.position_id]
    assert [row["position_id"] for row in payload["positions"]["completed_positions"]] == [completed.position_id]
    assert payload["positions"]["active_positions"][0]["health_score"] > 0
    assert payload["positions"]["completed_positions"][0]["state"] == "COMPLETED"


def test_rolling_payload_is_advisory_only_and_non_executable():
    payload, active, _ = _dashboard_fixture()
    roll = payload["rolls"]["recommendations"][0]

    assert roll["position_id"] == active.position_id
    assert roll["recommendation"] in {"ROLL_FORWARD", "ROLL_UP", "ROLL_DOWN", "ROLL_OUT", "NO_ROLL"}
    assert roll["execution_allowed"] is False
    assert "order" not in json.dumps(roll).lower()


def test_portfolio_capital_diversification_laddering_and_income_targets():
    payload, _, _ = _dashboard_fixture()
    portfolio = payload["portfolio"]

    assert portfolio["capital_allocated"] > 0
    assert portfolio["portfolio_utilization"] > 0
    assert portfolio["covered_call_allocation"] > 0
    assert portfolio["cash_secured_put_allocation"] > 0
    assert portfolio["underlying_concentration"]
    assert portfolio["expiry_ladder"]["ladder_quality_score"] > 0
    assert portfolio["monthly_premium_target"] == 500.0
    assert portfolio["rebalancing_recommendation"]["execution_allowed"] is False


def test_greeks_risk_budget_limits_assignment_volatility_and_stress_payloads():
    payload, _, _ = _dashboard_fixture()

    assert payload["greeks"]["portfolio_delta"] != 0
    assert payload["risk"]["risk_budget_utilization"]
    assert payload["risk"]["risk_limit_status"] in {"GREEN", "AMBER", "RED", "UNAVAILABLE"}
    assert payload["risk"]["assignment_exposure"]["contracts_exposed"] > 0
    assert payload["risk"]["iv_availability"] == "GREEN"
    assert payload["risk"]["stress_test_summary"]["status"] in {"GREEN", "AMBER", "RED"}


def test_stress_test_display_is_stably_ordered_and_includes_worst_case():
    payload, _, _ = _dashboard_fixture()
    scenarios = payload["stress_tests"]["scenarios"]

    assert [row["scenario_name"] for row in scenarios] == sorted(row["scenario_name"] for row in scenarios)
    assert payload["stress_tests"]["worst_stress_scenario"]["estimated_loss"] == max(row["estimated_loss"] for row in scenarios)
    assert scenarios[0]["approximation_flags"]


def test_operational_status_online_and_stale_data_degraded():
    payload, _, _ = _dashboard_fixture()
    stale = OptionsIncomeDashboardBuilder().build(
        opportunities=[],
        positions=[],
        portfolio=payload["portfolio"],
        risk_assessment={**payload["risk"], "portfolio_risk_status": payload["risk"]["risk_status"]},
        stress_report={"scenarios": payload["stress_tests"]["scenarios"], "max_estimated_loss": 1.0},
        generated_at="2026-07-14T00:00:00+00:00",
        now="2026-07-14T01:00:01+00:00",
        max_age_seconds=900,
    )

    assert payload["operational_status"]["status"] in {"ONLINE", "DEGRADED"}
    assert stale["operational_status"]["data_freshness"] == "STALE"
    assert stale["operational_status"]["status"] == "DEGRADED"


def test_alerts_include_severity_and_execution_posture_rules():
    payload, _, _ = _dashboard_fixture()

    assert payload["alerts"]
    assert all(row["severity"] in {"INFO", "WARNING", "CRITICAL"} for row in payload["alerts"])
    assert all(row["paper_only"] is True and row["execution_allowed"] is False for row in payload["alerts"])
    assert payload["summary"]["alert_count"] == len(payload["alerts"])


def test_explainability_payload_is_deterministic_and_auditable():
    first, _, _ = _dashboard_fixture()
    second, _, _ = _dashboard_fixture()

    assert first["explainability"] == second["explainability"]
    assert {row["decision"] for row in first["explainability"]} >= {"OPPORTUNITY_ACCEPTED", "RISK_STATUS_ASSIGNED", "ALERT_RAISED"}
    assert all(row["source_modules"] for row in first["explainability"])


def test_idempotent_json_payload_shape():
    first, _, _ = _dashboard_fixture()
    second, _, _ = _dashboard_fixture()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True))["summary"]["execution_allowed"] is False


def test_missing_portfolio_fails_closed():
    payload = build_options_income_dashboard(generated_at=NOW)

    assert payload["summary"]["engine_status"] == "FAIL_CLOSED"
    assert payload["operational_status"]["status"] == "OFFLINE"
    assert payload["alerts"][0]["severity"] == "CRITICAL"


def test_invalid_numeric_and_non_finite_values_fail_closed():
    payload, _, _ = _dashboard_fixture()
    bad_portfolio = dict(payload["portfolio"])
    bad_portfolio["capital_allocated"] = float("inf")

    result = build_options_income_dashboard(
        positions=[],
        portfolio=bad_portfolio,
        risk_assessment={**payload["risk"], "portfolio_risk_status": payload["risk"]["risk_status"]},
        stress_report={"scenarios": payload["stress_tests"]["scenarios"]},
        generated_at=NOW,
    )

    assert result["summary"]["engine_status"] == "FAIL_CLOSED"


def test_live_mode_and_execution_enabled_posture_fail_closed():
    payload, _, _ = _dashboard_fixture()
    live = build_options_income_dashboard(portfolio=payload["portfolio"], risk_assessment=payload["risk"], generated_at=NOW, mode="LIVE")
    armed = build_options_income_dashboard(portfolio=payload["portfolio"], risk_assessment=payload["risk"], generated_at=NOW, execution_allowed=True)

    assert live["summary"]["engine_status"] == "FAIL_CLOSED"
    assert armed["summary"]["engine_status"] == "FAIL_CLOSED"


def test_missing_greeks_and_missing_iv_fail_closed():
    payload, _, _ = _dashboard_fixture()
    missing_greeks = build_options_income_dashboard(portfolio=payload["portfolio"], risk_assessment={**payload["risk"], "greeks_by_underlying": {}}, generated_at=NOW)
    missing_iv = build_options_income_dashboard(portfolio=payload["portfolio"], risk_assessment={**payload["risk"], "iv_availability": "UNAVAILABLE"}, generated_at=NOW)

    assert missing_greeks["summary"]["engine_status"] == "FAIL_CLOSED"
    assert missing_iv["summary"]["engine_status"] == "FAIL_CLOSED"


def test_duplicate_position_and_invalid_lifecycle_state_fail_closed():
    payload, active, _ = _dashboard_fixture()
    duplicate = build_options_income_dashboard(
        positions=[active, active],
        portfolio=payload["portfolio"],
        risk_assessment=payload["risk"],
        stress_report={"scenarios": payload["stress_tests"]["scenarios"]},
        generated_at=NOW,
    )
    bad_state = build_options_income_dashboard(
        positions=[{**active.to_dict(), "current_state": "BAD_STATE"}],
        portfolio=payload["portfolio"],
        risk_assessment=payload["risk"],
        stress_report={"scenarios": payload["stress_tests"]["scenarios"]},
        generated_at=NOW,
    )

    assert duplicate["summary"]["engine_status"] == "FAIL_CLOSED"
    assert bad_state["summary"]["engine_status"] == "FAIL_CLOSED"


def test_repository_corruption_marked_offline():
    payload, _, _ = _dashboard_fixture()
    corrupted = OptionsIncomeDashboardBuilder().build(
        portfolio=payload["portfolio"],
        risk_assessment=payload["risk"],
        stress_report={"scenarios": payload["stress_tests"]["scenarios"]},
        generated_at=NOW,
        repository_corruption=True,
    )

    assert corrupted["operational_status"]["repository_health"] == "OFFLINE"
    assert corrupted["operational_status"]["status"] == "OFFLINE"


def test_api_payload_shape_and_route_registration():
    payload, _, _ = _dashboard_fixture()

    section = build_options_income_api_payload(payload, "summary")
    assert section["section"] == "summary"
    assert section["data"]["engine_name"] == "CSS Options Income Engine"
    assert section["execution_allowed"] is False
    router = create_options_income_router(lambda: payload)
    paths = {getattr(route, "path", None) if not isinstance(route, dict) else route["path"] for route in router.routes}
    assert set(OPTIONS_INCOME_API_ROUTES.values()).issubset(paths)


def test_api_fails_closed_for_bad_section_and_unsafe_payload():
    payload, _, _ = _dashboard_fixture()
    bad_section = build_options_income_api_payload(payload, "bad")
    unsafe = build_options_income_api_payload({**payload, "execution_allowed": True}, "summary")

    assert bad_section["data"]["status"] == "FAIL_CLOSED"
    assert unsafe["summary"]["engine_status"] == "FAIL_CLOSED"


def test_dashboard_mobile_ready_contract_contains_expected_read_only_panels():
    payload, _, _ = _dashboard_fixture()
    mobile_panels = ["summary", "positions", "portfolio", "greeks", "risk", "stress_tests", "alerts"]

    assert all(panel in payload for panel in mobile_panels)
    assert payload["portfolio"]["assignment_concentration"] is not None
    assert payload["stress_tests"]["worst_stress_scenario"]
    assert "order" not in json.dumps({panel: payload[panel] for panel in mobile_panels}).lower()


def test_oi002_through_oi007_integration_paths_are_reused():
    payload, _, _ = _dashboard_fixture()

    assert payload["opportunities"]["accepted_candidates"][0]["oi002_builder_status"] == "PASS"
    assert payload["positions"]["active_positions"][0]["state"] == "ACTIVE"
    assert payload["portfolio"]["allocations"]
    assert payload["risk"]["approval_status"] in {"APPROVED_PAPER", "APPROVED_WITH_WARNINGS", "REJECTED_RISK_LIMIT", "REJECTED_INVALID_DATA"}


def test_no_broker_or_execution_authority_terms_added_to_oi008_modules():
    source = "\n".join(
        [
            inspect.getsource(dashboard_module),
            inspect.getsource(api_module),
        ]
    )

    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
    assert ".env" not in source
