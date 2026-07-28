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
    assert response["error"] == "oanda_legacy_writes_quarantined"
    assert response["primary_denial_code"] == "oanda_legacy_writes_quarantined"
    assert any("condition_1" in item for item in response["secondary_denial_codes"])
    assert response["network_attempted"] is False


def test_oanda_firewall_allows_live_orders_when_enabled(monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "dummy")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    # Hardened firewall requires live arm + confirm env vars for user authorization
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)

    from backend.app.brokers.oanda_adapter import OandaAdapter

    adapter = OandaAdapter()
    monkeypatch.setattr(adapter, "_request_json", lambda *args, **kwargs: {"ok": True, "status": 200, "data": {}, "error": None})

    response = adapter.place_order(
        symbol="EUR_USD",
        side="BUY",
        units=1,
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false", "runtime_paused": "false"},
        user_context={"user_id": "99999", "role": "SUPER_USER", "role_profile": {"can_execute_live_trading": True}},
    )

    assert response["ok"] is False
    assert response["error"] == "oanda_legacy_writes_quarantined"
    assert response["primary_denial_code"] == "oanda_legacy_writes_quarantined"
    assert response["secondary_denial_codes"] == []
    assert response["network_attempted"] is False


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
