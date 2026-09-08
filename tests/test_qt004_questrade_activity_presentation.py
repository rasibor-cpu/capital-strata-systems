from datetime import datetime, timezone

from launcher import css_mobile_launcher as launcher


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _snapshot(rows=None, *, status="AVAILABLE", reason=None):
    ts = _ts()

    return {
        "status": "AVAILABLE",
        "acquisition_timestamp": ts,
        "balances": {
            "acquisition_timestamp": ts,
            "combinedBalances": [],
        },
        "positions": {
            "acquisition_timestamp": ts,
            "positions": [],
        },
        "activities": {
            "status": status,
            "provenance": "QUESTRADE_ACTIVITIES",
            "acquisition_timestamp": ts,
            "activity_count": len(rows or []),
            "activities": list(rows or []),
            "reason": reason,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def test_qt004_classifies_live_dividend_shape_without_portfolio_semantics():
    row = {
        "tradeDate": "2026-09-01T00:00:00.000000-04:00",
        "transactionDate": "2026-09-01T00:00:00.000000-04:00",
        "settlementDate": "2026-09-01T00:00:00.000000-04:00",
        "action": "DIV",
        "symbol": "ENB",
        "description": "ENBRIDGE INC CASH DIV ON 10 SHS",
        "quantity": 0,
        "price": 0,
        "grossAmount": 0,
        "netAmount": 6.91,
        "currency": "USD",
        "type": "Dividends",
    }

    result = launcher._build_questrade_activity_presentation(
        _snapshot([row])
    )

    assert result["status"] == "AVAILABLE"
    assert result["activity_count"] == 1
    assert result["classification_counts"]["DIVIDEND"] == 1

    item = result["rows"][0]
    assert item["classification"] == "DIVIDEND"
    assert item["symbol"] == "ENB"
    assert item["net_amount"] == 6.91
    assert item["currency"] == "USD"

    assert result["telemetry_semantics"] == "ACCOUNT_HISTORY"
    assert result["real_time_fill_feed"] is False
    assert result["portfolio_mutation_authority"] is False
    assert result["execution_authority"] is False


def test_qt004_classifies_supported_activity_families():
    rows = [
        {
            "action": "BUY",
            "symbol": "ABC",
            "type": "Trades",
        },
        {
            "description": "ECN FEE",
            "type": "Fees",
        },
        {
            "description": "ACCOUNT TRANSFER",
            "type": "Transfers",
        },
        {
            "description": "CASH INTEREST",
            "type": "Interest",
        },
        {
            "description": "NON RESIDENT WITHHOLDING TAX",
            "type": "Tax",
        },
        {
            "description": "BROKER ADJUSTMENT",
            "type": "Adjustment",
        },
    ]

    result = launcher._build_questrade_activity_presentation(
        _snapshot(rows)
    )

    assert [row["classification"] for row in result["rows"]] == [
        "TRADE",
        "FEE",
        "TRANSFER",
        "INTEREST",
        "TAX",
        "OTHER",
    ]


def test_qt004_empty_available_history_is_valid():
    result = launcher._build_questrade_activity_presentation(
        _snapshot([])
    )

    assert result["status"] == "AVAILABLE"
    assert result["activity_count"] == 0
    assert result["rows"] == []
    assert sum(result["classification_counts"].values()) == 0


def test_qt004_unavailable_history_stays_unavailable_and_fail_closed():
    result = launcher._build_questrade_activity_presentation(
        _snapshot(
            [],
            status="UNAVAILABLE",
            reason="activity_temporarily_unavailable",
        )
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["activity_count"] == 0
    assert result["reason"] == "activity_temporarily_unavailable"
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True


def test_qt004_launcher_projects_activity_separately_from_canonical_portfolio(
    monkeypatch,
):
    activity = {
        "action": "DIV",
        "symbol": "ENB",
        "description": "ENBRIDGE INC CASH DIV",
        "netAmount": 6.91,
        "currency": "USD",
        "type": "Dividends",
    }

    snapshot = _snapshot([activity])

    monkeypatch.setattr(
        launcher._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        lambda: snapshot,
    )

    base = {
        "runtime_status": {
            "runtime_mode": "DISABLED",
            "effective_mode": "DISABLED",
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }

    result = launcher.apply_launcher_questrade_read_only_cache(base)

    assert result["broker_activity"]["activity_count"] == 1
    assert (
        result["broker_activity"]["rows"][0]["classification"]
        == "DIVIDEND"
    )

    canonical = result["canonical_broker_portfolio"]

    # Activity rows must not become holdings or positions.
    assert canonical["exposures"] == []

    # Dividend cash-flow history must not be synthesized into
    # canonical realized/session P&L.
    assert (
        canonical["metrics"]["realized_pnl"]["availability"]
        == "UNAVAILABLE"
    )
    assert (
        canonical["metrics"]["session_pnl"]["availability"]
        == "UNAVAILABLE"
    )

    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True


def test_qt004_activity_projection_does_not_mutate_raw_snapshot():
    row = {
        "action": "DIV",
        "symbol": "ENB",
        "netAmount": 6.91,
        "currency": "USD",
        "type": "Dividends",
    }

    snapshot = _snapshot([row])

    before = repr(snapshot)

    launcher._build_questrade_activity_presentation(snapshot)

    assert repr(snapshot) == before
