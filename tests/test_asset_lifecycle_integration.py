from decimal import Decimal

import pytest

import backend.app.persistence.db as db_module
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycleError


@pytest.fixture
def runtime_service(tmp_path, monkeypatch):
    db_path = tmp_path / "css_runtime.db"
    db_module.close_connection()
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(db_module, "_CONNECTION", None)

    repository = TradeOutcomeRepository(tmp_path / "warehouse.json")
    repository.create_storage()
    service = TradeRuntimeService(canonical_lifecycle=__import__("backend.execution.canonical_trade_lifecycle", fromlist=["CanonicalTradeLifecycle"]).CanonicalTradeLifecycle(repository))
    return service


def _seed_trade(service, trade_id, symbol, broker_name, broker_mode, asset_class, strategy_id="mean"):
    session_id = f"{trade_id}-session"
    if service.persistence.sessions.get_session(session_id) is None:
        service.persistence.sessions.create_session(
            session_id=session_id,
            status="active",
            mode="paper",
            broker_name=broker_name,
            broker_mode=broker_mode,
            started_at="2026-06-24T10:00:00+00:00",
        )
    service.open_trade(
        trade_id=trade_id,
        session_id=session_id,
        broker_name=broker_name,
        broker_mode=broker_mode,
        symbol=symbol,
        direction="BUY",
        order_type="MARKET",
        quantity=Decimal("1"),
        filled_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        raw_payload_json='{"asset_class": "%s", "strategy_id": "%s", "market_regime": "risk_on"}' % (asset_class, strategy_id),
    )


def test_fx_lifecycle_integration(runtime_service):
    _seed_trade(runtime_service, "fx-close-1", "EUR_USD", "OANDA", "paper", "FX")
    runtime_service.close_trade("fx-close-1", Decimal("101"), Decimal("1"))
    trades = runtime_service.persistence.trades.get_all_session_trades("fx-close-1-session")
    assert trades[0]["status"] == "closed"


def test_crypto_lifecycle_integration(runtime_service):
    _seed_trade(runtime_service, "crypto-close-1", "BTC_USD", "COINBASE", "paper", "CRYPTO")
    runtime_service.close_trade("crypto-close-1", Decimal("102"), Decimal("2"))
    trades = runtime_service.persistence.trades.get_all_session_trades("crypto-close-1-session")
    assert trades[0]["status"] == "closed"


def test_options_lifecycle_integration(runtime_service):
    _seed_trade(runtime_service, "options-close-1", "SPY-C-250", "SIM", "paper", "OPTIONS")
    runtime_service.close_trade("options-close-1", Decimal("103"), Decimal("3"))
    trades = runtime_service.persistence.trades.get_all_session_trades("options-close-1-session")
    assert trades[0]["status"] == "closed"


def test_futures_lifecycle_integration(runtime_service):
    _seed_trade(runtime_service, "futures-close-1", "ES", "SIM", "paper", "FUTURES")
    runtime_service.close_trade("futures-close-1", Decimal("104"), Decimal("4"))
    trades = runtime_service.persistence.trades.get_all_session_trades("futures-close-1-session")
    assert trades[0]["status"] == "closed"


def test_duplicate_persistence_prevention(runtime_service):
    _seed_trade(runtime_service, "dup-close-1", "EUR_USD", "OANDA", "paper", "FX")
    runtime_service.close_trade("dup-close-1", Decimal("105"), Decimal("5"))

    with pytest.raises(CanonicalTradeLifecycleError):
        runtime_service.close_trade("dup-close-1", Decimal("106"), Decimal("6"))


def test_paper_mode_compatibility(runtime_service):
    _seed_trade(runtime_service, "paper-close-1", "EUR_USD", "OANDA", "paper", "FX")
    runtime_service.close_trade("paper-close-1", Decimal("107"), Decimal("7"))
    assert runtime_service.persistence.trades.get_trade("paper-close-1")["status"] == "closed"


def test_fail_closed_unsupported_asset(runtime_service):
    _seed_trade(runtime_service, "unsupported-close-1", "AAPL", "SIM", "paper", "equity")
    with pytest.raises(CanonicalTradeLifecycleError):
        runtime_service.close_trade("unsupported-close-1", Decimal("108"), Decimal("8"))
