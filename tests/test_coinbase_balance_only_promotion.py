from __future__ import annotations

from datetime import datetime, timezone, timedelta

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    apply_coinbase_balance_only_promotion,
    coinbase_balance_only_promotion_allowed,
    evaluate_canonical_broker_snapshot_freshness,
)
from dashboard.runtime.frontend_contract import build_frontend_payload


NOW = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)


def _snapshot(**overrides):
    payload = {
        "balances_loaded": True,
        "cash": 250.5,
        "equity": 260.25,
        "buying_power": 240.0,
        "available_balance": 240.0,
        "margin_available": 240.0,
        "margin_required": 0.0,
        "currency": "CAD",
        "timestamp": "2026-09-04T20:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _validation(snapshot=None, **overrides):
    snap = snapshot if snapshot is not None else _snapshot()
    payload = {
        "validation_status": "PASS",
        "balances_loaded": True,
        "broker_validation": {
            "validation_status": "PASS",
            "balances_loaded": True,
            "canonical_account_snapshot": snap,
        },
    }
    payload.update(overrides)
    return payload


def test_freshness_fails_closed_for_missing_naive_future_and_stale() -> None:
    assert evaluate_canonical_broker_snapshot_freshness({}, now=NOW)["reason"] == "missing_canonical_account_snapshot"
    assert evaluate_canonical_broker_snapshot_freshness({"cash": 1}, now=NOW)["reason"] == "missing_timestamp"
    assert evaluate_canonical_broker_snapshot_freshness({"timestamp": "not-a-time"}, now=NOW)["reason"] == "malformed_timestamp"
    assert evaluate_canonical_broker_snapshot_freshness({"timestamp": "2026-09-04T20:00:00"}, now=NOW)["reason"] == "naive_timestamp"
    assert evaluate_canonical_broker_snapshot_freshness({"timestamp": "2026-09-04T21:00:00+00:00"}, now=NOW)["reason"] == "future_timestamp"
    stale = evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": (NOW - timedelta(seconds=301)).isoformat()},
        now=NOW,
    )
    assert stale["ok"] is False
    assert stale["reason"] == "stale_timestamp"
    fresh = evaluate_canonical_broker_snapshot_freshness({"timestamp": NOW.isoformat()}, now=NOW)
    assert fresh["ok"] is True


def test_promotion_gates_require_coinbase_live_pass_and_fresh_snapshot() -> None:
    denied = coinbase_balance_only_promotion_allowed(
        selected_broker="OANDA",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert denied["allowed"] is False
    assert "selected_broker_not_coinbase" in denied["reasons"]

    paper = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="PAPER",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert paper["allowed"] is False

    failed = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE",
        coinbase_validation=_validation(
            validation_status="FAIL_CLOSED",
            broker_validation={"validation_status": "FAIL_CLOSED", "balances_loaded": True, "canonical_account_snapshot": _snapshot()},
        ),
        now=NOW,
    )
    assert failed["allowed"] is False

    allowed = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert allowed["allowed"] is True
    assert allowed["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_promoted_balances_do_not_imply_zero_pnl_or_positions() -> None:
    raw = apply_coinbase_balance_only_promotion(
        {
            "account_summary": {},
            "pnl_summary": {},
            "position_state": {},
            "open_positions": {},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        position_evidence=False,
        pnl_evidence=False,
        now=NOW,
    )
    assert raw["account_summary"]["cash_balance"] == 250.5
    assert raw["account_summary"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert raw["pnl_summary"]["realized_pnl"] == 0.0
    assert raw["pnl_summary"]["realized_pnl_availability"] == "UNAVAILABLE"
    assert raw["position_state"]["open_count"] == 0
    assert raw["position_state"]["open_count_availability"] == "UNAVAILABLE"

    frontend = build_frontend_payload(raw)
    pnl = frontend["sections"]["pnl_summary"]
    positions = frontend["sections"]["positions"]
    account = frontend["sections"]["account_summary"]
    assert account["cash_balance"] == 250.5
    assert account["cash_balance_availability"] == "AVAILABLE"
    assert isinstance(pnl["realized_pnl"], float)
    assert pnl["realized_pnl_availability"] == "UNAVAILABLE"
    assert isinstance(positions["total"], int)
    assert positions["total_availability"] == "UNAVAILABLE"
    assert pnl["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
