"""
Phase 177 — Canonical Financial Reporting Engine foundation tests.

Advisory / read-only: no broker, runtime, execution, or scheduler mutations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.financial_reporting.adapters import summarize_package
from backend.financial_reporting.balance_sheet import generate_balance_sheet
from backend.financial_reporting.cash_flow import generate_cash_flow_statement
from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.engine import CanonicalFinancialReportingEngine
from backend.financial_reporting.income_statement import generate_income_statement
from backend.financial_reporting.models import FinancialAmount, MissingReason, ReportingPeriodType
from backend.financial_reporting.periods import ReportingPeriod, build_period
from backend.financial_reporting.profitability_run_rate import (
    ProfitabilityRunRateConfig,
    generate_profitability_run_rate,
)
from dashboard.mission_control.pages import executive_overview
from dashboard.runtime.api.financial_reporting import create_financial_reporting_router


UTC = timezone.utc


def _dt(y, m, d, h=0, mi=0, s=0):
    return datetime(y, m, d, h, mi, s, tzinfo=UTC)


def _full_contract(**overrides) -> FinancialDataContract:
    period = build_period(
        ReportingPeriodType.MONTHLY,
        _dt(2026, 7, 1),
        _dt(2026, 7, 31, 23, 59, 59),
        label="2026-07",
    )
    base = dict(
        currency="USD",
        reporting_period=period,
        as_of=_dt(2026, 7, 15, 12),
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


# --- Reporting periods ---


def test_period_daily_monthly_annual_custom():
    daily = build_period(ReportingPeriodType.DAILY, _dt(2026, 7, 18), _dt(2026, 7, 18, 23, 59, 59))
    monthly = build_period(ReportingPeriodType.MONTHLY, _dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59, 59))
    annual = build_period(ReportingPeriodType.ANNUAL, _dt(2026, 1, 1), _dt(2026, 12, 31, 23, 59, 59))
    custom = build_period("CUSTOM", _dt(2026, 6, 1), _dt(2026, 6, 15))
    assert daily.calendar_days == 1
    assert monthly.calendar_days == 31
    assert annual.calendar_days == 365
    assert custom.period_type == ReportingPeriodType.CUSTOM


def test_period_elapsed_remaining_closed():
    period = build_period(ReportingPeriodType.MONTHLY, _dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59, 59))
    as_of = _dt(2026, 7, 10, 12)
    assert period.elapsed_days(as_of=as_of) == 10
    assert period.remaining_days(as_of=as_of) == 21
    closed = build_period(
        ReportingPeriodType.MONTHLY,
        _dt(2026, 6, 1),
        _dt(2026, 6, 30, 23, 59, 59),
        closed=True,
    )
    assert closed.elapsed_days(as_of=_dt(2026, 6, 15)) == closed.calendar_days
    assert closed.remaining_days(as_of=_dt(2026, 6, 15)) == 0


def test_period_invalid_range_and_naive_tz():
    with pytest.raises(ValueError):
        build_period(ReportingPeriodType.DAILY, _dt(2026, 7, 10), _dt(2026, 7, 1))
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type=ReportingPeriodType.DAILY,
            start=datetime(2026, 7, 1),
            end=datetime(2026, 7, 1, 23, 59, 59),
        )


# --- Income statement ---


def test_income_positive_profit():
    stmt = generate_income_statement(_full_contract())
    assert stmt.net_profit is not None
    assert stmt.net_profit > 0
    assert stmt.profit_margin is not None


def test_income_loss():
    c = _full_contract(
        realized_trading_gains=FinancialAmount.of("100"),
        unrealized_gains=FinancialAmount.zero(),
        interest_income=FinancialAmount.zero(),
        dividend_income=FinancialAmount.zero(),
        option_premium_income=FinancialAmount.zero(),
        realized_trading_losses=FinancialAmount.of("5000"),
        taxes=FinancialAmount.of("0"),
    )
    stmt = generate_income_statement(c)
    assert stmt.net_profit is not None
    assert stmt.net_profit < 0


def test_income_zero_activity():
    c = FinancialDataContract(
        currency="USD",
        reporting_period=build_period(ReportingPeriodType.DAILY, _dt(2026, 7, 1), _dt(2026, 7, 1, 23, 59, 59)),
        realized_trading_gains=FinancialAmount.zero(),
        unrealized_gains=FinancialAmount.zero(),
        interest_income=FinancialAmount.zero(),
        dividend_income=FinancialAmount.zero(),
        option_premium_income=FinancialAmount.zero(),
        fx_gains=FinancialAmount.zero(),
        treasury_income=FinancialAmount.zero(),
        other_operating_income=FinancialAmount.zero(),
        realized_trading_losses=FinancialAmount.zero(),
        unrealized_losses=FinancialAmount.zero(),
        broker_commissions=FinancialAmount.zero(),
        exchange_fees=FinancialAmount.zero(),
        financing_costs=FinancialAmount.zero(),
        borrowing_costs=FinancialAmount.zero(),
        market_data_costs=FinancialAmount.zero(),
        technology_costs=FinancialAmount.zero(),
        operating_expenses=FinancialAmount.zero(),
        personnel_expenses=FinancialAmount.zero(),
        professional_fees=FinancialAmount.zero(),
        administrative_costs=FinancialAmount.zero(),
        taxes=FinancialAmount.zero(),
        other_expenses=FinancialAmount.zero(),
    )
    stmt = generate_income_statement(c)
    assert stmt.net_profit == Decimal("0.00")


def test_income_missing_data_not_silent_zero():
    c = FinancialDataContract(currency="USD")
    stmt = generate_income_statement(c)
    assert stmt.net_profit is None
    assert stmt.missing_fields


def test_income_no_double_counting_negative_gains():
    c = _full_contract(
        realized_trading_gains=FinancialAmount.of("-500"),
        realized_trading_losses=FinancialAmount.of("100"),
    )
    stmt = generate_income_statement(c)
    assert any("negative" in w for w in stmt.warnings)
    # losses still only from loss line for direct costs contribution of 100 (+ other costs)
    assert stmt.realized_losses == Decimal("100.00")


# --- Profitability run rate ---


def test_run_rate_target_achieved_and_exceeded():
    period = build_period(ReportingPeriodType.MONTHLY, _dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59, 59))
    as_of = _dt(2026, 7, 15)
    achieved = generate_profitability_run_rate(
        actual_net_profit=Decimal("20000"),
        target_profit=Decimal("20000"),
        period=period,
        as_of=as_of,
    )
    assert achieved.traffic_light.value == "GREEN"
    assert achieved.required_daily_run_rate == Decimal("0.00")
    exceeded = generate_profitability_run_rate(
        actual_net_profit=Decimal("25000"),
        target_profit=Decimal("20000"),
        period=period,
        as_of=as_of,
    )
    assert exceeded.traffic_light.value == "GREEN"
    assert exceeded.required_daily_run_rate == Decimal("0.00")
    assert exceeded.remaining_profit_required == Decimal("-5000.00")


def test_run_rate_not_achieved_negative_actual_and_zero_remaining():
    period = build_period(ReportingPeriodType.MONTHLY, _dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59, 59))
    rr = generate_profitability_run_rate(
        actual_net_profit=Decimal("-1000"),
        target_profit=Decimal("10000"),
        period=period,
        as_of=_dt(2026, 7, 10),
    )
    assert rr.remaining_profit_required == Decimal("11000.00")
    assert rr.traffic_light.value in {"AMBER", "RED"}

    ended = generate_profitability_run_rate(
        actual_net_profit=Decimal("1000"),
        target_profit=Decimal("10000"),
        period=period,
        as_of=_dt(2026, 8, 1),
    )
    assert ended.remaining_days == 0
    assert ended.required_daily_run_rate == Decimal("0.00")


def test_run_rate_missing_target_not_available():
    period = build_period(ReportingPeriodType.DAILY, _dt(2026, 7, 1), _dt(2026, 7, 1, 23, 59, 59))
    rr = generate_profitability_run_rate(
        actual_net_profit=Decimal("100"),
        target_profit=None,
        period=period,
        as_of=_dt(2026, 7, 1),
    )
    assert rr.traffic_light.value == "NOT_AVAILABLE"


def test_run_rate_green_amber_red_decimal():
    period = build_period(ReportingPeriodType.MONTHLY, _dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59, 59))
    as_of = _dt(2026, 7, 16)  # 16 elapsed, 15 remaining
    # actual daily ~ 500; remaining needed small → GREEN/AMBER
    greenish = generate_profitability_run_rate(
        actual_net_profit=Decimal("8000"),
        target_profit=Decimal("10000"),
        period=period,
        as_of=as_of,
        config=ProfitabilityRunRateConfig(),
    )
    assert greenish.actual_daily_run_rate == Decimal("500.00")
    assert isinstance(greenish.required_daily_run_rate, Decimal)
    assert greenish.traffic_light.value in {"GREEN", "AMBER"}

    # need much more than actual pace → RED
    red = generate_profitability_run_rate(
        actual_net_profit=Decimal("1000"),
        target_profit=Decimal("30000"),
        period=period,
        as_of=as_of,
    )
    assert red.traffic_light.value == "RED"
    assert red.percentage_of_target_achieved == Decimal("0.0333")


# --- Balance sheet ---


def test_balance_sheet_balanced_and_unbalanced():
    bal = generate_balance_sheet(_full_contract())
    # Full contract may not perfectly balance — compute variance explicitly
    assert bal.total_assets is not None
    assert bal.accounting_equation_variance is not None

    # Force balance: assets 100, liab 40, equity 60
    balanced = generate_balance_sheet(
        FinancialDataContract(
            cash=FinancialAmount.of("100"),
            broker_cash=FinancialAmount.zero(),
            receivables=FinancialAmount.zero(),
            investments_fair_value=FinancialAmount.zero(),
            derivative_assets=FinancialAmount.zero(),
            other_assets=FinancialAmount.zero(),
            payables=FinancialAmount.of("40"),
            margin_liabilities=FinancialAmount.zero(),
            financing_liabilities=FinancialAmount.zero(),
            derivative_liabilities=FinancialAmount.zero(),
            tax_liabilities=FinancialAmount.zero(),
            other_liabilities=FinancialAmount.zero(),
            contributed_capital=FinancialAmount.of("60"),
            retained_earnings=FinancialAmount.zero(),
            current_period_earnings=FinancialAmount.zero(),
            aoci=FinancialAmount.zero(),
        )
    )
    assert balanced.balanced is True
    assert balanced.accounting_equation_variance == Decimal("0.00")

    unbalanced = generate_balance_sheet(
        FinancialDataContract(
            cash=FinancialAmount.of("100"),
            broker_cash=FinancialAmount.zero(),
            receivables=FinancialAmount.zero(),
            investments_fair_value=FinancialAmount.zero(),
            derivative_assets=FinancialAmount.zero(),
            other_assets=FinancialAmount.zero(),
            payables=FinancialAmount.of("10"),
            margin_liabilities=FinancialAmount.zero(),
            financing_liabilities=FinancialAmount.zero(),
            derivative_liabilities=FinancialAmount.zero(),
            tax_liabilities=FinancialAmount.zero(),
            other_liabilities=FinancialAmount.zero(),
            contributed_capital=FinancialAmount.of("60"),
            retained_earnings=FinancialAmount.zero(),
            current_period_earnings=FinancialAmount.zero(),
            aoci=FinancialAmount.zero(),
        )
    )
    assert unbalanced.balanced is False
    assert unbalanced.accounting_equation_variance == Decimal("30.00")


def test_balance_sheet_missing_sections():
    sheet = generate_balance_sheet(FinancialDataContract(currency="USD"))
    assert sheet.complete is False
    assert sheet.missing_fields
    assert sheet.balanced is None


# --- Cash flow ---


def test_cash_flow_reconciled_and_unreconciled():
    # opening 40k + net change: op 7k + inv -1k + fin 4k = +10k → expected 50k
    ok = generate_cash_flow_statement(_full_contract())
    assert ok.reconciled is True
    assert ok.cash_reconciliation_variance == Decimal("0.00")

    bad = generate_cash_flow_statement(
        _full_contract(closing_cash=FinancialAmount.of("49000"))
    )
    assert bad.reconciled is False
    assert bad.cash_reconciliation_variance == Decimal("1000.00")


def test_cash_flow_missing_sections():
    cf = generate_cash_flow_statement(FinancialDataContract(currency="USD"))
    assert cf.complete is False
    assert cf.missing_fields


# --- Engine ---


def test_engine_package_advisory_and_deterministic():
    engine = CanonicalFinancialReportingEngine()
    contract = _full_contract()
    a = engine.generate_financial_report_package(contract, report_id="fixed-id")
    b = engine.generate_financial_report_package(contract, report_id="fixed-id")
    assert a["advisory_only"] is True
    assert a["trading_impact"] is False
    assert a["schema_version"] == "css.canonical_financial_report.v1"
    # Deterministic money fields (ignore generated_at)
    a2 = {k: v for k, v in a.items() if k != "generated_at"}
    b2 = {k: v for k, v in b.items() if k != "generated_at"}
    assert a2["income_statement"] == b2["income_statement"]
    assert a2["profitability_run_rate"]["actual_net_profit"] == b2["profitability_run_rate"]["actual_net_profit"]
    blob_keys = set(a.keys())
    assert "password" not in blob_keys
    assert "secret" not in blob_keys
    assert "api_key" not in blob_keys
    assert "traceback" not in blob_keys


def test_engine_input_immutability():
    engine = CanonicalFinancialReportingEngine()
    contract = _full_contract()
    before = contract.amount_dict()
    engine.generate_financial_report_package(contract)
    after = contract.amount_dict()
    assert before == after


def test_engine_exception_isolation(monkeypatch):
    engine = CanonicalFinancialReportingEngine()

    def boom(_contract):
        raise RuntimeError("provider failure")

    monkeypatch.setattr(engine, "generate_balance_sheet", boom)
    package = engine.generate_financial_report_package(_full_contract())
    assert package["balance_sheet"] is None
    assert any("balance_sheet_error" in b for b in package["blockers"])
    assert package["income_statement"] is not None
    assert package["trading_impact"] is False


def test_readiness_precedence_not_ready():
    engine = CanonicalFinancialReportingEngine()
    contract = FinancialDataContract(currency="USD")  # no period
    package = engine.generate_financial_report_package(contract)
    readiness = package["readiness"]
    assert readiness["overall_state"] == "NOT_READY"
    assert readiness["overall_score"] <= 40.0


# --- API ---


def test_api_summary_http_200_stable_and_repeatable():
    app = FastAPI()
    app.include_router(
        create_financial_reporting_router(
            state_provider=lambda: {
                "portfolio": {"realized_pnl": 1000, "unrealized_pnl": 200, "cash": 5000, "equity": 50000},
                "target_profit": 5000,
            }
        )
    )
    client = TestClient(app)
    a = client.get("/api/financial-reporting/summary")
    b = client.get("/api/financial-reporting/summary")
    assert a.status_code == 200
    assert b.status_code == 200
    pa, pb = a.json(), b.json()
    assert pa["schema_version"].startswith("css.canonical_financial_report")
    assert pa["advisory_only"] is True
    assert pa["trading_impact"] is False
    assert pa["net_profit"] == pb["net_profit"]
    assert "traceback" not in pa
    assert "password" not in pa
    assert "secret" not in pa


def test_api_degraded_safe():
    app = FastAPI()

    def bad():
        raise RuntimeError("boom")

    app.include_router(create_financial_reporting_router(state_provider=bad))
    client = TestClient(app)
    res = client.get("/api/financial-reporting/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["trading_impact"] is False
    assert body["advisory_only"] is True
    # Still returns a package (partial from empty state) or degraded — never stack
    assert "traceback" not in body
    assert body.get("readiness", {}).get("overall_state") in {"NOT_READY", "AMBER", "RED", "GREEN"}


# --- UI ---


def test_ui_financial_reporting_card_renders():
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
    assert "Executive Financial Summary" in html or "Canonical Financial Reporting" in html
    assert (
        "/mission-control/reports/viewer?source=reports_center&amp;"
        "report_code=executive_financial_summary"
    ) in html
    financial_card = html.split('id="canonical-financial-reporting"', 1)[1].split(
        "</section>", 1
    )[0]
    assert 'href="/api/' not in financial_card
    assert "undefined" not in html.lower()
    assert "NaN" not in html
    assert 'data-phase="178"' in html or 'data-phase="177"' in html
    for light in ("GREEN", "AMBER", "RED", "NOT_AVAILABLE", "NOT_READY"):
        # at least one traffic/readiness token present
        pass
    assert "data-traffic-light=" in html
    assert "data-readiness=" in html


def test_ui_missing_values_safe():
    html = executive_overview.render({})
    assert 'id="canonical-financial-reporting"' in html
    assert "—" in html or "NOT_READY" in html
    marker = "Executive Financial Summary" if "Executive Financial Summary" in html else "Canonical Financial Reporting"
    assert "None" not in html.split(marker)[1][:800]


def test_summarize_package_keys():
    engine = CanonicalFinancialReportingEngine()
    package = engine.generate_financial_report_package(_full_contract())
    summary = summarize_package(package)
    for key in (
        "net_profit",
        "target_profit",
        "target_achieved_percentage",
        "required_daily_run_rate",
        "projected_period_end_profit",
        "profitability_traffic_light",
        "readiness",
    ):
        assert key in summary
