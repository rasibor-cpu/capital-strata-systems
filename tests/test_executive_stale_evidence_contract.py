from __future__ import annotations

from backend.executive_decision_intelligence.service import ExecutiveDecisionIntelligenceService
from dashboard.mission_control.pages.executive_overview import render


def _stale_state() -> dict:
    return {
        "platform": {
            "platform_status": "RED",
            "runtime_health": "RED",
            "runtime_mode": "DISABLED",
            "engine_mode": "UNAVAILABLE",
            "cycle": "UNAVAILABLE",
            "heartbeat": "2026-09-25T05:02:58Z",
            "broker_health": "RED",
            "runtime_offline": False,
        },
        "runtime": {
            "heartbeat_status": "STALE",
        },
        "portfolio": {
            "execution_status": "BLOCKED",
            "cash": 596.7317,
            "portfolio_value": 601.0005,
            "session_pnl": 393.3379,
            "open_positions": 10.0,
            "next_maturity": "UNAVAILABLE",
            "available_free": 601.0005,
            "realized_pnl": 393.0395,
            "unrealized_pnl": 0.2984,
            "equity": 601.0005,
            "buying_power": 596.7317,
            "operating_context": {
                "runtime_mode": "DISABLED",
                "advisory_only": True,
                "read_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "liquidity_margin": {
                "cash": 596.7317,
                "available_free": 601.0005,
                "buying_power": 596.7317,
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "maturity_expiry": {"status": "UNAVAILABLE"},
        },
        "risk": {"overall_risk_state": "RED"},
        "market_intelligence": {"market_regime": "DISABLED"},
        "alerts": {"count": "UNAVAILABLE"},
        "certification": {
            "rc1_platform_certification": "RED",
            "ready_for_live_trading": "NOT_CERTIFIED",
        },
        "data_freshness": {
            "overall_freshness": "STALE",
            "stale_mandatory_data": True,
            "last_runtime_heartbeat": "2026-09-25T05:02:58Z",
        },
        "executive_kpis": {},
        "operations_timeline": {},
        "institutional_executive_dashboard": {},
        "institutional_reporting": {},
        "broker_balance_summary": {"account_summary": {}},
        "safety": {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
    }


def test_edi_summary_withholds_fresh_sounding_conclusions_when_evidence_stale():
    summary = ExecutiveDecisionIntelligenceService().summary(_stale_state())
    assert summary["executive_state"] == "NOT_READY"
    assert summary["confidence"]["confidence_band"] == "VERY_LOW"
    assert summary["confidence"]["overall_confidence"] == 0.0
    assert summary["upstream"]["freshness_gate"] == "STALE_OR_UNAVAILABLE"
    assert "stale" in summary["top_risks"][0]["title"].lower()


def test_executive_overview_marks_secondary_financial_metrics_warn_when_stale():
    html = render(_stale_state())
    assert "STALE / SIMULATED SNAPSHOT" in html
    assert "Portfolio Equity" in html
    assert "Cash / Buying Power" in html
    assert "NOT_READY" in html
