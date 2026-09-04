from __future__ import annotations

from dashboard.runtime.frontend_contract import build_frontend_payload


def test_missing_pnl_and_positions_keep_numeric_schema_and_mark_unavailable() -> None:
    payload = build_frontend_payload({})
    pnl = payload["sections"]["pnl_summary"]
    positions = payload["sections"]["positions"]

    assert isinstance(pnl["realized_pnl"], float)
    assert isinstance(pnl["unrealized_pnl"], float)
    assert isinstance(pnl["net_pnl"], float)
    assert isinstance(pnl["account_equity"], float)
    assert pnl["realized_pnl"] == 0.0
    assert pnl["unrealized_pnl"] == 0.0
    assert pnl["net_pnl"] == 0.0
    assert pnl["account_equity"] == 0.0
    assert pnl["realized_pnl_availability"] == "UNAVAILABLE"
    assert pnl["unrealized_pnl_availability"] == "UNAVAILABLE"
    assert pnl["net_pnl_availability"] == "UNAVAILABLE"
    assert pnl["account_equity_availability"] == "UNAVAILABLE"
    assert pnl["availability_state"] == "UNAVAILABLE"
    assert isinstance(positions["total"], int)
    assert positions["total"] == 0
    assert positions["total_availability"] == "UNAVAILABLE"
    assert positions["open_count_availability"] == "UNAVAILABLE"


def test_unavailable_strings_do_not_enter_numeric_fields() -> None:
    payload = build_frontend_payload(
        {
            "pnl_summary": {
                "realized_pnl": "UNAVAILABLE",
                "unrealized_pnl": "DATA UNAVAILABLE",
                "net_pnl": "UNAVAILABLE",
                "account_equity": "UNAVAILABLE",
            },
            "position_state": {"open_count": "UNAVAILABLE"},
            "open_positions": {"total": "UNAVAILABLE"},
        }
    )
    pnl = payload["sections"]["pnl_summary"]
    positions = payload["sections"]["positions"]

    assert pnl["realized_pnl"] == 0.0
    assert pnl["unrealized_pnl"] == 0.0
    assert pnl["net_pnl"] == 0.0
    assert pnl["account_equity"] == 0.0
    assert pnl["realized_pnl_availability"] == "UNAVAILABLE"
    assert positions["total"] == 0
    assert positions["open_count"] == 0
    assert positions["total_availability"] == "UNAVAILABLE"


def test_explicit_availability_is_preserved_for_real_zeros() -> None:
    payload = build_frontend_payload(
        {
            "pnl_summary": {
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "account_equity": 100.0,
                "realized_pnl_availability": "AVAILABLE",
                "unrealized_pnl_availability": "AVAILABLE",
                "net_pnl_availability": "AVAILABLE",
                "account_equity_availability": "AVAILABLE",
                "source": "INDEPENDENT_PNL",
            },
            "position_state": {"open_count": 0, "open_count_availability": "AVAILABLE"},
            "open_positions": {"total": 0, "total_availability": "AVAILABLE"},
        }
    )
    pnl = payload["sections"]["pnl_summary"]
    positions = payload["sections"]["positions"]

    assert pnl["realized_pnl"] == 0.0
    assert pnl["realized_pnl_availability"] == "AVAILABLE"
    assert pnl["account_equity"] == 100.0
    assert pnl["source"] == "INDEPENDENT_PNL"
    assert positions["total"] == 0
    assert positions["total_availability"] == "AVAILABLE"


def test_evidenced_pnl_and_positions_remain_numeric_and_available() -> None:
    payload = build_frontend_payload(
        {
            "pnl_summary": {
                "realized_pnl": 12.5,
                "unrealized_pnl": -1.25,
                "net_pnl": 11.25,
                "account_equity": 3000.0,
            },
            "position_state": {
                "open_count": 1,
                "positions": [{"symbol": "BTC-USD", "qty": 0.001}],
            },
            "open_positions": {"total": 1},
        }
    )
    pnl = payload["sections"]["pnl_summary"]
    positions = payload["sections"]["positions"]

    assert pnl["realized_pnl"] == 12.5
    assert pnl["realized_pnl_availability"] == "AVAILABLE"
    assert pnl["net_pnl_availability"] == "AVAILABLE"
    assert positions["total"] == 1
    assert positions["total_availability"] == "AVAILABLE"
    assert positions["items"][0]["symbol"] == "BTC-USD"
