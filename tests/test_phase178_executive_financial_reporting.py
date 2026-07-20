"""
Phase 178 — Executive Financial Reporting Suite tests.

Advisory / read-only. No broker, runtime, execution, or scheduler mutations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.executive_reporting.ei_adapter import executive_intelligence_financial_provider
from backend.executive_reporting.evidence_bridge import (
    financial_evidence_for_176j,
    merge_financial_evidence_into_176j,
)
from backend.executive_reporting.html_render import render_executive_financial_html
from backend.executive_reporting.management_actions import generate_management_actions
from backend.executive_reporting.narrative import generate_executive_narrative
from backend.executive_reporting.package import build_executive_financial_report_package
from backend.executive_reporting.service import ExecutiveFinancialReportingService
from backend.executive_reporting.summary import build_executive_financial_summary
from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.engine import CanonicalFinancialReportingEngine
from backend.financial_reporting.models import FinancialAmount, ReportingPeriodType
from backend.financial_reporting.periods import build_period
from backend.reporting.executive_brief_readiness_orchestrator import (
    ExecutiveBriefReadinessOrchestrator,
    evidence_from_mission_control_state,
)
from backend.reports_center.catalogue import build_catalogue
from backend.reports_center.producers import produce, producer_is_registered
from dashboard.mission_control.pages import executive_overview
from dashboard.runtime.api.executive_reporting import create_executive_reporting_router


UTC = timezone.utc


def _dt(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=UTC)


def _full_contract(**overrides) -> FinancialDataContract:
    period = build_period(
        ReportingPeriodType.MONTHLY,
        _dt(2026, 7, 1, 0),
        datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        label="2026-07",
    )
    base = dict(
        currency="USD",
        reporting_period=period,
        as_of=_dt(2026, 7, 15),
        realized_trading_gains=FinancialAmount.of("10000"),
        unrealized_gains=FinancialAmount.of("2000"),
        interest_income=FinancialAmount.of("100"),
        dividend_income=FinancialAmount.of("50"),
        option_premium_income=FinancialAmount.of("300"),
        fx_gains=FinancialAmount.zero(),
        treasury_income=FinancialAmount.zero(),
        other_operating_income=FinancialAmount.zero(),
        realized_trading_losses=FinancialAmount.of("1500"),
        unrealized_losses=FinancialAmount.of("200"),
        broker_commissions=FinancialAmount.of("100"),
        exchange_fees=FinancialAmount.of("50"),
        financing_costs=FinancialAmount.of("75"),
        borrowing_costs=FinancialAmount.zero(),
        market_data_costs=FinancialAmount.of("25"),
        technology_costs=FinancialAmount.of("400"),
        operating_expenses=FinancialAmount.of("100"),
        personnel_expenses=FinancialAmount.of("500"),
        professional_fees=FinancialAmount.of("150"),
        administrative_costs=FinancialAmount.of("50"),
        taxes=FinancialAmount.of("800"),
        other_expenses=FinancialAmount.zero(),
        cash=FinancialAmount.of("20000"),
        broker_cash=FinancialAmount.of("30000"),
        receivables=FinancialAmount.of("1000"),
        investments_fair_value=FinancialAmount.of("80000"),
        derivative_assets=FinancialAmount.of("2000"),
        other_assets=FinancialAmount.of("1000"),
        payables=FinancialAmount.of("3000"),
        margin_liabilities=FinancialAmount.of("5000"),
        financing_liabilities=FinancialAmount.of("2000"),
        derivative_liabilities=FinancialAmount.of("1000"),
        tax_liabilities=FinancialAmount.of("800"),
        other_liabilities=FinancialAmount.of("200"),
        contributed_capital=FinancialAmount.of("100000"),
        retained_earnings=FinancialAmount.of("12000"),
        current_period_earnings=FinancialAmount.of("10000"),
        aoci=FinancialAmount.zero(),
        operating_cash_inflows=FinancialAmount.of("15000"),
        operating_cash_outflows=FinancialAmount.of("8000"),
        investing_cash_inflows=FinancialAmount.of("1000"),
        investing_cash_outflows=FinancialAmount.of("2000"),
        financing_cash_inflows=FinancialAmount.of("5000"),
        financing_cash_outflows=FinancialAmount.of("1000"),
        opening_cash=FinancialAmount.of("40000"),
        closing_cash=FinancialAmount.of("50000"),
        target_profit=FinancialAmount.of("20000"),
    )
    base.update(overrides)
    return FinancialDataContract(**base)


def _pkg177(**overrides):
    engine = CanonicalFinancialReportingEngine()
    return engine.generate_financial_report_package(_full_contract(**overrides), report_id="t177")


# --- Summary ---


def test_summary_complete_and_decimal_safe():
    summary = build_executive_financial_summary(_pkg177())
    assert summary["advisory_only"] is True
    assert summary["trading_impact"] is False
    assert summary["net_profit"] is not None
    assert summary["schema_version"].startswith("css.executive_financial_summary")
    # decimal strings, not floats
    assert isinstance(summary["net_profit"], str)


def test_summary_missing_target_and_negative_profit():
    pkg = _pkg177(
        target_profit=FinancialAmount.missing(),
        realized_trading_gains=FinancialAmount.of("100"),
        unrealized_gains=FinancialAmount.zero(),
        interest_income=FinancialAmount.zero(),
        dividend_income=FinancialAmount.zero(),
        option_premium_income=FinancialAmount.zero(),
        realized_trading_losses=FinancialAmount.of("5000"),
        taxes=FinancialAmount.zero(),
    )
    summary = build_executive_financial_summary(pkg)
    assert summary["target_profit"] is None
    assert Decimal(str(summary["net_profit"])) < 0


def test_summary_target_exceeded():
    pkg = _pkg177(target_profit=FinancialAmount.of("100"))
    summary = build_executive_financial_summary(pkg)
    assert summary["profitability_traffic_light"] == "GREEN"


# --- Narrative ---


def test_narrative_profitable_and_deterministic():
    pkg = _pkg177()
    summary = build_executive_financial_summary(pkg)
    actions = generate_management_actions(summary=summary, phase177_package=pkg)
    a = generate_executive_narrative(summary=summary, phase177_package=pkg, management_actions=actions)
    b = generate_executive_narrative(summary=summary, phase177_package=pkg, management_actions=actions)
    assert a == b
    assert "profitable" in a["sections"]["profitability"].lower() or "profit" in a["sections"]["profitability"].lower()
    assert "audited statutory" in a["sections"]["executive_conclusion"].lower()
    # no trading instructions
    plain = a["plain_text"].lower()
    assert "buy " not in plain
    assert "sell " not in plain
    assert "execute" not in plain


def test_narrative_loss_and_missing_data():
    pkg = _pkg177(
        realized_trading_gains=FinancialAmount.of("10"),
        unrealized_gains=FinancialAmount.zero(),
        interest_income=FinancialAmount.zero(),
        dividend_income=FinancialAmount.zero(),
        option_premium_income=FinancialAmount.zero(),
        realized_trading_losses=FinancialAmount.of("9000"),
        taxes=FinancialAmount.zero(),
        target_profit=FinancialAmount.missing(),
    )
    summary = build_executive_financial_summary(pkg)
    narrative = generate_executive_narrative(summary=summary, phase177_package=pkg)
    assert "loss" in narrative["sections"]["profitability"].lower() or "zero" in narrative["sections"]["profitability"].lower()
    assert "target" in narrative["sections"]["target_progress"].lower()


# --- Package ---


def test_report_package_sections_and_safety():
    package = build_executive_financial_report_package(_pkg177(), report_id="fixed-178")
    for key in (
        "metadata",
        "financial_summary",
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "profitability_run_rate",
        "readiness",
        "narrative",
        "kpi_table",
        "management_actions",
        "evidence_index",
        "warnings",
        "limitations",
    ):
        assert key in package
    assert package["advisory_only"] is True
    assert package["trading_impact"] is False
    assert package["period_type"] in {
        "DAILY",
        "WEEKLY",
        "MONTHLY",
        "QUARTERLY",
        "YEAR_TO_DATE",
        "ANNUAL",
        "CUSTOM",
    }
    html = render_executive_financial_html(package)
    for heading in (
        "Executive Summary",
        "Financial Performance",
        "Profitability Target and Required Run Rate",
        "Income Statement",
        "Balance Sheet",
        "Cash Flow",
        "Key Risks and Data Limitations",
        "Management Actions",
    ):
        assert heading in html
    assert "audited statutory" in html.lower() or "ADVISORY ONLY" in html


def test_package_no_mutation_of_phase177():
    pkg177 = _pkg177()
    before = str(pkg177.get("report_id"))
    build_executive_financial_report_package(pkg177)
    assert pkg177.get("report_id") == before


# --- Reports Center ---


def test_reports_center_registration_and_produce():
    codes = {
        "executive_financial_summary",
        "canonical_income_statement",
        "canonical_balance_sheet",
        "canonical_cash_flow_statement",
        "profitability_run_rate_report",
    }
    catalogue_codes = {d.report_code for d in build_catalogue()}
    for code in codes:
        assert code in catalogue_codes
        assert producer_is_registered(code)
        produced = produce(code, filters={"report_date": "2026-07-15"}, repo_root=Path.cwd())
        assert produced["advisory_only"] is True
        assert produced.get("trading_impact") is False
        assert produced.get("html")
        assert produced.get("content") is not None


# --- Readiness 176J ---


def test_176j_detects_financial_outputs():
    pkg = build_executive_financial_report_package(_pkg177())
    evidence = financial_evidence_for_176j(pkg)
    assert evidence.get("income_statement")
    assert evidence.get("balance_sheet")
    assert evidence.get("cash_flow")
    assert evidence.get("financial_report_package", {}).get("present") is True

    orch = ExecutiveBriefReadinessOrchestrator()
    # Merge into otherwise empty financial slots
    base = {
        "runtime": {"status": "HEALTHY"},
        "broker_connectivity": {"status": "GREEN"},
        "portfolio_snapshot": {"equity": 1},
        "risk_metrics": {"status": "NORMAL"},
        "pnl": {"net_pnl": 1},
        "market_intelligence": {"status": "READY"},
        "ai_recommendation_summary": {"status": "READY"},
        "open_alerts": {"count": 0},
        "system_health": {"status": "HEALTHY"},
        "reporting_data_freshness": {"status": "FRESH", "age_seconds": 1},
    }
    merged = merge_financial_evidence_into_176j(base, pkg)
    report = orch.generate_report(evidence=merged)
    # Advisory financial components should not be missing
    missing = set(report.missing_datasets or [])
    assert "income_statement" not in missing
    assert "balance_sheet" not in missing
    assert "cash_flow" not in missing
    # State names remain 176J vocabulary
    assert report.overall_state in {"GREEN", "AMBER", "RED", "NOT_READY"}


def test_176j_mapper_from_mc_state_bridge():
    state = {
        "portfolio": {"realized_pnl": 1000, "cash": 5000, "equity": 40000},
        "target_profit": 2000,
        "platform": {"runtime_health": "HEALTHY", "broker_health": "GREEN", "platform_status": "HEALTHY"},
        "runtime": {"heartbeat_status": "HEALTHY"},
        "risk": {"status": "NORMAL"},
        "market_intelligence": {"status": "READY"},
        "alerts": {"count": 0},
        "data_freshness": {"overall_freshness": "FRESH", "age_seconds": 10},
    }
    evidence = evidence_from_mission_control_state(state)
    assert evidence.get("income_statement") is not None or evidence.get("financial_report_package")


# --- EI ---


def test_ei_adapter_no_mutation_deterministic():
    package = build_executive_financial_report_package(_pkg177(), report_id="ei-1")
    a = executive_intelligence_financial_provider(package)
    b = executive_intelligence_financial_provider(package)
    assert a == b
    assert a["mutable"] is False
    assert a["trading_impact"] is False
    assert "financial_headline" in a
    assert "management_actions" in a


# --- Management actions ---


def test_management_actions_conditions():
    summary = build_executive_financial_summary(
        _pkg177(target_profit=FinancialAmount.missing())
    )
    actions = generate_management_actions(summary=summary)
    codes = {a["code"] for a in actions}
    assert "missing_target_profit" in codes
    assert all(a["executable"] is False for a in actions)
    assert all(a["trading_impact"] is False for a in actions)


# --- API ---


def test_api_endpoints_stable_and_degraded():
    app = FastAPI()
    app.include_router(
        create_executive_reporting_router(
            state_provider=lambda: {
                "portfolio": {"realized_pnl": 1000, "cash": 5000, "equity": 50000},
                "target_profit": 5000,
            }
        )
    )
    client = TestClient(app)
    for path in (
        "/api/executive-reporting/financial-summary",
        "/api/executive-reporting/financial-report",
        "/api/executive-reporting/financial-narrative",
        "/api/executive-reporting/management-actions",
    ):
        a = client.get(path)
        b = client.get(path)
        assert a.status_code == 200
        assert b.status_code == 200
        assert a.json().get("trading_impact") is False or (
            path.endswith("financial-report") and a.json().get("trading_impact") is False
        )
        assert "traceback" not in a.json()
        assert "password" not in a.json()

    gen = client.post("/api/executive-reporting/generate")
    assert gen.status_code == 200
    body = gen.json()
    assert body["source_data_mutated"] is False
    assert body["trading_impact"] is False

    # degraded provider
    app2 = FastAPI()

    def bad():
        raise RuntimeError("boom")

    app2.include_router(create_executive_reporting_router(state_provider=bad))
    res = TestClient(app2).get("/api/executive-reporting/financial-summary")
    assert res.status_code == 200
    assert res.json().get("trading_impact") is False


# --- Mission Control ---


def test_mc_cards_render_phase178():
    html = executive_overview.render(
        {
            "portfolio": {"realized_pnl": 1000, "cash": 5000, "equity": 40000},
            "target_profit": 2000,
            "platform": {},
            "runtime": {},
            "risk": {},
            "market_intelligence": {},
            "alerts": {"count": 0},
            "certification": {},
            "data_freshness": {},
            "executive_kpis": {},
            "operations_timeline": {"events": []},
            "institutional_executive_dashboard": {},
            "institutional_reporting": {},
            "safety": {},
        }
    )
    assert 'id="canonical-financial-reporting"' in html
    assert "Executive Financial Summary" in html
    assert 'data-phase="178"' in html
    assert "undefined" not in html.lower()
    assert "NaN" not in html
    # NOT_AVAILABLE must not use good/green class alone without token
    if 'data-traffic-light="NOT_AVAILABLE"' in html:
        assert "mc-status good\">NOT_AVAILABLE" not in html


def test_service_end_to_end():
    service = ExecutiveFinancialReportingService()
    package = service.generate_from_contract(_full_contract(), report_id="svc-1")
    assert package["report_id"] == "svc-1"
    assert service.ei_provider({"target_profit": 1})["advisory_only"] is True
