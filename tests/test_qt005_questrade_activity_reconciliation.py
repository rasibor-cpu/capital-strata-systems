from backend.reconciliation.questrade_activity_reconciliation import (
    reconcile_questrade_activity_history,
)


def _presentation(rows, status="AVAILABLE"):
    return {
        "status": status,
        "rows": rows,
        "classification_counts": {},
        "telemetry_semantics": "ACCOUNT_HISTORY",
        "real_time_fill_feed": False,
        "portfolio_mutation_authority": False,
        "execution_authority": False,
    }


def _outcome(**overrides):
    row = {
        "trade_id": "CSS-1",
        "timestamp_open": "2026-09-07T14:00:00-04:00",
        "timestamp_close": "2026-09-08T10:30:00-04:00",
        "symbol": "TD",
        "asset_class": "EQUITIES",
        "entry_price": 80.0,
        "exit_price": 82.0,
        "quantity": 5.0,
        "realized_pnl": 10.0,
        "holding_duration_seconds": 73800.0,
        "strategy_id": "manual",
        "market_regime": "UNKNOWN",
        "broker": "QUESTRADE",
    }
    row.update(overrides)
    return row


def test_exact_trade_economic_date_match_is_corroborated():
    activity = {
        "classification": "TRADE",
        "trade_date": "2026-09-08T00:00:00-04:00",
        "action": "SELL",
        "symbol": "TD",
        "quantity": 5,
        "price": 82.0,
        "net_amount": 410.0,
        "currency": "CAD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [_outcome(currency="CAD", close_action="SELL")],
    )

    row = result["rows"][0]

    assert row["reconciliation_status"] == "CORROBORATED"
    assert row["matched_trade_id"] == "CSS-1"
    assert row["candidate_count"] == 1
    assert result["reconciliation_semantics"] == "CORROBORATION_ONLY"
    assert result["stable_broker_activity_id_available"] is False


def test_trade_without_exact_candidate_is_unmatched():
    activity = {
        "classification": "TRADE",
        "trade_date": "2026-09-08T00:00:00-04:00",
        "symbol": "TD",
        "quantity": 5,
        "price": 99.0,
        "currency": "CAD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [_outcome()],
    )

    assert result["rows"][0]["reconciliation_status"] == "UNMATCHED"
    assert result["rows"][0]["matched_trade_id"] is None


def test_multiple_exact_candidates_are_ambiguous():
    activity = {
        "classification": "TRADE",
        "trade_date": "2026-09-08",
        "symbol": "TD",
        "quantity": 5,
        "price": 82.0,
        "currency": "CAD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [
            _outcome(trade_id="CSS-1"),
            _outcome(trade_id="CSS-2"),
        ],
    )

    assert result["rows"][0]["reconciliation_status"] == "AMBIGUOUS"
    assert result["rows"][0]["candidate_count"] == 2
    assert result["rows"][0]["matched_trade_id"] is None


def test_dividend_is_not_trade_pnl_and_is_not_applicable():
    activity = {
        "classification": "DIVIDEND",
        "trade_date": "2026-09-01",
        "symbol": "ENB",
        "net_amount": 6.91,
        "currency": "USD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [],
    )

    row = result["rows"][0]

    assert row["reconciliation_status"] == "NOT_APPLICABLE"
    assert result["cash_flow_by_currency_and_classification"] == {
        "USD": {"DIVIDEND": 6.91}
    }
    assert result["pnl_promotion_authority"] is False


def test_transfer_is_capital_movement_not_profit_loss():
    activity = {
        "classification": "TRANSFER",
        "transaction_date": "2026-09-08",
        "net_amount": 1200.0,
        "currency": "CAD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [],
    )

    assert result["rows"][0]["reconciliation_status"] == "NOT_APPLICABLE"
    assert result["cash_flow_by_currency_and_classification"] == {
        "CAD": {"TRANSFER": 1200.0}
    }
    assert result["pnl_promotion_authority"] is False


def test_currency_buckets_are_never_silently_combined():
    rows = [
        {
            "classification": "DIVIDEND",
            "net_amount": 6.91,
            "currency": "USD",
        },
        {
            "classification": "FEE",
            "net_amount": -4.95,
            "currency": "CAD",
        },
    ]

    result = reconcile_questrade_activity_history(
        _presentation(rows),
        [],
    )

    assert result["cash_flow_by_currency_and_classification"] == {
        "CAD": {"FEE": -4.95},
        "USD": {"DIVIDEND": 6.91},
    }


def test_non_questrade_outcome_cannot_corroborate():
    activity = {
        "classification": "TRADE",
        "trade_date": "2026-09-08",
        "symbol": "TD",
        "quantity": 5,
        "price": 82.0,
        "currency": "CAD",
    }

    result = reconcile_questrade_activity_history(
        _presentation([activity]),
        [_outcome(broker="OANDA")],
    )

    assert result["rows"][0]["reconciliation_status"] == "UNMATCHED"


def test_unavailable_activity_history_fails_closed():
    result = reconcile_questrade_activity_history(
        _presentation([], status="UNAVAILABLE"),
        [],
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True
    assert result["trade_outcome_write_authority"] is False
    assert result["portfolio_mutation_authority"] is False
    assert result["pnl_promotion_authority"] is False
    assert result["execution_authority"] is False


def test_activity_input_is_not_mutated():
    activity = {
        "classification": "DIVIDEND",
        "symbol": "ENB",
        "net_amount": 6.91,
        "currency": "USD",
    }
    presentation = _presentation([activity])

    before = repr(presentation)

    reconcile_questrade_activity_history(
        presentation,
        [],
    )

    assert repr(presentation) == before


def _trade(**overrides):
    row = dict(classification="TRADE", trade_date="2026-09-08", symbol="TD",
               quantity=5, price=82, currency="CAD", action="SELL")
    row.update(overrides)
    return row


def test_canonical_schema_missing_currency_and_direction_is_ambiguous():
    result = reconcile_questrade_activity_history(_presentation([_trade()]), [_outcome()])
    row = result["rows"][0]
    assert row["reconciliation_status"] == "AMBIGUOUS"
    assert row["matched_trade_id"] is None
    assert row["candidates"][0]["limitations"] == ["currency_unverified", "close_action_unverified"]
    assert "realized_pnl" not in row["candidates"][0]


def test_conflicting_evidence_and_invalid_economics_do_not_match():
    cases = [dict(currency="USD"), dict(action="BUY"), dict(action="BTO"),
             dict(quantity=0), dict(price=float("inf")), dict(quantity=float("nan")),
             dict(trade_date=None, settlement_date="2026-09-08")]
    for changes in cases:
        result = reconcile_questrade_activity_history(
            _presentation([_trade(**changes)]), [_outcome(currency="CAD", close_action="SELL")])
        assert result["rows"][0]["reconciliation_status"] == "UNMATCHED"


def test_duplicate_activity_evidence_cannot_double_corroborate():
    result = reconcile_questrade_activity_history(
        _presentation([_trade(), _trade()]), [_outcome(currency="CAD", close_action="SELL")])
    assert result["reconciliation_counts"]["AMBIGUOUS"] == 2
    assert all(row["matched_trade_id"] is None for row in result["rows"])


def test_unavailable_sources_do_not_claim_success():
    result = reconcile_questrade_activity_history(_presentation([_trade()], "UNAVAILABLE"), [_outcome()])
    assert result["rows"] == []
    result = reconcile_questrade_activity_history(_presentation([_trade()]), [], outcome_source_available=False)
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "css_trade_outcomes_unavailable"


def test_cash_flow_categories_and_nonfinite_amounts():
    rows = [dict(classification=c, currency="CAD", net_amount=-2) for c in ["FEE", "TAX", "INTEREST", "TRANSFER"]]
    rows.append(dict(classification="DIVIDEND", currency="USD", net_amount=float("inf")))
    result = reconcile_questrade_activity_history(_presentation(rows), [])
    assert result["cash_flow_by_currency_and_classification"] == {"CAD": {"FEE": -2, "TAX": -2, "INTEREST": -2, "TRANSFER": -2}}


def test_launcher_reads_repository_without_writing_or_promoting_pnl(monkeypatch, tmp_path):
    import json
    from launcher import css_mobile_launcher as launcher
    path = tmp_path / "trade_outcomes.json"
    path.write_text(json.dumps([_outcome()]), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_CACHE, "read", lambda: {
        "status": "AVAILABLE", "balances": {"combinedBalances": []},
        "positions": {"positions": []}, "activities": {"status": "AVAILABLE", "activities": [
            dict(type="Trades", action="SELL", symbol="TD", quantity=5, price=82,
                 currency="CAD", tradeDate="2026-09-08", netAmount=410)]}})
    def forbidden(*args, **kwargs):
        raise AssertionError("Repository write attempted")
    monkeypatch.setattr(launcher.TradeOutcomeRepository, "append_outcome", forbidden)
    monkeypatch.setattr(launcher.TradeOutcomeRepository, "create_storage", forbidden)
    result = launcher.apply_launcher_questrade_read_only_cache({})
    assert path.read_bytes() == before
    assert result["broker_activity_reconciliation"]["rows"][0]["reconciliation_status"] == "AMBIGUOUS"
    portfolio = result["canonical_broker_portfolio"]
    assert portfolio["exposures"] == []
    for metric in ["realized_pnl", "session_pnl"]:
        assert portfolio["metrics"][metric]["availability"] == "UNAVAILABLE"
    path.write_text("invalid json", encoding="utf-8")
    result = launcher.apply_launcher_questrade_read_only_cache({})
    assert result["broker_activity_reconciliation"]["outcome_source_status"] == "UNAVAILABLE"
    assert path.read_text(encoding="utf-8") == "invalid json"
