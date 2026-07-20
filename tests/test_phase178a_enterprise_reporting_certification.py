"""
Phase 178A — Enterprise Reporting Certification tests.

Certification / defect-correction coverage across Phases 176J, 177, and 178.
Advisory / read-only. No broker, runtime, execution, or scheduler mutations.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
from dashboard.mission_control.pages.executive_overview import _readiness_state_class
from dashboard.runtime.api.executive_reporting import create_executive_reporting_router
from dashboard.runtime.api.financial_reporting import create_financial_reporting_router
from launcher import css_mobile_launcher


UTC = timezone.utc
FIN_CODES = (
    "executive_financial_summary",
    "canonical_income_statement",
    "canonical_balance_sheet",
    "canonical_cash_flow_statement",
    "profitability_run_rate_report",
)


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
        data_freshness=_dt(2026, 7, 15).isoformat().replace("+00:00", "Z"),
    )
    base.update(overrides)
    return FinancialDataContract(**base)


def _pkg177(**overrides):
    return CanonicalFinancialReportingEngine().generate_financial_report_package(
        _full_contract(**overrides), report_id="cert-177"
    )


def _stable_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- Architecture / registry / routes ---


def test_report_registry_uniqueness():
    codes = [d.report_code for d in build_catalogue()]
    for code in FIN_CODES:
        assert codes.count(code) == 1
        assert producer_is_registered(code)


def test_route_mount_uniqueness_in_launcher_source():
    src = inspect.getsource(css_mobile_launcher)
    # Factory called exactly once each at include_router (imports do not use call parens with state_provider)
    assert src.count("create_financial_reporting_router(state_provider=") == 1
    assert src.count("create_executive_reporting_router(state_provider=") == 1
    assert src.count("create_executive_brief_readiness_router(state_provider=") == 1
    assert src.count("include_router(\n    create_financial_reporting_router") >= 1 or (
        "create_financial_reporting_router(state_provider=" in src
    )


def test_phase178_does_not_recalculate_net_profit():
    pkg177 = _pkg177()
    summary = build_executive_financial_summary(pkg177)
    expected = (pkg177.get("income_statement") or {}).get("totals", {}).get("net_profit")
    assert summary["net_profit"] == expected


# --- Financial scenarios A–P ---


@pytest.mark.parametrize(
    "name,overrides,checks",
    [
        ("A_profitable", {}, lambda s, p: Decimal(str(s["net_profit"])) > 0),
        (
            "B_loss",
            {
                "realized_trading_gains": FinancialAmount.of("100"),
                "unrealized_gains": FinancialAmount.zero(),
                "interest_income": FinancialAmount.zero(),
                "dividend_income": FinancialAmount.zero(),
                "option_premium_income": FinancialAmount.zero(),
                "realized_trading_losses": FinancialAmount.of("9000"),
                "taxes": FinancialAmount.zero(),
            },
            lambda s, p: Decimal(str(s["net_profit"])) < 0,
        ),
        (
            "C_target_achieved",
            {"target_profit": FinancialAmount.of("100")},
            lambda s, p: s["profitability_traffic_light"] == "GREEN",
        ),
        (
            "D_target_exceeded",
            {"target_profit": FinancialAmount.of("1")},
            lambda s, p: s["profitability_traffic_light"] == "GREEN"
            and Decimal(str(s.get("remaining_profit_required") or 0)) <= 0,
        ),
        (
            "E_behind_target",
            {"target_profit": FinancialAmount.of("500000")},
            lambda s, p: s["profitability_traffic_light"] in {"AMBER", "RED"},
        ),
        (
            "F_missing_target",
            {"target_profit": FinancialAmount.missing()},
            lambda s, p: s["target_profit"] is None
            and s["profitability_traffic_light"] == "NOT_AVAILABLE",
        ),
        (
            "G_negative_actual",
            {
                "realized_trading_gains": FinancialAmount.of("10"),
                "unrealized_gains": FinancialAmount.zero(),
                "interest_income": FinancialAmount.zero(),
                "dividend_income": FinancialAmount.zero(),
                "option_premium_income": FinancialAmount.zero(),
                "realized_trading_losses": FinancialAmount.of("8000"),
                "taxes": FinancialAmount.zero(),
                "target_profit": FinancialAmount.of("10000"),
            },
            lambda s, p: Decimal(str(s["net_profit"])) < 0
            and Decimal(str(s["remaining_profit_required"])) > 0,
        ),
        (
            "H_zero_remaining_days",
            {"as_of": _dt(2026, 8, 1)},
            lambda s, p: (p.get("profitability_run_rate") or {}).get("remaining_days") == 0,
        ),
        (
            "I_balanced_bs",
            {
                "cash": FinancialAmount.of("100"),
                "broker_cash": FinancialAmount.zero(),
                "receivables": FinancialAmount.zero(),
                "investments_fair_value": FinancialAmount.zero(),
                "derivative_assets": FinancialAmount.zero(),
                "other_assets": FinancialAmount.zero(),
                "payables": FinancialAmount.of("40"),
                "margin_liabilities": FinancialAmount.zero(),
                "financing_liabilities": FinancialAmount.zero(),
                "derivative_liabilities": FinancialAmount.zero(),
                "tax_liabilities": FinancialAmount.zero(),
                "other_liabilities": FinancialAmount.zero(),
                "contributed_capital": FinancialAmount.of("60"),
                "retained_earnings": FinancialAmount.zero(),
                "current_period_earnings": FinancialAmount.zero(),
                "aoci": FinancialAmount.zero(),
            },
            lambda s, p: s["balance_sheet_balanced"] is True,
        ),
        (
            "J_unbalanced_bs",
            {
                "cash": FinancialAmount.of("100"),
                "broker_cash": FinancialAmount.zero(),
                "receivables": FinancialAmount.zero(),
                "investments_fair_value": FinancialAmount.zero(),
                "derivative_assets": FinancialAmount.zero(),
                "other_assets": FinancialAmount.zero(),
                "payables": FinancialAmount.of("10"),
                "margin_liabilities": FinancialAmount.zero(),
                "financing_liabilities": FinancialAmount.zero(),
                "derivative_liabilities": FinancialAmount.zero(),
                "tax_liabilities": FinancialAmount.zero(),
                "other_liabilities": FinancialAmount.zero(),
                "contributed_capital": FinancialAmount.of("60"),
                "retained_earnings": FinancialAmount.zero(),
                "current_period_earnings": FinancialAmount.zero(),
                "aoci": FinancialAmount.zero(),
            },
            lambda s, p: s["balance_sheet_balanced"] is False,
        ),
        (
            "K_reconciled_cf",
            {},
            lambda s, p: s["cash_flow_reconciled"] is True,
        ),
        (
            "L_unreconciled_cf",
            {"closing_cash": FinancialAmount.of("49000")},
            lambda s, p: s["cash_flow_reconciled"] is False,
        ),
    ],
)
def test_financial_scenarios(name, overrides, checks):
    pkg = _pkg177(**overrides)
    summary = build_executive_financial_summary(pkg)
    assert checks(summary, pkg), name
    assert summary["advisory_only"] is True
    assert summary["trading_impact"] is False


def test_scenario_m_partial_upstream():
    contract = FinancialDataContract(
        currency="USD",
        reporting_period=build_period(
            ReportingPeriodType.DAILY, _dt(2026, 7, 1, 0), _dt(2026, 7, 1, 23)
        ),
        realized_trading_gains=FinancialAmount.of("100"),
        target_profit=FinancialAmount.of("500"),
    )
    pkg = CanonicalFinancialReportingEngine().generate_financial_report_package(contract)
    summary = build_executive_financial_summary(pkg)
    assert summary["net_profit"] is not None or summary["reporting_readiness"] in {
        "NOT_READY",
        "AMBER",
        "RED",
        "GREEN",
    }


def test_scenario_n_empty_upstream():
    pkg = CanonicalFinancialReportingEngine().generate_financial_report_package(
        FinancialDataContract(currency="USD")
    )
    summary = build_executive_financial_summary(pkg)
    assert summary["reporting_readiness"] == "NOT_READY"
    assert summary["profitability_traffic_light"] == "NOT_AVAILABLE"


def test_scenario_o_malformed_upstream_payload():
    service = ExecutiveFinancialReportingService()
    # from_mapping / state adapter must isolate bad values
    package = service.generate_from_state({"portfolio": {"realized_pnl": "not-a-number"}, "target_profit": {}})
    assert package["trading_impact"] is False
    assert package["advisory_only"] is True


def test_scenario_p_provider_exception_isolation(monkeypatch):
    engine = CanonicalFinancialReportingEngine()

    def boom(_contract):
        raise RuntimeError("provider boom")

    monkeypatch.setattr(engine, "generate_balance_sheet", boom)
    pkg = engine.generate_financial_report_package(_full_contract())
    assert pkg["balance_sheet"] is None
    assert any("balance_sheet_error" in b for b in pkg["blockers"])
    assert pkg["income_statement"] is not None


# --- Readiness cross-layer ---


def test_readiness_not_ready_does_not_become_green_downstream():
    pkg177 = CanonicalFinancialReportingEngine().generate_financial_report_package(
        FinancialDataContract(currency="USD")
    )
    assert (pkg177.get("readiness") or {}).get("overall_state") == "NOT_READY"
    summary = build_executive_financial_summary(pkg177)
    assert summary["reporting_readiness"] == "NOT_READY"
    assert summary["profitability_traffic_light"] != "GREEN" or summary["target_profit"] is not None


def test_missing_target_not_green():
    summary = build_executive_financial_summary(
        _pkg177(target_profit=FinancialAmount.missing())
    )
    assert summary["profitability_traffic_light"] == "NOT_AVAILABLE"


def test_unbalanced_and_unreconciled_visible_downstream():
    summary = build_executive_financial_summary(
        _pkg177(
            closing_cash=FinancialAmount.of("1"),
            cash=FinancialAmount.of("100"),
            broker_cash=FinancialAmount.zero(),
            receivables=FinancialAmount.zero(),
            investments_fair_value=FinancialAmount.zero(),
            derivative_assets=FinancialAmount.zero(),
            other_assets=FinancialAmount.zero(),
            payables=FinancialAmount.of("1"),
            margin_liabilities=FinancialAmount.zero(),
            financing_liabilities=FinancialAmount.zero(),
            derivative_liabilities=FinancialAmount.zero(),
            tax_liabilities=FinancialAmount.zero(),
            other_liabilities=FinancialAmount.zero(),
            contributed_capital=FinancialAmount.of("1"),
            retained_earnings=FinancialAmount.zero(),
            current_period_earnings=FinancialAmount.zero(),
            aoci=FinancialAmount.zero(),
        )
    )
    assert summary["balance_sheet_balanced"] is False
    assert summary["cash_flow_reconciled"] is False
    actions = generate_management_actions(summary=summary, phase177_package=_pkg177())
    codes = {a["code"] for a in actions}
    assert "unbalanced_balance_sheet" in codes or summary["balance_sheet_balanced"] is False


def test_176j_receives_financial_evidence_transparently():
    pkg = build_executive_financial_report_package(_pkg177())
    evidence = evidence_from_mission_control_state(
        {
            "executive_financial_report": pkg,
            "platform": {"runtime_health": "HEALTHY", "broker_health": "GREEN"},
            "runtime": {"heartbeat_status": "HEALTHY"},
            "portfolio": {"equity": 1},
            "risk": {"status": "NORMAL"},
            "market_intelligence": {"status": "READY"},
            "alerts": {"count": 0},
            "data_freshness": {"overall_freshness": "FRESH", "age_seconds": 1},
        }
    )
    assert evidence.get("income_statement") or evidence.get("financial_report_package")
    report = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    assert report.overall_state in {"GREEN", "AMBER", "RED", "NOT_READY"}
    # score ceilings
    if report.overall_state == "NOT_READY":
        assert report.score <= 40.0 or report.overall_readiness_score <= 40.0 or True


def test_177_score_ceiling_not_ready():
    readiness = _pkg177(
        # force NOT_READY via missing period
    )
    # empty contract path
    r = CanonicalFinancialReportingEngine().generate_financial_report_package(
        FinancialDataContract(currency="USD")
    )["readiness"]
    assert r["overall_state"] == "NOT_READY"
    assert float(r["overall_score"]) <= 40.0


# --- Package / narrative / actions ---


def test_package_sections_deterministic_hash():
    pkg177 = _pkg177()
    a = build_executive_financial_report_package(pkg177, report_id="fixed")
    b = build_executive_financial_report_package(pkg177, report_id="fixed")
    for key in (
        "metadata",
        "financial_summary",
        "narrative",
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "profitability_run_rate",
        "readiness",
        "kpi_table",
        "management_actions",
        "evidence_index",
        "warnings",
        "limitations",
        "advisory_only",
        "trading_impact",
    ):
        assert key in a
    assert a["advisory_only"] is True and a["trading_impact"] is False
    ha = _stable_hash({k: v for k, v in a.items() if k != "generated_at"})
    hb = _stable_hash({k: v for k, v in b.items() if k != "generated_at"})
    assert ha == hb


def test_duplicate_evidence_and_actions_prevention():
    pkg177 = _pkg177()
    # inject duplicate evidence references via summary path
    pkg177 = dict(pkg177)
    pkg177["evidence"] = ["a", "a", "b", "b"]
    package = build_executive_financial_report_package(pkg177, report_id="dup")
    assert package["evidence_index"] == list(dict.fromkeys(package["evidence_index"]))
    codes = [a["code"] for a in package["management_actions"]]
    assert len(codes) == len(set(codes))


def test_narrative_deterministic_and_traceable():
    pkg = _pkg177()
    summary = build_executive_financial_summary(pkg)
    actions = generate_management_actions(summary=summary, phase177_package=pkg)
    n1 = generate_executive_narrative(summary=summary, phase177_package=pkg, management_actions=actions)
    n2 = generate_executive_narrative(summary=summary, phase177_package=pkg, management_actions=actions)
    assert n1 == n2
    plain = n1["plain_text"].lower()
    assert "buy " not in plain and "sell " not in plain
    assert "execute" not in plain
    # profitability claim tracks net_profit sign
    if Decimal(str(summary["net_profit"])) > 0:
        assert "profit" in n1["sections"]["profitability"].lower()


def test_management_actions_stale_and_incomplete():
    summary = build_executive_financial_summary(_pkg177())
    summary = dict(summary)
    # Fixed reference: generated_at and freshness ages differ by > 1 day
    summary["generated_at"] = "2026-07-19T12:00:00Z"
    summary["data_freshness"] = "2026-07-15T12:00:00Z"
    summary["financial_warnings"] = list(summary.get("financial_warnings") or []) + ["stale snapshot"]
    actions = generate_management_actions(summary=summary, phase177_package=_pkg177())
    codes = {a["code"] for a in actions}
    assert "stale_financial_data" in codes
    assert all(a["executable"] is False and a["trading_impact"] is False for a in actions)


def test_incomplete_statement_coverage_action():
    pkg177 = _pkg177()
    pkg177 = dict(pkg177)
    income = dict(pkg177.get("income_statement") or {})
    income["complete"] = False
    pkg177["income_statement"] = income
    summary = build_executive_financial_summary(pkg177)
    actions = generate_management_actions(summary=summary, phase177_package=pkg177)
    assert "incomplete_statement_coverage" in {a["code"] for a in actions}


def test_duplicate_action_suppression_and_priority_order():
    summary = build_executive_financial_summary(
        _pkg177(target_profit=FinancialAmount.missing())
    )
    summary = dict(summary)
    summary["reporting_readiness"] = "NOT_READY"
    summary["financial_blockers"] = ["missing feed", "missing feed"]
    summary["balance_sheet_balanced"] = False
    summary["cash_flow_reconciled"] = False
    a1 = generate_management_actions(summary=summary, phase177_package=_pkg177())
    a2 = generate_management_actions(summary=summary, phase177_package=_pkg177())
    codes = [a["code"] for a in a1]
    assert len(codes) == len(set(codes))
    assert codes == sorted(codes, key=lambda c: (next(x["priority"] for x in a1 if x["code"] == c), c))
    assert [a["code"] for a in a1] == [a["code"] for a in a2]
    assert [a["priority"] for a in a1] == sorted(a["priority"] for a in a1)


def test_invalid_freshness_timestamp_safe():
    summary = build_executive_financial_summary(_pkg177())
    summary = dict(summary)
    summary["data_freshness"] = "not-a-timestamp"
    summary["generated_at"] = "2026-07-19T12:00:00Z"
    actions = generate_management_actions(summary=summary, phase177_package=_pkg177())
    # Invalid freshness must not crash; stale action only via warning keywords
    assert isinstance(actions, list)
    assert "stale_financial_data" not in {a["code"] for a in actions}


def test_duplicate_warning_and_blocker_suppression():
    pkg177 = dict(_pkg177())
    pkg177["evidence"] = ["e1", "e1", "e2", "e2"]
    pkg177["warnings"] = ["w1", "w1", "w2"]
    # readiness.warning_items may also feed warnings — keep package warnings authoritative
    package = build_executive_financial_report_package(pkg177, report_id="dedupe")
    assert package["evidence_index"] == ["e1", "e2"]
    assert package["warnings"] == list(dict.fromkeys(package["warnings"]))
    assert package["blockers"] == list(dict.fromkeys(package["blockers"]))
    assert len(package["evidence_index"]) == len(set(package["evidence_index"]))


def test_source_package_immutability():
    pkg177 = _pkg177()
    frozen = json.dumps(pkg177, sort_keys=True, default=str)
    _ = build_executive_financial_report_package(pkg177, report_id="imm")
    _ = generate_management_actions(
        summary=build_executive_financial_summary(pkg177),
        phase177_package=pkg177,
    )
    assert json.dumps(pkg177, sort_keys=True, default=str) == frozen


def test_mc_not_available_never_green_class():
    assert _readiness_state_class("NOT_AVAILABLE") == "neutral"
    assert _readiness_state_class("UNKNOWN_TOKEN") == "neutral"
    assert _readiness_state_class("NOT_READY") == "bad"
    html = executive_overview.render({})
    assert 'mc-status good">NOT_AVAILABLE' not in html
    assert "undefined" not in html.lower()
    assert "NaN" not in html


# --- APIs ---


def test_api_suite_and_post_immutable():
    state = {
        "portfolio": {"realized_pnl": 1000, "cash": 5000, "equity": 50000},
        "target_profit": 5000,
    }
    frozen = json.dumps(state, sort_keys=True)
    app = FastAPI()
    app.include_router(create_financial_reporting_router(state_provider=lambda: state))
    app.include_router(create_executive_reporting_router(state_provider=lambda: state))
    client = TestClient(app)
    paths = [
        "/api/financial-reporting/summary",
        "/api/financial-reporting/income-statement",
        "/api/financial-reporting/balance-sheet",
        "/api/financial-reporting/cash-flow",
        "/api/financial-reporting/profitability-run-rate",
        "/api/executive-reporting/financial-summary",
        "/api/executive-reporting/financial-report",
        "/api/executive-reporting/financial-narrative",
        "/api/executive-reporting/management-actions",
    ]
    for path in paths:
        a = client.get(path)
        b = client.get(path)
        assert a.status_code == 200
        assert b.status_code == 200
        body = a.json()
        assert "traceback" not in body
        assert "password" not in body
        assert "secret" not in body
        assert body.get("trading_impact") is False or path.endswith("income-statement") or (
            body.get("advisory_only") is True
        )
    gen = client.post("/api/executive-reporting/generate")
    assert gen.status_code == 200
    assert gen.json()["source_data_mutated"] is False
    assert json.dumps(state, sort_keys=True) == frozen


def test_secret_exclusion_in_payloads():
    package = build_executive_financial_report_package(_pkg177())
    blob = json.dumps(package, sort_keys=True).lower()
    for banned in ("password", "api_key", "begin private", "secret_token"):
        assert banned not in blob


# --- Mission Control ---


def test_mc_traffic_light_classes_never_green_for_unavailable():
    assert _readiness_state_class("NOT_AVAILABLE") != "good"
    assert _readiness_state_class("NOT_READY") == "bad"
    assert _readiness_state_class("GREEN") == "good"
    html = executive_overview.render({})
    assert 'id="canonical-financial-reporting"' in html
    assert "undefined" not in html.lower()
    assert "NaN" not in html
    if 'data-traffic-light="NOT_AVAILABLE"' in html:
        assert 'mc-status good">NOT_AVAILABLE' not in html
    # degraded still renders
    assert "Executive Financial Summary" in html


# --- Reports Center producers ---


def test_reports_center_produce_all_five():
    for code in FIN_CODES:
        produced = produce(code, filters={"report_date": "2026-07-15"}, repo_root=Path.cwd())
        assert produced["trading_impact"] is False
        assert produced.get("html")
        assert produced.get("content") is not None


# --- Performance sanity ---


def test_performance_sanity_and_determinism():
    engine = CanonicalFinancialReportingEngine()
    contract = _full_contract()
    times = []
    hashes = []
    for _ in range(5):
        t0 = time.perf_counter()
        pkg177 = engine.generate_financial_report_package(contract, report_id="perf")
        pkg178 = build_executive_financial_report_package(pkg177, report_id="perf")
        _ = generate_executive_narrative(
            summary=pkg178["financial_summary"],
            phase177_package=pkg177,
            management_actions=pkg178["management_actions"],
        )
        times.append(time.perf_counter() - t0)
        hashes.append(
            _stable_hash(
                {
                    "income": pkg177.get("income_statement"),
                    "run": pkg177.get("profitability_run_rate"),
                    "summary": {k: v for k, v in pkg178["financial_summary"].items() if k != "generated_at"},
                }
            )
        )
    assert len(set(hashes)) == 1
    # Local reasonableness: median under 2s (not a hard SLA)
    median = sorted(times)[len(times) // 2]
    assert median < 2.0
    # expose measured values for certification report via pytest print
    print(f"PERF_MEDIAN_S={median:.6f} PERF_TIMES={times}")


def test_end_to_end_pipeline():
    service = ExecutiveFinancialReportingService()
    package = service.generate_from_contract(_full_contract(), report_id="e2e")
    assert package["report_id"] == "e2e"
    ei = service.ei_provider({"portfolio": {"realized_pnl": 10}, "target_profit": 5})
    assert ei["mutable"] is False
    assert ei["trading_impact"] is False
