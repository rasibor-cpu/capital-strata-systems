from datetime import datetime, timezone

from dashboard.runtime.frontend_contract import build_frontend_payload
from launcher import css_mobile_launcher as launcher


def _snapshot() -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "status": "AVAILABLE",
        "acquisition_timestamp": ts,
        "balances": {
            "acquisition_timestamp": ts,
            "combinedBalances": [
                {"currency": "CAD", "cash": -95.0, "marketValue": 1680.0, "totalEquity": 1585.0, "buyingPower": 3597.0}
            ],
        },
        "positions": {
            "acquisition_timestamp": ts,
            "positions": [
                {"symbol": "TD", "openQuantity": 5, "currentMarketValue": 608.15, "openPnl": 311.8525},
                {"symbol": "T.TO", "openQuantity": 10, "currentMarketValue": 133.9, "openPnl": -107.0},
                {"symbol": "ENB", "openQuantity": 10, "currentMarketValue": 503.0, "openPnl": 166.109},
            ],
        },
    }


def test_r84_launcher_cache_overlay_preserves_fail_closed_runtime(monkeypatch):
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_CACHE, "read", lambda: _snapshot())
    base = {
        "runtime_status": {"runtime_mode": "DISABLED", "effective_mode": "DISABLED", "execution_allowed": False, "live_trading_blocked": True, "broker_execution_armed": False, "advisory_only": True},
        "resolved_mode": "DISABLED",
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    overlaid = launcher.apply_launcher_questrade_read_only_cache(base)
    assert overlaid["selected_broker"] == "QUESTRADE"
    assert overlaid["canonical_mode"] == "LIVE_READ_ONLY"
    assert overlaid["runtime_status"]["runtime_mode"] == "DISABLED"
    assert overlaid["execution_allowed"] is False
    assert overlaid["live_trading_blocked"] is True
    assert overlaid["broker_execution_armed"] is False
    assert overlaid["advisory_only"] is True

    frontend = build_frontend_payload(overlaid)
    assert frontend["resolved_mode"] == "DISABLED"
    portfolio = frontend["sections"]["canonical_broker_portfolio"]
    assert portfolio["status"] == "AVAILABLE"
    assert portfolio["broker"] == "QUESTRADE"
    assert len(portfolio["exposures"]) == 3
    assert [row["instrument"] for row in portfolio["exposures"]] == ["TD", "T.TO", "ENB"]
    assert portfolio["metrics"]["session_pnl"]["availability"] == "UNAVAILABLE"
    assert portfolio["metrics"]["realized_pnl"]["availability"] == "UNAVAILABLE"
    assert portfolio["metrics"]["unrealized_pnl"]["availability"] == "UNAVAILABLE"


def test_r84_empty_cache_does_not_modify_launcher_payload(monkeypatch):
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_CACHE, "read", lambda: None)
    base = {"runtime_status": {"runtime_mode": "DISABLED"}, "selected_broker": "NONE"}
    assert launcher.apply_launcher_questrade_read_only_cache(base) == base
