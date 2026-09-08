from datetime import datetime, timezone

from backend.brokers.questrade.contracts import map_positions
from backend.runtime.canonical_broker_portfolio import (
    build_canonical_broker_portfolio,
)


NOW = datetime(2026, 9, 8, 15, 55, tzinfo=timezone.utc)
TS = NOW.isoformat()


def test_r811_closed_equity_rows_with_zero_open_quantity_are_not_holdings():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "TD",
                    "securityType": "Stock",
                    "openQuantity": 0,
                    "closedQuantity": 5,
                    "currentMarketValue": None,
                    "openPnl": None,
                    "closedPnl": 309.2025,
                },
                {
                    "symbol": "T.TO",
                    "securityType": "Stock",
                    "openQuantity": 0,
                    "closedQuantity": 10,
                    "closedPnl": -108.2,
                },
                {
                    "symbol": "ENB",
                    "securityType": "Stock",
                    "openQuantity": 0,
                    "closedQuantity": 10,
                    "closedPnl": 165.859,
                },
            ]
        },
        generated_at=TS,
    )

    assert mapped["holdings"] == []
    assert mapped["option_positions"] == []
    assert mapped["position_count"] == 0


def test_r811_string_zero_quantity_is_also_filtered():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "TD",
                    "securityType": "Stock",
                    "openQuantity": "0",
                }
            ]
        },
        generated_at=TS,
    )

    assert mapped["holdings"] == []
    assert mapped["position_count"] == 0


def test_r811_nonzero_long_and_short_equities_are_preserved():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "SHOP",
                    "securityType": "Stock",
                    "openQuantity": 5,
                    "currentMarketValue": 200.0,
                },
                {
                    "symbol": "ABC",
                    "securityType": "Stock",
                    "openQuantity": -3,
                    "currentMarketValue": -75.0,
                },
            ]
        },
        generated_at=TS,
    )

    assert [row["quantity"] for row in mapped["holdings"]] == [
        5,
        -3,
    ]

    assert [row["symbol"] for row in mapped["holdings"]] == [
        "SHOP",
        "ABC",
    ]


def test_r811_zero_quantity_option_is_not_current_position():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "SPY260918C00600000",
                    "securityType": "Option",
                    "currentQuantity": 0,
                    "openQuantity": 0,
                    "closedQuantity": 1,
                    "expiryDate": "2026-09-18",
                    "strikePrice": 600.0,
                    "optionType": "Call",
                }
            ]
        },
        generated_at=TS,
    )

    assert mapped["option_positions"] == []
    assert mapped["position_count"] == 0


def test_r811_nonzero_long_and_short_options_remain_intact():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "SPY260918C00600000",
                    "securityType": "Option",
                    "currentQuantity": 2,
                    "expiryDate": "2026-09-18",
                    "strikePrice": 600.0,
                    "optionType": "Call",
                },
                {
                    "symbol": "SPY260918P00500000",
                    "securityType": "Option",
                    "currentQuantity": -1,
                    "expiryDate": "2026-09-18",
                    "strikePrice": 500.0,
                    "optionType": "Put",
                },
            ]
        },
        generated_at=TS,
    )

    assert len(mapped["option_positions"]) == 2

    long_row, short_row = mapped["option_positions"]

    assert long_row["quantity"] == 2
    assert long_row["side"] == "LONG"

    assert short_row["quantity"] == -1
    assert short_row["side"] == "SHORT"


def test_r811_current_quantity_is_authoritative_when_present():
    mapped = map_positions(
        {
            "positions": [
                {
                    "symbol": "TD",
                    "securityType": "Stock",
                    "currentQuantity": 0,
                    "openQuantity": 5,
                    "closedQuantity": 5,
                }
            ]
        },
        generated_at=TS,
    )

    # Questrade currentQuantity, when present, is the effective quantity
    # already used by the pre-existing mapper contract.
    assert mapped["holdings"] == []
    assert mapped["position_count"] == 0


def test_r811_closed_pnl_does_not_become_current_canonical_exposure_or_pnl():
    raw = {
        "selected_broker": "QUESTRADE",
        "canonical_mode": "LIVE_READ_ONLY",
        "questrade": {
            "status": "AVAILABLE",
            "balances": {
                "acquisition_timestamp": TS,
                "combinedBalances": [
                    {
                        "currency": "CAD",
                        "cash": 1567.090372,
                        "marketValue": 0.0,
                        "totalEquity": 1567.090372,
                        "buyingPower": 5182.792411,
                    }
                ],
            },
            "positions": {
                "acquisition_timestamp": TS,
                "positions": [
                    {
                        "symbol": "TD",
                        "securityType": "Stock",
                        "openQuantity": 0,
                        "closedQuantity": 5,
                        "closedPnl": 309.2025,
                    },
                    {
                        "symbol": "T.TO",
                        "securityType": "Stock",
                        "openQuantity": 0,
                        "closedQuantity": 10,
                        "closedPnl": -108.2,
                    },
                    {
                        "symbol": "ENB",
                        "securityType": "Stock",
                        "openQuantity": 0,
                        "closedQuantity": 10,
                        "closedPnl": 165.859,
                    },
                ],
            },
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }

    canonical = build_canonical_broker_portfolio(
        raw,
        now=NOW,
    )

    assert canonical["status"] == "AVAILABLE"
    assert canonical["exposures"] == []

    assert canonical["metrics"]["open_positions"]["value"] == 0

    assert (
        canonical["metrics"]["realized_pnl"]["availability"]
        == "UNAVAILABLE"
    )
    assert (
        canonical["metrics"]["session_pnl"]["availability"]
        == "UNAVAILABLE"
    )

    assert canonical["execution_allowed"] is False
    assert canonical["live_trading_blocked"] is True
    assert canonical["broker_execution_armed"] is False
    assert canonical["advisory_only"] is True
