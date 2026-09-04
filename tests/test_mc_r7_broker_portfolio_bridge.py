from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy
from backend.runtime.canonical_broker_portfolio import (
    EXPOSURE_ACCOUNT_ASSET_BALANCE,
    EXPOSURE_HOLDING,
    EXPOSURE_POSITION,
    PROVENANCE_BROKER_REPORTED,
    PROVENANCE_DERIVED,
    apply_canonical_broker_portfolio_bridge,
    build_canonical_broker_portfolio,
)
from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    apply_coinbase_balance_only_promotion,
)
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.pages.executive_overview import render
from dashboard.runtime.frontend_contract import build_frontend_payload


NOW = datetime(2026, 9, 4, 23, 0, tzinfo=timezone.utc)


def _max_age() -> float:
    return float(gate_config(load_freshness_policy(), "broker_snapshot")["max_age_seconds"])


def _coinbase_validation(timestamp=None, **overrides):
    payload = {
        "validation_status": "PASS",
        "balances_loaded": True,
        "broker_validation": {
            "validation_status": "PASS",
            "balances_loaded": True,
            "canonical_account_snapshot": {
                "balances_loaded": True,
                "cash": 80.0,
                "equity": 90.0,
                "buying_power": 70.0,
                "available_balance": 70.0,
                "currency": "CAD",
                "timestamp": (timestamp or NOW).isoformat() if not isinstance(timestamp, str) else timestamp,
            },
            "account_asset_balances": [
                {"currency": "BTC", "available_balance": 0.0, "account_id": "acct-btc"},
                {"currency": "CAD", "available_balance": 80.0, "account_id": "acct-cad"},
            ],
        },
    }
    payload.update(overrides)
    return payload


def _promote_coinbase(validation=None, **kwargs):
    options = {
        "selected_broker": "COINBASE",
        "canonical_mode": "LIVE_READ_ONLY",
        "coinbase_validation": validation if validation is not None else _coinbase_validation(),
        "now": NOW,
    }
    options.update(kwargs)
    raw = apply_coinbase_balance_only_promotion(
        {"account_summary": {}, "pnl_summary": {}, "position_state": {}, "open_positions": {}},
        **options,
    )
    raw["selected_broker"] = options["selected_broker"]
    raw["canonical_mode"] = options["canonical_mode"]
    return apply_canonical_broker_portfolio_bridge(raw, now=NOW)


def _binance_payload(timestamp=None, **overrides):
    ts = timestamp if isinstance(timestamp, str) else (timestamp or NOW).isoformat()
    payload = {
        "selected_broker": "BINANCE",
        "canonical_mode": "LIVE_READ_ONLY",
        "binance_live_validation": {
            "validation_status": "PASS",
            "broker_validation": {
                "validation_status": "PASS",
                "validation_timestamp": ts,
                "account_asset_balances": [
                    {
                        "asset": "BTC",
                        "available_quantity": 0.0,
                        "available_quantity_availability": "AVAILABLE",
                        "held_quantity": 0.0,
                        "held_quantity_availability": "AVAILABLE",
                        "total_quantity": 0.0,
                        "total_quantity_availability": "AVAILABLE",
                        "total_quantity_provenance": "derived_available_plus_held",
                        "market_value": None,
                        "market_value_availability": "UNAVAILABLE",
                        "provenance": "BINANCE_LIVE_READ_ONLY",
                    },
                    {
                        "asset": "USDT",
                        "available_quantity": 10.0,
                        "available_quantity_availability": "AVAILABLE",
                        "held_quantity": 2.5,
                        "held_quantity_availability": "AVAILABLE",
                        "total_quantity": 12.5,
                        "total_quantity_availability": "AVAILABLE",
                        "total_quantity_provenance": "derived_available_plus_held",
                        "market_value": 12.5,
                        "market_value_availability": "UNAVAILABLE",
                        "provenance": "BINANCE_LIVE_READ_ONLY",
                    },
                ],
            },
        },
    }
    payload.update(overrides)
    return payload


def _oanda_payload(timestamp=None, **overrides):
    ts = timestamp if isinstance(timestamp, str) else (timestamp or NOW).isoformat()
    payload = {
        "selected_broker": "OANDA",
        "canonical_mode": "LIVE_READ_ONLY",
        "timestamp": ts,
        "account_summary": {
            "balance": 100.0,
            "NAV": 105.0,
            "buying_power": 90.0,
            "marginAvailable": 90.0,
            "marginUsed": 15.0,
            "currency": "USD",
            "timestamp": ts,
        },
        "oanda_positions": [
            {
                "instrument": "EUR_USD",
                "long": {"units": "10", "unrealizedPL": "2.5", "averagePrice": "1.08"},
                "short": {"units": "0"},
            }
        ],
    }
    payload.update(overrides)
    return payload


def _questrade_payload(timestamp=None, **overrides):
    ts = timestamp if isinstance(timestamp, str) else (timestamp or NOW).isoformat()
    payload = {
        "selected_broker": "QUESTRADE",
        "questrade_read_only": {
            "status": "HOLDINGS_READY",
            "timestamp": ts,
            "provider_timestamp": ts,
            "provenance": "QUESTRADE_POSITIONS",
            "balances": [
                {
                    "currency": "CAD",
                    "cash": 0.0,
                    "equity": 250.0,
                    "buying_power": 100.0,
                    "available_cash": 0.0,
                    "market_value": 250.0,
                    "provenance": "QUESTRADE_BALANCES",
                }
            ],
            "holdings": [
                {
                    "symbol": "SHOP",
                    "security_type": "EQUITY",
                    "quantity": 5,
                    "market_value": 200.0,
                    "unrealized_pnl": 12.0,
                    "provenance": "QUESTRADE_POSITIONS",
                }
            ],
            "option_positions": [
                {
                    "symbol": "SHOP21JAN26C100",
                    "security_type": "OPTION",
                    "quantity": 1,
                    "expiry": "2026-01-21",
                    "unrealized_pnl": -3.0,
                    "market_value": 50.0,
                    "side": "LONG",
                    "provenance": "QUESTRADE_POSITIONS",
                }
            ],
        },
    }
    payload.update(overrides)
    return payload


def _mc(raw):
    frontend = build_frontend_payload(raw)
    state = build_mission_control_state({"frontend_payload": frontend}, allow_mock=False)
    return frontend, state


def test_1_coinbase_spot_asset_balance_promotion() -> None:
    raw = _promote_coinbase()
    portfolio = raw["canonical_broker_portfolio"]
    assert portfolio["status"] == "AVAILABLE"
    assert portfolio["broker"] == "COINBASE"
    kinds = {row["exposure_kind"] for row in portfolio["exposures"]}
    assert kinds == {EXPOSURE_ACCOUNT_ASSET_BALANCE}
    assets = {row["asset"] for row in portfolio["exposures"]}
    assert assets == {"BTC", "CAD"}
    btc = next(row for row in portfolio["exposures"] if row["asset"] == "BTC")
    assert btc["available_quantity"] == 0.0
    assert btc["not_a_position"] is True
    frontend, state = _mc(raw)
    assert state["portfolio"]["spot_asset_balances"]["status"] == "AVAILABLE"
    assert frontend["sections"]["canonical_broker_portfolio"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_2_coinbase_balances_are_not_relabeled_positions() -> None:
    raw = _promote_coinbase()
    _, state = _mc(raw)
    portfolio = state["portfolio"]
    assert portfolio["open_positions"] == "UNAVAILABLE"
    assert portfolio["session_pnl"] == "UNAVAILABLE"
    assert portfolio["maturity_expiry"]["status"] == "UNAVAILABLE"
    page = render(state)
    assert "data-not-positions" in page
    assert "Account Asset Balances" in page
    assert all(row.get("exposure_kind") != EXPOSURE_POSITION for row in raw["canonical_broker_portfolio"]["exposures"])


def test_3_binance_free_locked_balance_promotion() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    usdt = next(row for row in raw["canonical_broker_portfolio"]["exposures"] if row["asset"] == "USDT")
    assert usdt["available_quantity"] == 10.0
    assert usdt["held_quantity"] == 2.5
    assert usdt["available_quantity_field"] == "free"
    assert usdt["held_quantity_field"] == "locked"
    _, state = _mc(raw)
    assert state["portfolio"]["spot_asset_balances"]["status"] == "AVAILABLE"
    assert state["portfolio"]["spot_asset_balances"]["source"] == "BINANCE_LIVE_READ_ONLY"


def test_4_binance_derived_total_is_explicitly_derived() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    usdt = next(row for row in raw["canonical_broker_portfolio"]["exposures"] if row["asset"] == "USDT")
    assert usdt["total_quantity"] == 12.5
    assert usdt["total_quantity_provenance"] == "derived_available_plus_held"
    assert usdt["total_quantity_availability"] == "AVAILABLE"
    assert usdt["provenance"] == PROVENANCE_BROKER_REPORTED
    assert usdt["market_value"] is None


def test_5_binance_balances_are_not_relabeled_positions() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    _, state = _mc(raw)
    assert all(row["exposure_kind"] == EXPOSURE_ACCOUNT_ASSET_BALANCE for row in raw["canonical_broker_portfolio"]["exposures"])
    assert state["portfolio"]["open_positions"] == "UNAVAILABLE"
    assert state["portfolio"]["session_pnl"] == "UNAVAILABLE"
    assert state["portfolio"]["maturity_expiry"]["status"] == "UNAVAILABLE"
    assert "Open Positions" in render(state)


def test_6_oanda_authoritative_fx_position_promotion() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    portfolio = raw["canonical_broker_portfolio"]
    assert portfolio["status"] == "AVAILABLE"
    positions = [row for row in portfolio["exposures"] if row["exposure_kind"] == EXPOSURE_POSITION]
    assert len(positions) == 1
    assert positions[0]["instrument"] == "EUR_USD"
    assert positions[0]["units"] == 10.0
    assert positions[0]["side"] == "BUY"
    assert positions[0]["asset_class"] == "FX"
    _, state = _mc(raw)
    assert state["portfolio"]["open_positions"] == 1
    assert state["portfolio"]["open_positions_availability"] == "AVAILABLE"
    assert state["portfolio"]["cash"] == 100.0
    assert state["portfolio"]["portfolio_value"] == 105.0


def test_7_oanda_unrealized_pnl_preserved_when_broker_reported() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    row = raw["canonical_broker_portfolio"]["exposures"][0]
    assert row["unrealized_pnl"] == 2.5
    assert row["unrealized_pnl_availability"] == "AVAILABLE"
    assert row["unrealized_pnl_provenance"] == PROVENANCE_BROKER_REPORTED


def test_8_oanda_unsupported_realized_and_session_pnl_remain_unavailable() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    _, state = _mc(raw)
    metrics = raw["canonical_broker_portfolio"]["metrics"]
    assert metrics["session_pnl"]["availability"] == "UNAVAILABLE"
    assert metrics["realized_pnl"]["availability"] == "UNAVAILABLE"
    assert raw["canonical_broker_portfolio"]["session_pnl_by_instrument"]["status"] == "UNAVAILABLE"
    assert state["portfolio"]["session_pnl"] == "UNAVAILABLE"
    assert state["portfolio"]["realized_pnl"] == "UNAVAILABLE"
    assert state["portfolio"]["session_pnl_by_instrument"] == "UNAVAILABLE"
    row = raw["canonical_broker_portfolio"]["exposures"][0]
    assert row["realized_pnl_availability"] == "UNAVAILABLE"
    assert row["session_pnl_availability"] == "UNAVAILABLE"


def test_9_questrade_holdings_promotion() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)
    holdings = [row for row in raw["canonical_broker_portfolio"]["exposures"] if row["exposure_kind"] == EXPOSURE_HOLDING]
    assert len(holdings) == 1
    assert holdings[0]["instrument"] == "SHOP"
    assert holdings[0]["quantity"] == 5
    assert holdings[0]["market_value"] == 200.0
    assert holdings[0]["unrealized_pnl"] == 12.0
    _, state = _mc(raw)
    assert state["portfolio"]["cash"] == 0.0
    assert state["portfolio"]["portfolio_value"] == 250.0


def test_10_questrade_true_position_promotion() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)
    positions = [row for row in raw["canonical_broker_portfolio"]["exposures"] if row["exposure_kind"] == EXPOSURE_POSITION]
    assert len(positions) == 1
    assert positions[0]["security_type"] == "OPTION"
    assert positions[0]["instrument"] == "SHOP21JAN26C100"
    _, state = _mc(raw)
    assert state["portfolio"]["open_positions"] == 1


def test_11_questrade_option_expiry_preservation() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)
    option = next(row for row in raw["canonical_broker_portfolio"]["exposures"] if row["exposure_kind"] == EXPOSURE_POSITION)
    assert option["maturity"] == "2026-01-21"
    assert option["maturity_availability"] == "AVAILABLE"
    _, state = _mc(raw)
    assert state["portfolio"]["maturity_expiry"]["status"] == "AVAILABLE"
    assert state["portfolio"]["next_maturity"] == "2026-01-21"
    assert "2026-01-21" in render(state)


def test_12_non_expiring_instruments_do_not_receive_fabricated_maturity() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)
    holding = next(row for row in raw["canonical_broker_portfolio"]["exposures"] if row["exposure_kind"] == EXPOSURE_HOLDING)
    assert holding["maturity"] is None
    assert holding["maturity_availability"] == "UNAVAILABLE"
    coinbase = _promote_coinbase()
    assert all(row["maturity_availability"] == "UNAVAILABLE" for row in coinbase["canonical_broker_portfolio"]["exposures"])
    oanda = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    assert oanda["canonical_broker_portfolio"]["exposures"][0]["maturity_availability"] == "UNAVAILABLE"
    binance = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    assert all(row["maturity_availability"] == "UNAVAILABLE" for row in binance["canonical_broker_portfolio"]["exposures"])


def test_13_provider_disabled_or_unavailable_remains_unavailable() -> None:
    raw = apply_canonical_broker_portfolio_bridge(
        {
            "selected_broker": "QUESTRADE",
            "questrade_read_only": {
                "status": "PROVIDER_UNAVAILABLE",
                "failure_reason": "QUESTRADE_PROVIDER_DISABLED",
                "fabricated": False,
                "timestamp": NOW.isoformat(),
            },
        },
        now=NOW,
    )
    assert raw["canonical_broker_portfolio"]["status"] == "UNAVAILABLE"
    assert raw["canonical_broker_portfolio"]["metrics"]["cash"]["value"] is None
    _, state = _mc(raw)
    assert state["portfolio"]["cash"] == "UNAVAILABLE"
    assert state["portfolio"]["open_positions"] == "UNAVAILABLE"


def test_14_broker_reported_zero_values_survive_promotion() -> None:
    coinbase = _promote_coinbase()
    btc = next(row for row in coinbase["canonical_broker_portfolio"]["exposures"] if row["asset"] == "BTC")
    assert btc["available_quantity"] == 0.0
    binance = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    btc_b = next(row for row in binance["canonical_broker_portfolio"]["exposures"] if row["asset"] == "BTC")
    assert btc_b["available_quantity"] == 0.0
    assert btc_b["held_quantity"] == 0.0
    qt = apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)
    assert qt["canonical_broker_portfolio"]["metrics"]["cash"]["value"] == 0.0
    assert qt["canonical_broker_portfolio"]["metrics"]["cash"]["availability"] == "AVAILABLE"


def test_15_missing_values_are_not_converted_to_zero() -> None:
    raw = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    metrics = raw["canonical_broker_portfolio"]["metrics"]
    assert metrics["session_pnl"]["value"] is None
    assert metrics["realized_pnl"]["value"] is None
    assert metrics["next_maturity"]["value"] is None
    assert metrics["session_pnl"]["availability"] == "UNAVAILABLE"
    _, state = _mc(raw)
    assert state["portfolio"]["session_pnl"] == "UNAVAILABLE"
    assert state["portfolio"]["realized_pnl"] == "UNAVAILABLE"
    assert state["portfolio"]["next_maturity"] == "UNAVAILABLE"


def test_16_provenance_survives_to_mission_control() -> None:
    raw = _promote_coinbase()
    _, state = _mc(raw)
    canonical = state["portfolio"]["canonical_broker_portfolio"]
    assert canonical["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert all(row["provenance"] == PROVENANCE_BROKER_REPORTED for row in canonical["exposures"])
    oanda = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    _, oanda_state = _mc(oanda)
    assert oanda_state["portfolio"]["canonical_broker_portfolio"]["metrics"]["cash"]["provenance"] == PROVENANCE_BROKER_REPORTED


def test_17_derived_values_are_visibly_marked_derived() -> None:
    binance = apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW)
    usdt = next(row for row in binance["canonical_broker_portfolio"]["exposures"] if row["asset"] == "USDT")
    assert usdt["total_quantity_provenance"] == "derived_available_plus_held"
    oanda = apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW)
    assert oanda["canonical_broker_portfolio"]["metrics"]["open_positions"]["provenance"] == PROVENANCE_DERIVED
    page = render(_mc(binance)[1])
    assert "derived_available_plus_held" in page


def test_18_and_19_freshness_uses_canonical_broker_snapshot_and_stale_is_not_current() -> None:
    policy = {"gates": {"broker_snapshot": {"max_age_seconds": 90}}}
    fresh = build_canonical_broker_portfolio(
        _binance_payload(timestamp=(NOW - timedelta(seconds=90)).isoformat()),
        now=NOW,
        policy=policy,
    )
    stale = build_canonical_broker_portfolio(
        _binance_payload(timestamp=(NOW - timedelta(seconds=91)).isoformat()),
        now=NOW,
        policy=policy,
    )
    assert fresh["status"] == "AVAILABLE"
    assert fresh["freshness"]["max_age_seconds"] == 90.0
    assert stale["status"] == "UNAVAILABLE"
    assert "stale" in stale["reason"]
    max_age = _max_age()
    stale_oanda = apply_canonical_broker_portfolio_bridge(
        _oanda_payload(timestamp=(NOW - timedelta(seconds=max_age + 5)).isoformat()),
        now=NOW,
    )
    assert stale_oanda["canonical_broker_portfolio"]["status"] == "UNAVAILABLE"
    _, state = _mc(stale_oanda)
    assert state["portfolio"]["cash"] == "UNAVAILABLE"
    assert state["portfolio"]["open_positions"] == "UNAVAILABLE"


def test_20_execution_remains_fail_closed() -> None:
    for raw in (_promote_coinbase(), apply_canonical_broker_portfolio_bridge(_binance_payload(), now=NOW), apply_canonical_broker_portfolio_bridge(_oanda_payload(), now=NOW), apply_canonical_broker_portfolio_bridge(_questrade_payload(), now=NOW)):
        portfolio = raw["canonical_broker_portfolio"]
        assert portfolio["execution_allowed"] is False
        assert portfolio["live_trading_blocked"] is True
        assert portfolio["broker_execution_armed"] is False
        assert portfolio["advisory_only"] is True
        _, state = _mc(raw)
        assert state["safety"]["execution_allowed"] is False
        assert state["safety"]["live_trading_blocked"] is True
        assert state["safety"]["broker_execution_armed"] is False
        page = render(state)
        assert "Execution allowed: false" in page or "execution allowed: false" in page.lower()


def test_21_no_broker_write_capability_is_introduced() -> None:
    source = Path("backend/runtime/canonical_broker_portfolio.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.name.lower() for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    forbidden = ("place", "submit", "cancel", "modify", "close_order", "withdraw", "transfer")
    assert not any(any(token in name for token in forbidden) for name in names)
    assert "requests." not in source
    assert "socket" not in source
