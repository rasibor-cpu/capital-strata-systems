"""Phase 177D — Options Income runtime integration tests."""

from __future__ import annotations

import backend.options.options_income_runtime_service as runtime_service
from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry
from backend.options.options_income_api import (
    OPTIONS_INCOME_API_ROUTES,
    build_options_income_api_payload,
    create_options_income_router,
)
from backend.options.options_income_reporting import build_options_income_executive_report
from backend.options.options_income_runtime_service import (
    OptionsIncomeRuntimeContext,
    STATUS_ADVISORY_READY,
    STATUS_ADVISORY_ONLY,
    STATUS_DATA_DEPENDENCY_BLOCKED,
    STATUS_FAILED,
    STATUS_NO_CURRENT_OPPORTUNITIES,
    STATUS_NO_OPEN_OPTION_POSITIONS,
    STATUS_PARTIAL_DATA,
    STATUS_STALE,
    STATUS_TARGET_NOT_CONFIGURED,
    build_mission_control_options_income,
    build_options_income_mobile_card,
    build_options_income_runtime_snapshot,
)
from backend.runtime.runtime_mode import resolve_runtime_mode
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.portfolio_projection import build_options_income_panel


def test_runtime_snapshot_deploys_without_fabricating_opportunities() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["deployment_state"] == "DEPLOYED"
    assert snap["opportunity_count"] == 0
    assert snap["engine_status"] == STATUS_DATA_DEPENDENCY_BLOCKED
    assert snap["status"] == STATUS_ADVISORY_ONLY
    assert "OPTION_CHAIN" in snap["missing_dependencies"]
    assert snap["execution_authority"] == "BLOCKED"
    assert snap["advisory_only"] is True
    assert snap["live_trading_enabled"] is False
    assert snap["state_hash"]


def test_no_current_opportunities_when_chains_present_but_empty() -> None:
    snap = build_options_income_runtime_snapshot(
        OptionsIncomeRuntimeContext(
            persist=False,
            option_chain_available=True,
            market_data_available=True,
            account_holdings_available=True,
            opportunities=[],
        )
    )
    assert snap["engine_status"] == STATUS_NO_CURRENT_OPPORTUNITIES
    assert snap["opportunity_count"] == 0


def test_advisory_readiness_precedes_empty_opportunity_outcome() -> None:
    cases = (
        ("DATA_DEPENDENCY_BLOCKED", ["BROKER_OPERATIONAL_READINESS"], STATUS_DATA_DEPENDENCY_BLOCKED),
        ("STALE", [], STATUS_STALE),
        ("PARTIAL_DATA", [], STATUS_PARTIAL_DATA),
    )
    for readiness, missing, expected in cases:
        snap = build_options_income_runtime_snapshot(
            OptionsIncomeRuntimeContext(
                persist=False,
                option_chain_available=True,
                market_data_available=True,
                account_holdings_available=True,
                opportunities=[],
                advisory_data={
                    "readiness_status": readiness,
                    "missing_dependencies": missing,
                    "stale": readiness == "STALE",
                    "partial": readiness == "PARTIAL_DATA",
                },
            )
        )
        assert snap["engine_status"] == expected
        assert snap["opportunity_outcome"] == "EVALUATION_BLOCKED"
        assert snap["opportunity_count"] == 0
        assert set(missing).issubset(set(snap["missing_dependencies"]))


def test_fully_ready_with_opportunity_is_advisory_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_service,
        "build_options_income_dashboard",
        lambda **kwargs: {
            "summary": {"engine_status": "READY"},
            "opportunities": {
                "accepted_candidates": [{"strategy_type": "COVERED_CALL", "symbol": "SPY"}],
                "rejected_candidates": [],
            },
            "positions": {},
        },
    )
    snap = build_options_income_runtime_snapshot(
        OptionsIncomeRuntimeContext(
            persist=False,
            option_chain_available=True,
            market_data_available=True,
            account_holdings_available=True,
            opportunities=[{"strategy_type": "COVERED_CALL", "symbol": "SPY"}],
            advisory_data={"readiness_status": "ADVISORY_READY", "missing_dependencies": []},
        )
    )
    assert snap["engine_status"] == STATUS_ADVISORY_READY
    assert snap["opportunity_count"] == 1
    assert snap["opportunity_outcome"] == "QUALIFYING_OPPORTUNITIES_FOUND"


def test_unexpected_scanner_fault_is_sanitized_failed(monkeypatch) -> None:
    def _raise(**kwargs):
        raise RuntimeError("access_token=secret-value account_number=123456")

    monkeypatch.setattr(runtime_service, "build_options_income_dashboard", _raise)
    snap = build_options_income_runtime_snapshot(
        OptionsIncomeRuntimeContext(
            persist=False,
            option_chain_available=True,
            market_data_available=True,
            account_holdings_available=True,
            opportunities=[],
            advisory_data={"readiness_status": "ADVISORY_READY", "missing_dependencies": []},
        )
    )
    assert snap["engine_status"] == STATUS_FAILED
    assert snap["correlation_id"]
    assert snap["failure_reason"] == "UNEXPECTED_PROVIDER_FAULT"
    assert "secret-value" not in str(snap)
    assert "123456" not in str(snap)


def test_premium_periods_separated() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    premium = snap["premium_accounting"]
    assert premium["session"]["measurement_period"] == "CURRENT_SESSION"
    assert premium["portfolio"]["measurement_period"] == "CURRENT_PORTFOLIO"
    assert premium["lifetime"]["measurement_period"] == "LIFETIME"
    assert premium["forecast_advisory"]["measurement_period"] == "FORECAST"


def test_target_not_configured_run_rate() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False, monthly_income_target=None))
    assert snap["run_rate"]["status"] == STATUS_TARGET_NOT_CONFIGURED


def test_run_rate_computed_when_target_set() -> None:
    snap = build_options_income_runtime_snapshot(
        OptionsIncomeRuntimeContext(
            persist=False,
            monthly_income_target=1000.0,
            current_month_actual_income=100.0,
            elapsed_days=10,
            remaining_days=20,
        )
    )
    assert snap["run_rate"]["status"] == "COMPUTED"
    assert snap["run_rate"]["target_attainment_percent"] == 10.0


def test_greeks_no_open_positions() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["greeks"]["status"] == STATUS_NO_OPEN_OPTION_POSITIONS


def test_rolling_recommendations_advisory_only() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["rolling"]["execution_allowed"] is False
    assert snap["rolling"]["order_submission"] == "BLOCKED"


def test_collateral_refuses_simulated_margin_inference() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["collateral"]["status"] == "ADVISORY_UNAVAILABLE"


def test_certification_and_readiness_separated() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["certification"]["outcome"] in {
        "ADVISORY_READY",
        "DATA_DEPENDENCY_BLOCKED",
        "PARTIALLY_READY",
        "CERTIFIED_ADVISORY",
    }
    assert snap["certification"]["live_ready"] is False
    assert snap["certification"]["execution_ready"] is False
    assert snap["operational_readiness"]


def test_mission_control_no_longer_not_yet_deployed() -> None:
    state = build_mission_control_state(allow_mock=True)
    options = state["options_income"]
    panel = state["options_income_panel"]
    assert options["status"] != "UNAVAILABLE"
    assert options["deployment_state"] == "DEPLOYED"
    assert panel["deployed"] is True
    assert panel["status"] != "NOT YET DEPLOYED"
    assert options["execution_blocked"] is True
    assert state["certification"]["options_income_certification"] not in {"UNAVAILABLE", "NOT YET DEPLOYED"}


def test_mobile_card_concise() -> None:
    card = build_options_income_mobile_card(OptionsIncomeRuntimeContext(persist=False))
    assert "options_income_status" in card
    assert "opportunity_count" in card
    assert card["execution_blocked"] is True
    assert card["detail_route"] == "/mission-control/options-income"


def test_api_routes_readonly_and_present() -> None:
    assert "/api/options-income" in OPTIONS_INCOME_API_ROUTES.values()
    assert "/api/options-income/status" in OPTIONS_INCOME_API_ROUTES.values()
    assert "/api/options-income/report" in OPTIONS_INCOME_API_ROUTES.values()
    assert "/api/options-income/certification" in OPTIONS_INCOME_API_ROUTES.values()
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    status = build_options_income_api_payload(snap, "status")
    assert status["section"] == "status"
    assert status["data"]["execution_authority"] == "BLOCKED"
    router = create_options_income_router(payload_provider=lambda: snap)
    methods = set()
    for route in getattr(router, "routes", []):
        methods |= set(getattr(route, "methods", set()) or set())
    assert not methods or "GET" in methods


def test_paginated_report_metadata() -> None:
    report = build_options_income_executive_report(
        ctx=OptionsIncomeRuntimeContext(persist=False),
        commit_reference="test",
    )
    assert report["execution_allowed"] is False
    assert report["document"]["page_count"] >= 3
    page_types = {p["page_type"] for p in report["document"]["pages"]}
    assert "cover" in page_types and "toc" in page_types and "summary" in page_types
    assert report["document"]["presentation"]["page_size"] == "A4"
    assert "html" in report


def test_runtime_resolver_and_broker_registry_unchanged() -> None:
    resolution = resolve_runtime_mode()
    assert resolution.runtime_mode.value == "DISABLED"
    assert resolution.execution_enabled is False
    brokers = get_canonical_broker_registry().list_brokers()
    assert brokers == list(TIER1_BROKERS)
    assert "IBKR" not in brokers


def test_provenance_present() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["provenance"]["engine"] == "OPTIONS_ENGINE"
    assert snap["premium_accounting"]["session"]["provenance"]
    assert snap["greeks"]["provenance"]


def test_frontend_contract_exposes_options_income_card() -> None:
    from dashboard.runtime.frontend_contract import build_frontend_payload

    payload = build_frontend_payload({})
    section = payload["sections"]["options_income"]
    assert section["execution_blocked"] is True
    assert "options_income_status" in section
    assert section["detail_route"] == "/mission-control/options-income"


def test_panel_mapping_from_mc_options() -> None:
    oi = build_mission_control_options_income(OptionsIncomeRuntimeContext(persist=False))
    panel = build_options_income_panel(
        {"options_income": oi, "runtime": {}, "runtime_snapshot": {}, "freshness": {}}
    )
    assert panel["deployed"] is True
    assert panel["status"] != "NOT YET DEPLOYED"
