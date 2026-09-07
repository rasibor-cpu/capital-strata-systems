from datetime import datetime, timezone

from tests.test_mc_r7_broker_portfolio_bridge import (
    _mc,
    _questrade_payload,
)


def test_r810_three_holdings_zero_true_positions():
    payload = _questrade_payload()

    now = datetime.now(timezone.utc).isoformat()
    payload["questrade_read_only"]["timestamp"] = now
    payload["questrade_read_only"]["provider_timestamp"] = now

    qt = payload["questrade_read_only"]

    qt["holdings"] = [
        {
            "symbol": "TD",
            "security_type": "EQUITY",
            "quantity": 5,
            "market_value": 608.15,
            "unrealized_pnl": 311.8525,
            "provenance": "QUESTRADE_POSITIONS",
        },
        {
            "symbol": "T.TO",
            "security_type": "EQUITY",
            "quantity": 10,
            "market_value": 133.90,
            "unrealized_pnl": -107.0,
            "provenance": "QUESTRADE_POSITIONS",
        },
        {
            "symbol": "ENB",
            "security_type": "EQUITY",
            "quantity": 10,
            "market_value": 500.90,
            "unrealized_pnl": 164.009,
            "provenance": "QUESTRADE_POSITIONS",
        },
    ]

    qt["option_positions"] = []

    frontend, state = _mc(payload)
    portfolio = state["portfolio"]

    canonical = portfolio["canonical_broker_portfolio"]

    assert canonical["status"] == "AVAILABLE"

    # R7 invariant: open_positions means true POSITION exposure,
    # not ordinary equity holdings.
    assert portfolio["open_positions"] == 0

    # R8.10 presentation semantics.
    assert portfolio["holdings_count"] == 3
    assert portfolio["broker_exposure_count"] == 3

    assert portfolio["holdings_count_availability"] == "AVAILABLE"
    assert portfolio["broker_exposure_count_availability"] == "AVAILABLE"

    # Three ordinary equity holdings remain holdings.
    assert len(portfolio["holdings"]) == 3

    # There are no true broker POSITION rows.
    assert portfolio["positions"] == []

    # Account-asset balances must not be counted as exposures.
    assert all(
        row.get("exposure_kind") != "ACCOUNT_ASSET_BALANCE"
        for row in canonical["exposures"]
    )

    holdings = [
        row
        for row in canonical["exposures"]
        if row.get("exposure_kind") == "HOLDING"
    ]
    positions = [
        row
        for row in canonical["exposures"]
        if row.get("exposure_kind") == "POSITION"
    ]

    assert len(holdings) == 3
    assert len(positions) == 0

    assert {row["instrument"] for row in holdings} == {
        "TD",
        "T.TO",
        "ENB",
    }

    # Safety invariant: reconciliation remains advisory/read-only.
    # These controls are owned by the top-level Mission Control state
    # / execution committee, not by the portfolio object.
    assert state["advisory_only"] is True

    execution_committee = state["execution_committee"]

    assert execution_committee["execution_allowed"] is False
    assert execution_committee["live_trading_blocked"] is True
    assert execution_committee["broker_execution_armed"] is False
    assert execution_committee["read_only"] is True
    assert execution_committee["advisory_only"] is True
