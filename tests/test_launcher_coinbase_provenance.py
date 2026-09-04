from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
from launcher.css_mobile_launcher import apply_launcher_coinbase_balance_only_promotion


NOW = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)
LAUNCHER_SOURCE = Path("launcher/css_mobile_launcher.py")


def _validation() -> dict:
    return {
        "validation_status": "PASS",
        "balances_loaded": True,
        "broker_validation": {
            "validation_status": "PASS",
            "balances_loaded": True,
            "canonical_account_snapshot": {
                "balances_loaded": True,
                "cash": 250.5,
                "equity": 260.25,
                "buying_power": 240.0,
                "available_balance": 240.0,
                "margin_available": 240.0,
                "margin_required": 0.0,
                "currency": "CAD",
                "timestamp": NOW.isoformat(),
            },
        },
    }


def test_launcher_source_does_not_use_presence_as_evidence() -> None:
    source = LAUNCHER_SOURCE.read_text(encoding="utf-8")
    assert "position_evidence=bool(positions)" not in source
    assert 'account.get(key) is not None for key in ("realized_pnl"' not in source
    assert "apply_launcher_coinbase_balance_only_promotion" in source


def test_launcher_stale_legacy_zero_pnl_is_unavailable_under_balance_only() -> None:
    raw = apply_launcher_coinbase_balance_only_promotion(
        {
            "account_summary": {
                "cash_balance": 12.0,
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "pnl_summary": {
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "account_equity": 0.0,
                "realized_pnl_availability": "AVAILABLE",
                "unrealized_pnl_availability": "AVAILABLE",
                "net_pnl_availability": "AVAILABLE",
                "account_equity_availability": "AVAILABLE",
                "availability_state": "AVAILABLE",
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "position_state": {"open_count": 0, "positions": [], "source": "UNAVAILABLE"},
            "open_positions": {"total": 0, "source": "UNAVAILABLE"},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    frontend = build_frontend_payload(raw)
    pnl = frontend["sections"]["pnl_summary"]
    account = frontend["sections"]["account_summary"]
    assert account["cash_balance"] == 250.5
    assert account["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert isinstance(pnl["realized_pnl"], float)
    assert pnl["realized_pnl"] == 0.0
    assert pnl["realized_pnl_availability"] == "UNAVAILABLE"
    assert pnl["unrealized_pnl_availability"] == "UNAVAILABLE"
    assert pnl["net_pnl_availability"] == "UNAVAILABLE"
    assert pnl["availability_state"] == "UNAVAILABLE"
    assert pnl["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_launcher_stale_nonempty_positions_are_unavailable_under_balance_only() -> None:
    raw = apply_launcher_coinbase_balance_only_promotion(
        {
            "account_summary": {},
            "pnl_summary": {
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "account_equity": 0.0,
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "position_state": {
                "open_count": 2,
                "open_count_availability": "AVAILABLE",
                "positions": [
                    {"symbol": "BTC-USD", "qty": 0.01},
                    {"symbol": "ETH-USD", "qty": 0.2},
                ],
                "source": "LAUNCHER_POSITION_ARTIFACT",
            },
            "open_positions": {
                "total": 2,
                "total_availability": "AVAILABLE",
                "source": "LAUNCHER_POSITION_ARTIFACT",
            },
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    frontend = build_frontend_payload(raw)
    positions = frontend["sections"]["positions"]
    assert isinstance(positions["total"], int)
    assert positions["total"] == 2
    assert positions["total_availability"] == "UNAVAILABLE"
    assert positions["open_count_availability"] == "UNAVAILABLE"
    assert raw["position_state"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert raw["open_positions"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_launcher_empty_positions_are_not_authoritative_zero() -> None:
    raw = apply_launcher_coinbase_balance_only_promotion(
        {
            "pnl_summary": {},
            "position_state": {
                "open_count": 0,
                "open_count_availability": "AVAILABLE",
                "positions": [],
                "source": "LAUNCHER_POSITION_ARTIFACT",
            },
            "open_positions": {"total": 0, "total_availability": "AVAILABLE"},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert raw["position_state"]["open_count"] == 0
    assert raw["position_state"]["open_count_availability"] == "UNAVAILABLE"
    assert isinstance(build_frontend_payload(raw)["sections"]["positions"]["total"], int)


def test_launcher_retains_explicit_compatible_fresh_evidence() -> None:
    raw = apply_launcher_coinbase_balance_only_promotion(
        {
            "pnl_summary": {
                "realized_pnl": 8.25,
                "unrealized_pnl": 1.75,
                "net_pnl": 10.0,
                "account_equity": 260.25,
                "realized_pnl_availability": "AVAILABLE",
                "unrealized_pnl_availability": "AVAILABLE",
                "net_pnl_availability": "AVAILABLE",
                "account_equity_availability": "AVAILABLE",
                "availability_state": "AVAILABLE",
                "source": "COINBASE_LIVE_READ_ONLY_PNL",
                "timestamp": NOW.isoformat(),
                "validation_status": "PASS",
            },
            "position_state": {
                "open_count": 1,
                "open_count_availability": "AVAILABLE",
                "positions": [{"symbol": "BTC-USD", "qty": 0.001}],
                "source": "COINBASE_LIVE_READ_ONLY_POSITIONS",
                "timestamp": NOW.isoformat(),
                "validation_status": "PASS",
            },
            "open_positions": {"total": 1, "total_availability": "AVAILABLE"},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    frontend = build_frontend_payload(raw)
    assert frontend["sections"]["pnl_summary"]["realized_pnl"] == 8.25
    assert frontend["sections"]["pnl_summary"]["realized_pnl_availability"] == "AVAILABLE"
    assert frontend["sections"]["pnl_summary"]["source"] == "COINBASE_LIVE_READ_ONLY_PNL"
    assert frontend["sections"]["positions"]["total"] == 1
    assert frontend["sections"]["positions"]["total_availability"] == "AVAILABLE"
