import importlib
import inspect
import time

import pytest
from fastapi import HTTPException


def _reload_auth_modules():
    import backend.app.auth.auth_config as auth_config
    import backend.app.auth.auth_router as auth_router

    importlib.reload(auth_config)
    importlib.reload(auth_router)
    return auth_config, auth_router


def test_auth_requires_password_env(monkeypatch):
    monkeypatch.delenv("REA_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.setenv("REA_SUPERUSER_USERNAME", "admin")
    auth_config, auth_router = _reload_auth_modules()

    assert auth_config.REA_SUPERUSER_PASSWORD == ""

    with pytest.raises(HTTPException) as excinfo:
        auth_router.login(auth_router.LoginRequest(username="admin", password="x"))

    assert excinfo.value.status_code == 503
    assert "Superuser password not configured" in str(excinfo.value.detail)


def test_headless_mode_does_not_return_otp(monkeypatch):
    monkeypatch.setenv("REA_SUPERUSER_PASSWORD", "strongpass")
    monkeypatch.setenv("REA_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("HEADLESS_DEV_MODE", "1")
    auth_config, auth_router = _reload_auth_modules()

    response = auth_router.login(auth_router.LoginRequest(username="admin", password="strongpass"))

    assert response.ok is True
    assert "OTP=" not in response.message
    assert "generated" in response.message.lower()


def test_auth_rate_limit_on_login(monkeypatch):
    monkeypatch.setenv("REA_SUPERUSER_PASSWORD", "strongpass")
    monkeypatch.setenv("REA_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("HEADLESS_DEV_MODE", "1")
    monkeypatch.setenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
    auth_config, auth_router = _reload_auth_modules()

    request = auth_router.LoginRequest(username="admin", password="wrong")

    for _ in range(3):
        with pytest.raises(HTTPException) as excinfo:
            auth_router.login(request)
        assert excinfo.value.status_code == 401

    with pytest.raises(HTTPException) as excinfo:
        auth_router.login(request)
    assert excinfo.value.status_code == 429


def test_oanda_firewall_blocks_live_orders_without_env(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    response = adapter.place_order(symbol="EUR_USD", side="BUY", units=1)

    assert response["ok"] is False
    assert response["error"] == "live_execution_blocked_by_firewall"


def test_oanda_env_flag_alone_cannot_authorize_live_order(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.delenv("REA_LIVE_ARM", raising=False)
    monkeypatch.delenv("REA_CONFIRM_LIVE", raising=False)

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    response = adapter.place_order(
        symbol="EUR_USD",
        side="BUY",
        units=1,
        idempotency_key="test-order-1",
        user_context={
            "user_id": "22222",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": True},
        },
    )

    assert response["ok"] is False
    assert response["error"].startswith(
        "live_execution_blocked_by_canonical_gate"
    )


def test_oanda_allows_order_only_after_canonical_live_authorization(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    monkeypatch.setattr(
        adapter,
        "_request_json",
        lambda *args, **kwargs: {
            "ok": True,
            "status": 200,
            "data": {},
            "error": None,
        },
    )

    response = adapter.place_order(
        symbol="EUR_USD",
        side="BUY",
        units=1,
        idempotency_key="test-order-2",
        user_context={
            "user_id": "22222",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": True},
        },
    )

    assert response["ok"] is True


def test_oanda_order_requires_idempotency_key(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    response = adapter.place_order(
        symbol="EUR_USD",
        side="BUY",
        units=1,
        user_context={
            "user_id": "22222",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": True},
        },
    )

    assert response["ok"] is False
    assert response["error"] == "missing_idempotency_key"


def test_oanda_order_unit_ceiling_is_enforced(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("OANDA_MAX_ORDER_UNITS", "10")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    response = adapter.place_order(
        symbol="EUR_USD",
        side="BUY",
        units=11,
        idempotency_key="test-order-3",
        user_context={
            "user_id": "22222",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": True},
        },
    )

    assert response["ok"] is False
    assert response["error"] == "order_units_exceed_configured_ceiling"


def test_oanda_private_mutation_request_cannot_bypass_authorization(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    response = adapter._request_json(
        "POST",
        "v3/accounts/123/orders",
        {"order": {}},
    )

    assert response["ok"] is False
    assert (
        response["error"]
        == "broker_mutation_requires_canonical_authorization"
    )


def test_headless_guarded_entry_execution_gate_no_arg():
    import backend.app.headless_guarded_entry as headless_guarded_entry

    source = inspect.getsource(headless_guarded_entry)
    assert "ExecutionGate(allow_live=cfg.allow_live)" not in source


def test_trade_decision_orchestrator_capital_allocator_init(monkeypatch):
    monkeypatch.setenv("CSS_TOTAL_CAPITAL", "50000")
    import backend.intelligence.trade_decision_orchestrator as tdo

    importlib.reload(tdo)
    orchestrator = tdo.TradeDecisionOrchestrator()

    assert orchestrator.capital_allocator.total_capital == 50000.0


def test_css_unified_trade_gate_normalizes_asset_class():
    from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate

    gate = CSSUnifiedTradeGate()
    candidate = {
        "asset_class": "CRYPTO",
        "expected_value": 10.0,
        "cost": 1.0,
        "probability": 0.8,
    }
    session = {"role": "TRADER", "created": time.time()}
    portfolio_state = {"crypto": 0}

    decision = gate.evaluate(
        candidate=candidate,
        session=session,
        portfolio_state=portfolio_state,
        engine_mode="SAFE",
    )

    assert decision.approved is True
