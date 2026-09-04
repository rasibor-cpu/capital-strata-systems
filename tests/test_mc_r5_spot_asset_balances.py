from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy
from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    apply_coinbase_balance_only_promotion,
)
from backend.runtime.coinbase_spot_asset_balances import (
    SECTION_LABEL,
    build_spot_asset_balances,
)
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.pages.executive_overview import render
from dashboard.runtime.frontend_contract import build_frontend_payload


NOW = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)
FORBIDDEN_BALANCE_LABELS = (
    "Open Positions",
    "Trades",
    "Futures Positions",
    "Options Positions",
    "Leveraged Positions",
)


def _canonical_max_age() -> float:
    policy = load_freshness_policy()
    cfg = gate_config(policy, "broker_snapshot")
    return float(cfg["max_age_seconds"])


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
        "account_id": "acct-cad-1",
        "timestamp": NOW.isoformat(),
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


def _promote(validation=None, **kwargs):
    options = {
        "selected_broker": "COINBASE",
        "canonical_mode": "LIVE_READ_ONLY",
        "coinbase_validation": validation if validation is not None else _validation(),
        "position_evidence": False,
        "pnl_evidence": False,
        "now": NOW,
    }
    options.update(kwargs)
    return apply_coinbase_balance_only_promotion(
        {"account_summary": {}, "pnl_summary": {}, "position_state": {}, "open_positions": {}},
        **options,
    )


def _mission_state(raw):
    frontend = build_frontend_payload(raw)
    return frontend, build_mission_control_state({"frontend_payload": frontend}, allow_mock=False)


def test_a_fresh_pass_coinbase_live_read_only_makes_asset_balances_available() -> None:
    accounts = [
        {
            "account_id": "acct-btc",
            "currency": "BTC",
            "available_balance": 0.15,
            "held_balance": 0.01,
            "total_balance": 0.16,
        },
        {
            "account_id": "acct-cad-1",
            "currency": "CAD",
            "available_balance": 240.0,
            "held_balance": 10.0,
            "total_balance": 250.0,
        },
    ]
    validation = _validation()
    validation["account_asset_balances"] = accounts
    validation["broker_validation"]["account_asset_balances"] = accounts

    raw = _promote(validation)
    frontend, state = _mission_state(raw)
    section = frontend["sections"]["spot_asset_balances"]
    portfolio = state["portfolio"]
    balances = portfolio["spot_asset_balances"]

    assert section["status"] == "AVAILABLE"
    assert section["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert section["section_label"] == SECTION_LABEL
    assert section["section_label"] == "Account Asset Balances"
    assert section["market_value_availability"] == "UNAVAILABLE"
    assert {row["asset"] for row in section["rows"]} == {"BTC", "CAD"}
    btc = next(row for row in section["rows"] if row["asset"] == "BTC")
    assert btc["available_quantity"] == 0.15
    assert btc["held_quantity"] == 0.01
    assert btc["total_quantity"] == 0.16
    assert btc["total_quantity_provenance"] == "derived_available_plus_held"
    assert btc["provenance"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert btc["market_value"] is None
    assert btc["market_value_availability"] == "UNAVAILABLE"
    assert btc["account_id"] == "acct-btc"
    assert balances["status"] == "AVAILABLE"
    assert balances["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert {row["asset"] for row in balances["rows"]} == {"BTC", "CAD"}


def test_a_snapshot_only_artifact_preserves_available_quantity_without_invented_hold() -> None:
    raw = _promote()
    section = raw["spot_asset_balances"]
    assert section["status"] == "AVAILABLE"
    assert len(section["rows"]) == 1
    row = section["rows"][0]
    assert row["asset"] == "CAD"
    assert row["available_quantity"] == 240.0
    assert row["held_quantity"] is None
    assert row["held_quantity_availability"] == "UNAVAILABLE"
    assert row["total_quantity"] is None
    assert row["total_quantity_availability"] == "UNAVAILABLE"
    assert row["market_value"] is None
    assert row["account_id"] == "acct-cad-1"
    assert row["provenance"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_b_stale_timestamp_makes_asset_balances_unavailable() -> None:
    max_age = _canonical_max_age()
    raw = _promote(
        _validation(
            _snapshot(timestamp=(NOW - timedelta(seconds=max_age + 1)).isoformat())
        )
    )
    section = raw["spot_asset_balances"]
    assert section["status"] == "UNAVAILABLE"
    assert section["rows"] == []
    assert any("stale" in str(reason) for reason in section.get("reasons", [])) or "stale" in section["reason"]


def test_c_future_timestamp_makes_asset_balances_unavailable() -> None:
    raw = _promote(_validation(_snapshot(timestamp=(NOW + timedelta(hours=1)).isoformat())))
    section = raw["spot_asset_balances"]
    assert section["status"] == "UNAVAILABLE"
    assert section["rows"] == []
    assert "future" in section["reason"] or any("future" in str(reason) for reason in section.get("reasons", []))


def test_d_malformed_and_missing_timestamp_make_asset_balances_unavailable() -> None:
    missing = _promote(_validation(_snapshot(timestamp="")))
    malformed = _promote(_validation(_snapshot(timestamp="not-a-time")))
    naive = _promote(_validation(_snapshot(timestamp="2026-09-04T20:00:00")))
    for section in (
        missing["spot_asset_balances"],
        malformed["spot_asset_balances"],
        naive["spot_asset_balances"],
    ):
        assert section["status"] == "UNAVAILABLE"
        assert section["rows"] == []


def test_e_failed_validation_makes_asset_balances_unavailable() -> None:
    raw = _promote(
        _validation(
            validation_status="FAIL_CLOSED",
            broker_validation={
                "validation_status": "FAIL_CLOSED",
                "balances_loaded": True,
                "canonical_account_snapshot": _snapshot(),
            },
        )
    )
    section = raw["spot_asset_balances"]
    assert section["status"] == "UNAVAILABLE"
    assert section["rows"] == []
    assert "validation_status_not_pass" in section.get("reasons", []) or "validation" in section["reason"]


def test_f_wrong_broker_makes_asset_balances_unavailable() -> None:
    raw = _promote(selected_broker="OANDA")
    section = raw["spot_asset_balances"]
    assert section["status"] == "UNAVAILABLE"
    assert section["rows"] == []
    assert "selected_broker_not_coinbase" in section.get("reasons", [])


def test_g_wrong_mode_makes_asset_balances_unavailable() -> None:
    for mode in ("PAPER", "LIVE", "ADVISORY"):
        raw = _promote(canonical_mode=mode)
        section = raw["spot_asset_balances"]
        assert section["status"] == "UNAVAILABLE", mode
        assert section["rows"] == []
        assert "canonical_mode_not_live_read_only" in section.get("reasons", [])


def test_h_balance_rows_do_not_make_positions_pnl_or_maturity_available() -> None:
    raw = _promote()
    frontend, state = _mission_state(raw)
    portfolio = state["portfolio"]
    assert raw["spot_asset_balances"]["status"] == "AVAILABLE"
    assert frontend["sections"]["positions"]["total_availability"] == "UNAVAILABLE"
    assert frontend["sections"]["pnl_summary"]["availability_state"] == "UNAVAILABLE"
    assert frontend["sections"]["pnl_summary"]["realized_pnl_availability"] == "UNAVAILABLE"
    assert portfolio["open_positions"] == "UNAVAILABLE"
    assert portfolio["open_positions_availability"] == "UNAVAILABLE"
    assert portfolio["session_pnl"] == "UNAVAILABLE"
    assert portfolio["session_pnl_by_instrument"] == "UNAVAILABLE"
    assert portfolio["maturity_expiry"]["status"] == "UNAVAILABLE"


def test_i_balances_are_not_relabeled_as_positions() -> None:
    raw = _promote()
    frontend, state = _mission_state(raw)
    section = frontend["sections"]["spot_asset_balances"]
    assert section["section_label"] == "Account Asset Balances"
    assert section["section_kind"] == "spot_asset_balances"
    for forbidden in FORBIDDEN_BALANCE_LABELS:
        assert section["section_label"] != forbidden
    page = html.unescape(render(state))
    assert "Current Holdings / Exposure" in page
    assert "Account Asset Balances" in page
    assert "data-not-positions" in page
    assert "Account asset quantities are not open positions" in page
    assert "Current Holdings / Positions" not in page
    start = page.index('id="current-holdings-exposure"')
    snippet = page[start:]
    assert snippet.index("Account Asset Balances") < snippet.index("Open Positions")
    for forbidden in ("Trades", "Futures Positions", "Options Positions", "Leveraged Positions"):
        assert forbidden not in snippet[: snippet.index("Open Positions")]


def test_j_market_value_remains_unavailable_without_price_evidence() -> None:
    validation = _validation()
    validation["broker_validation"]["account_asset_balances"] = [
        {
            "currency": "BTC",
            "available_balance": 1.0,
            "market_value": 65000.0,
            "fiat_equivalent": 65000.0,
        }
    ]
    raw = _promote(validation)
    section = raw["spot_asset_balances"]
    assert section["status"] == "AVAILABLE"
    assert section["market_value_availability"] == "UNAVAILABLE"
    assert section["rows"][0]["market_value"] is None
    assert section["rows"][0]["market_value_availability"] == "UNAVAILABLE"
    frontend = build_frontend_payload(raw)
    assert frontend["sections"]["spot_asset_balances"]["rows"][0]["market_value"] is None


def test_fallback_hold_zero_is_not_treated_as_independent() -> None:
    validation = _validation()
    validation["broker_validation"]["accounts"] = [
        {
            "account_id": "FALLBACK-COINBASE",
            "currency": "USD",
            "available_balance": 12.0,
            "held_balance": 0.0,
            "total_balance": 12.0,
        }
    ]
    section = build_spot_asset_balances(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=validation,
        now=NOW,
    )
    assert section["status"] == "AVAILABLE"
    row = section["rows"][0]
    assert row["available_quantity"] == 12.0
    assert row["held_quantity"] is None
    assert row["held_quantity_availability"] == "UNAVAILABLE"
    assert row["total_quantity"] is None
    assert "account_id" not in row


def test_affirmative_zero_available_is_available() -> None:
    validation = _validation()
    validation["broker_validation"]["account_asset_balances"] = [
        {"currency": "ETH", "available_balance": 0.0}
    ]
    section = build_spot_asset_balances(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=validation,
        now=NOW,
    )
    assert section["status"] == "AVAILABLE"
    assert section["rows"][0]["available_quantity"] == 0.0
    assert section["rows"][0]["available_quantity_availability"] == "AVAILABLE"


def test_freshness_uses_canonical_broker_snapshot_policy() -> None:
    policy = {"gates": {"broker_snapshot": {"max_age_seconds": 90}}}
    fresh = build_spot_asset_balances(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(_snapshot(timestamp=(NOW - timedelta(seconds=90)).isoformat())),
        now=NOW,
        policy=policy,
    )
    stale = build_spot_asset_balances(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(_snapshot(timestamp=(NOW - timedelta(seconds=91)).isoformat())),
        now=NOW,
        policy=policy,
    )
    assert fresh["status"] == "AVAILABLE"
    assert stale["status"] == "UNAVAILABLE"
    assert fresh["freshness"]["max_age_seconds"] == 90.0
    assert stale["freshness"]["max_age_seconds"] == 90.0
