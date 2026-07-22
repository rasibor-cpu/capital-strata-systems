from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.branding import get_brand_service
from backend.executive.business_calendar import BusinessCalendar
from backend.executive.executive_api import create_executive_intelligence_router
from backend.executive.executive_balance_sheet import build_balance_sheet
from backend.executive.executive_cashflow import build_cashflow_statement
from backend.executive.executive_commentary import ExecutiveCommentaryEngine
from backend.executive.executive_income_statement import build_income_statement
from backend.executive.executive_metrics import ExecutiveMetricEngine
from backend.executive.executive_models import (
    ExecutiveReport,
    ExecutiveReportType,
    PageOrientation,
    ReportSection,
    ReportTable,
    TrafficLight,
)
from backend.executive.executive_rendering import ExecutiveRenderingService
from backend.executive.executive_run_rate import ExecutiveRunRateEngine, RunRateInputs
from backend.executive.executive_scorecard import CATEGORY_WEIGHTS, ExecutiveScorecardEngine
from backend.executive.executive_service import ExecutiveIntelligenceService
from backend.reporting.pdf import EnterprisePDFRenderer


@pytest.fixture
def executive_state() -> dict:
    return {
        "current_date": "2026-07-21",
        "period_start": "2026-01-01",
        "period_end": "2026-07-21",
        "currency": "CAD",
        "revenue": 1000.0,
        "cost_of_revenue": 200.0,
        "operating_expenses": 300.0,
        "taxes": 100.0,
        "realized_pnl": 350.0,
        "unrealized_pnl": 50.0,
        "opening_equity": 10000.0,
        "portfolio_equity": 11000.0,
        "cash": 3000.0,
        "buying_power": 6000.0,
        "deployed_capital": 5000.0,
        "liabilities": 1000.0,
        "gross_exposure": 4000.0,
        "total_trades": 10,
        "wins": 6,
        "losses": 4,
        "winning_pnl": 900.0,
        "losing_pnl": -400.0,
        "returns": [0.01, -0.005, 0.015, 0.002],
        "equity_curve": [100.0, 120.0, 90.0, 110.0],
        "broker_allocation": {"coinbase": 0.5, "oanda": 0.5},
        "strategy_allocation": {"options": 0.6, "fx": 0.4},
        "asset_allocation": {"equity": 0.7, "cash": 0.3},
        "annual_target": 1000.0,
        "quarterly_target": 250.0,
        "monthly_target": 84.0,
        "trading_days": 252,
        "operating_cash_flow": 500.0,
        "investing_cash_flow": -100.0,
        "financing_cash_flow": 50.0,
        "opening_cash": 2550.0,
        "closing_cash": 3000.0,
        "investments": 7000.0,
        "receivables": 500.0,
        "other_assets": 500.0,
        "shareholders_equity": 10000.0,
        "executive_scores": {
            key: 82.0
            for key in CATEGORY_WEIGHTS
        },
    }


def test_canonical_metric_engine_calculates_each_metric_without_mutation(
    executive_state: dict,
) -> None:
    original = copy.deepcopy(executive_state)
    metrics = ExecutiveMetricEngine().calculate(executive_state)
    assert metrics["gross_profit"].value == 800.0
    assert metrics["operating_profit"].value == 500.0
    assert metrics["net_profit"].value == 400.0
    assert metrics["daily_return"].value == 0.1
    assert metrics["win_rate"].value == 0.6
    assert metrics["profit_factor"].value == 2.25
    assert metrics["maximum_drawdown"].value == 0.25
    assert metrics["current_drawdown"].value == pytest.approx(1 / 12, abs=1e-8)
    assert metrics["broker_allocation"].status == TrafficLight.GREEN
    assert executive_state == original


def test_canonical_financial_statements(executive_state: dict) -> None:
    income = build_income_statement(
        executive_state,
        period_start="2026-01-01",
        period_end="2026-07-21",
    )
    balance = build_balance_sheet(executive_state, as_of="2026-07-21")
    cashflow = build_cashflow_statement(
        executive_state,
        period_start="2026-01-01",
        period_end="2026-07-21",
    )
    assert income.lines[-1].key == "net_profit"
    assert income.lines[-1].amount == 400.0
    assert balance.balanced is True
    assert balance.lines[-1].amount == 11000.0
    assert cashflow.balanced is True
    assert cashflow.lines[-1].amount == 3000.0


def test_business_calendar_supports_weekends_holidays_and_exchange_extensions() -> None:
    calendar = BusinessCalendar.for_year(
        2026,
        exchange="NYSE",
        additional_holidays=[date(2026, 7, 2)],
    )
    assert calendar.is_business_day(date(2026, 7, 1)) is True
    assert calendar.is_business_day(date(2026, 7, 2)) is False
    assert calendar.is_business_day(date(2026, 7, 3)) is False
    assert calendar.is_business_day(date(2026, 7, 4)) is False
    assert calendar.next_business_day(date(2026, 7, 2)) == date(2026, 7, 6)


def test_run_rate_is_deterministic_and_uses_business_days() -> None:
    calendar = BusinessCalendar(exchange="TEST")
    inputs = RunRateInputs(
        annual_target=1000.0,
        quarterly_target=250.0,
        monthly_target=100.0,
        current_profit=400.0,
        current_date=date(2026, 7, 21),
        trading_days=252,
    )
    first = ExecutiveRunRateEngine().calculate(inputs, calendar=calendar)
    second = ExecutiveRunRateEngine().calculate(inputs, calendar=calendar)
    assert first == second
    assert first.elapsed_trading_days > 0
    assert first.remaining_trading_days == 252 - first.elapsed_trading_days
    assert first.required_daily_profit > 0
    assert 0.0 <= first.probability_of_meeting_target <= 1.0
    assert first.commentary


def test_weighted_scorecard_and_commentary_are_deterministic(
    executive_state: dict,
) -> None:
    scorecard = ExecutiveScorecardEngine().calculate(executive_state["executive_scores"])
    metrics = ExecutiveMetricEngine().calculate(executive_state)
    run_rate = ExecutiveRunRateEngine().calculate(
        RunRateInputs(
            annual_target=1000.0,
            quarterly_target=250.0,
            monthly_target=100.0,
            current_profit=400.0,
            current_date=date(2026, 7, 21),
            trading_days=252,
        ),
        calendar=BusinessCalendar(exchange="TEST"),
    )
    engine = ExecutiveCommentaryEngine()
    assert scorecard.weights_total == 1.0
    assert scorecard.overall_score == 82.0
    assert scorecard.overall_status == TrafficLight.GREEN
    assert engine.generate(metrics=metrics, scorecard=scorecard, run_rate=run_rate) == engine.generate(
        metrics=metrics,
        scorecard=scorecard,
        run_rate=run_rate,
    )


def test_service_package_is_serializable_read_only_and_single_model(
    executive_state: dict,
) -> None:
    original = copy.deepcopy(executive_state)
    service = ExecutiveIntelligenceService(state_provider=lambda: executive_state)
    package = service.build_package()
    public = {key: value for key, value in package.items() if key != "_objects"}
    json.dumps(public)
    assert package["safety"]["read_only"] is True
    assert package["safety"]["execution_allowed"] is False
    assert package["safety"]["runtime_mutation_allowed"] is False
    assert package["safety"]["broker_access_attempted"] is False
    assert executive_state == original
    report = service.canonical_report()
    assert report.as_dict()["safety"]["execution_allowed"] is False
    assert report.paper_size == "A4"


def test_pdf_is_a4_portrait_with_metadata_bookmarks_and_embedded_fonts(
    executive_state: dict,
) -> None:
    report = ExecutiveIntelligenceService(
        state_provider=lambda: executive_state
    ).canonical_report()
    rendered = EnterprisePDFRenderer().render(report)
    pdf = rendered["pdf_bytes"]
    assert pdf.startswith(b"%PDF-1.4")
    assert rendered["layout"]["paper_size"] == "A4"
    assert rendered["layout"]["orientation"] == "portrait"
    assert rendered["layout"]["width_points"] == pytest.approx(595.2756, abs=0.01)
    assert rendered["layout"]["height_points"] == pytest.approx(841.8898, abs=0.01)
    assert rendered["metadata"]["embedded_fonts"] is True
    assert rendered["metadata"]["bookmarks"]
    assert b"/Outlines" in pdf
    assert b"/FontFile2" in pdf
    assert rendered["safety"]["execution_allowed"] is False


def test_pdf_decorates_every_page_with_header_footer_and_watermark(
    executive_state: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.reporting.pdf.pdf_page_templates as templates

    calls = {"header": 0, "footer": 0, "watermark": 0}
    originals = {
        "header": templates.draw_header,
        "footer": templates.draw_footer,
        "watermark": templates.draw_watermark,
    }

    def wrap(name):
        def wrapped(*args, **kwargs):
            calls[name] += 1
            return originals[name](*args, **kwargs)

        return wrapped

    monkeypatch.setattr(templates, "draw_header", wrap("header"))
    monkeypatch.setattr(templates, "draw_footer", wrap("footer"))
    monkeypatch.setattr(templates, "draw_watermark", wrap("watermark"))
    report = ExecutiveIntelligenceService(
        state_provider=lambda: executive_state
    ).canonical_report()
    rendered = EnterprisePDFRenderer().render(report)
    assert calls == {
        "header": rendered["page_count"],
        "footer": rendered["page_count"],
        "watermark": rendered["page_count"],
    }


def test_wide_and_long_tables_switch_to_a4_landscape_and_paginate() -> None:
    columns = tuple(f"Column {index}" for index in range(10))
    rows = tuple(tuple(f"R{row}C{column}" for column in range(10)) for row in range(180))
    report = ExecutiveReport.create(
        report_type=ExecutiveReportType.BOARD_PACK,
        title="Wide Board Pack",
        subtitle="Landscape and pagination test",
        runtime_version="RC1.1",
        reporting_period="2026",
        classification=get_brand_service().document_standard.classification,
        generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        sections=(
            ReportSection(
                title="Long Table",
                tables=(ReportTable("Large Evidence Matrix", columns, rows),),
            ),
        ),
    )
    rendered = EnterprisePDFRenderer().render(report)
    assert report.orientation == PageOrientation.LANDSCAPE
    assert rendered["layout"]["orientation"] == "landscape"
    assert rendered["layout"]["paper_size"] == "A4"
    assert rendered["page_count"] > 3


def test_empty_report_and_derived_renderers_remain_usable() -> None:
    report = ExecutiveReport.create(
        report_type=ExecutiveReportType.EXECUTIVE_SUMMARY,
        title="Empty Executive Report",
        subtitle="No evidence",
        runtime_version="RC1.1",
        reporting_period="UNAVAILABLE",
        classification=get_brand_service().document_standard.classification,
        sections=(),
    )
    rendering = ExecutiveRenderingService()
    assert rendering.pdf(report)["pdf_bytes"].startswith(b"%PDF")
    assert "No report content available" in rendering.html(report)
    assert rendering.print_preview(report) == rendering.html(report)
    assert rendering.api(report)["paper"]["size"] == "A4"


def test_executive_api_is_get_only_serializable_and_non_mutating(
    executive_state: dict,
) -> None:
    original = copy.deepcopy(executive_state)
    app = FastAPI()
    router = create_executive_intelligence_router(
        state_provider=lambda: executive_state
    )
    app.include_router(router)
    client = TestClient(app)
    paths = (
        "/executive/summary",
        "/executive/kpis",
        "/executive/scorecard",
        "/executive/income",
        "/executive/balance-sheet",
        "/executive/cashflow",
        "/executive/run-rate",
        "/executive/risk",
        "/executive/commentary",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["safety"]["execution_allowed"] is False
        assert client.post(path).status_code == 405
    assert executive_state == original
    route_methods = {
        method
        for route in router.routes
        if getattr(route, "path", "").startswith("/executive/")
        for method in (getattr(route, "methods", set()) or set())
    }
    assert route_methods == {"GET"}


def test_foundation_has_no_broker_imports_or_direct_brand_asset_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = list((root / "backend/executive").glob("*.py"))
    sources += list((root / "backend/reporting/pdf").glob("*.py"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "backend.brokers" not in combined
    assert "assets/branding" not in combined
    assert "assets\\branding" not in combined
    assert "execute_trade" not in combined
    assert "live_order" not in combined
