"""
tests/test_oanda_live_firewall.py

Targeted tests for the OANDA live execution firewall hardening patch.

Coverage:
  - Each of the 8 firewall conditions blocks when not met
  - All 8 conditions passing allows the firewall through
  - place_order() returns an explicit firewall-denied error when blocked
  - place_order() returns the correct error key for each denial reason
  - practice / paper paths are unaffected (read endpoints, close_trade/position)
  - kill switch blocks at condition 5
  - runtime paused blocks at condition 6
  - margin lock blocks at condition 8
  - health RED blocks at condition 8
  - default state is fail-closed (no env var = blocked)
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from backend.app.brokers.oanda_adapter import OandaAdapter, OandaLiveFirewallDecision, OrderRequest


# ─── Helpers ─────────────────────────────────────────────────────────────────

SUPER_USER_CTX: Dict[str, Any] = {
    "user_id": "99999",
    "role": "SUPER_USER",
    "role_profile": {"can_execute_live_trading": True},
}

TRADER_CTX: Dict[str, Any] = {
    "user_id": "11111",
    "role": "TRADER",
    "role_profile": {"can_execute_live_trading": False},
}


def _armed_adapter(monkeypatch) -> OandaAdapter:
    """Return an OandaAdapter with OANDA_ENABLE_LIVE_TRADING=1."""
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    return OandaAdapter()


def _all_conditions_pass_kwargs(monkeypatch) -> Dict[str, Any]:
    """Return kwargs that satisfy all 8 firewall conditions."""
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    return {
        "broker_mode": "live",
        "broker_execution_armed": True,
        "governance_approved": True,
        "controls": {"trading_paused": "false", "runtime_paused": "false"},
        "user_context": SUPER_USER_CTX,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1 — Default / fail-closed behaviour
# ═══════════════════════════════════════════════════════════════════════════════

def test_default_state_is_fail_closed(monkeypatch):
    """No env vars set → firewall blocked at condition 1."""
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    assert not adapter.allow_live_trades
    result = adapter._evaluate_live_firewall()
    assert not result.allowed
    assert "condition_1" in result.denied_reason


def test_place_order_is_blocked_by_default(monkeypatch):
    """place_order() with no args must return a firewall-denied error."""
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    result = adapter.place_order(symbol="EUR_USD")
    assert not result["ok"]
    assert "live_firewall_denied" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2 — Individual condition failures
# ═══════════════════════════════════════════════════════════════════════════════

def test_condition_1_env_var_not_set_blocks(monkeypatch):
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_1" in d.denied_reason
    assert "OANDA_ENABLE_LIVE_TRADING_not_set" in d.denied_reason


def test_condition_2_broker_mode_not_live_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    for mode in ("paper", "practice", "", "PAPER", "test"):
        d = adapter._evaluate_live_firewall(
            broker_mode=mode,
            broker_execution_armed=True,
            governance_approved=True,
            user_context=SUPER_USER_CTX,
        )
        assert not d.allowed, f"Expected block for broker_mode={mode!r}"
        assert "condition_2" in d.denied_reason


def test_condition_2_live_broker_mode_passes(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    adapter = OandaAdapter()
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    # Should not fail at condition 2 (may fail at 7 if live_toggle is strict)
    assert "condition_2" not in d.denied_reason


def test_condition_3_execution_not_armed_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=False,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_3" in d.denied_reason
    assert "broker_execution_not_armed" in d.denied_reason


def test_condition_4_governance_not_approved_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=False,
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_4" in d.denied_reason
    assert "governance_not_approved" in d.denied_reason


def test_condition_5_env_kill_switch_blocks(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "1")
    adapter = OandaAdapter()
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_5" in d.denied_reason
    assert "kill_switch" in d.denied_reason


def test_condition_5_mobile_controls_kill_switch_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"live_order_kill_switch": True},
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_5" in d.denied_reason


def test_condition_5_global_kill_switch_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"global_live_order_kill_switch": True},
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_5" in d.denied_reason


def test_condition_6_trading_paused_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    for paused_val in ("true", "1", "yes"):
        d = adapter._evaluate_live_firewall(
            broker_mode="live",
            broker_execution_armed=True,
            governance_approved=True,
            controls={"trading_paused": paused_val},
            user_context=SUPER_USER_CTX,
        )
        assert not d.allowed, f"Expected block for trading_paused={paused_val!r}"
        assert "condition_6" in d.denied_reason
        assert "runtime_paused" in d.denied_reason


def test_condition_6_runtime_paused_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"runtime_paused": "true"},
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_6" in d.denied_reason


def test_condition_7_unauthorized_user_blocks(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    # TRADER without can_execute_live_trading should be blocked
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false"},
        user_context=TRADER_CTX,
    )
    assert not d.allowed
    assert "condition_7" in d.denied_reason


def test_condition_7_no_user_context_blocks(monkeypatch):
    """No user context at all — must fail closed."""
    adapter = _armed_adapter(monkeypatch)
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    # Ensure no audit thread-local is set
    from backend.app.observability.audit_context import clear_audit_user
    clear_audit_user()
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false"},
        user_context=None,
    )
    assert not d.allowed
    assert "condition_7" in d.denied_reason


def test_condition_8_margin_rejection_lock_blocks(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    adapter = OandaAdapter()
    adapter.margin_rejection_lock = True
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false"},
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_8" in d.denied_reason
    assert "margin_rejection_lock" in d.denied_reason


def test_condition_8_health_red_blocks(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    adapter = OandaAdapter()
    adapter.health_state = "RED"
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false"},
        user_context=SUPER_USER_CTX,
    )
    assert not d.allowed
    assert "condition_8" in d.denied_reason
    assert "health_RED" in d.denied_reason


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3 — All conditions passing
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_conditions_passing_allows_firewall(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    adapter = OandaAdapter()
    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false", "runtime_paused": "false"},
        user_context=SUPER_USER_CTX,
    )
    assert d.allowed
    assert d.denied_reason == ""
    assert d.audit_log.get("firewall_result") == "ALLOWED"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4 — place_order() integration
# ═══════════════════════════════════════════════════════════════════════════════

def test_place_order_returns_firewall_denied_on_condition_1(monkeypatch):
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    result = adapter.place_order(
        symbol="EUR_USD",
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    assert not result["ok"]
    assert result["error"].startswith("live_firewall_denied:")
    assert "condition_1" in result["error"]


def test_place_order_missing_symbol_caught_before_firewall(monkeypatch):
    """missing_symbol guard runs before firewall — validate order hygiene."""
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    result = adapter.place_order(symbol="")
    assert not result["ok"]
    assert result["error"] == "missing_symbol"


def test_place_order_order_request_firewall_denied(monkeypatch):
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    result = adapter.place_order(
        order=OrderRequest(symbol="GBP_USD", side="BUY", units=100),
    )
    assert not result["ok"]
    assert "live_firewall_denied" in result["error"]


def test_place_order_kill_switch_returns_firewall_denied(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "1")
    adapter = OandaAdapter()
    result = adapter.place_order(
        symbol="EUR_USD",
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        user_context=SUPER_USER_CTX,
    )
    assert not result["ok"]
    assert "condition_5" in result["error"]


def test_place_order_governance_denied_returns_firewall_denied(monkeypatch):
    adapter = _armed_adapter(monkeypatch)
    result = adapter.place_order(
        symbol="EUR_USD",
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=False,
        user_context=SUPER_USER_CTX,
    )
    assert not result["ok"]
    assert "condition_4" in result["error"]


def test_place_order_logs_denial(monkeypatch, caplog):
    import logging
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    with caplog.at_level(logging.WARNING, logger=""):
        adapter.place_order(symbol="EUR_USD", broker_mode="live")
    assert "OANDA FIREWALL" in caplog.text
    assert "DENIED" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5 — Practice / paper paths unaffected
# ═══════════════════════════════════════════════════════════════════════════════

def test_close_trade_not_blocked_by_firewall(monkeypatch):
    """close_trade() must NOT go through the live firewall — it reduces risk."""
    monkeypatch.setenv("OANDA_API_KEY", "test-key")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()

    with patch.object(adapter, "_request_json", return_value={"ok": True, "status": 200, "data": {}, "error": None}) as mock_req:
        result = adapter.close_trade("trade-abc-123")

    assert result["ok"]
    mock_req.assert_called_once()


def test_close_position_not_blocked_by_firewall(monkeypatch):
    """close_position() must NOT go through the live firewall."""
    monkeypatch.setenv("OANDA_API_KEY", "test-key")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()

    with patch.object(adapter, "_request_json", return_value={"ok": True, "status": 200, "data": {}, "error": None}) as mock_req:
        result = adapter.close_position("EUR_USD")

    assert result["ok"]
    mock_req.assert_called_once()


def test_get_account_summary_not_blocked_by_firewall(monkeypatch):
    """Read endpoints must be unaffected by live firewall state."""
    monkeypatch.setenv("OANDA_API_KEY", "test-key")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "123")
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()

    with patch.object(adapter, "_request_json", return_value={"ok": True, "status": 200, "data": {"account": {}}, "error": None}) as mock_req:
        result = adapter.get_account_summary()

    assert result["ok"]
    mock_req.assert_called_once()


def test_oanda_practice_mode_live_flag_remains_off_by_default(monkeypatch):
    """OANDA practice URLs do not enable live trading. Flag must remain False."""
    monkeypatch.setenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    assert not adapter.allow_live_trades


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6 — Audit log content
# ═══════════════════════════════════════════════════════════════════════════════

def test_firewall_audit_log_contains_condition_states(monkeypatch):
    monkeypatch.setenv("OANDA_ENABLE_LIVE_TRADING", "1")
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.setenv("REA_LIVE_ARM", "1")
    monkeypatch.setenv("REA_CONFIRM_LIVE", "YES")
    monkeypatch.delenv("CSS_LIVE_ORDER_KILL_SWITCH", raising=False)
    adapter = OandaAdapter()

    d = adapter._evaluate_live_firewall(
        broker_mode="live",
        broker_execution_armed=True,
        governance_approved=True,
        controls={"trading_paused": "false"},
        user_context=SUPER_USER_CTX,
    )
    log = d.audit_log
    assert "oanda_enable_live_trading" in log
    assert "broker_mode" in log
    assert "broker_execution_armed" in log
    assert "governance_approved" in log
    assert "kill_switch_blocked" in log
    assert "trading_paused" in log
    assert "user_authorized" in log
    assert "margin_rejection_lock" in log
    assert "health_state" in log


def test_firewall_audit_log_populated_on_denial(monkeypatch):
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    adapter = OandaAdapter()
    d = adapter._evaluate_live_firewall()
    assert "oanda_enable_live_trading" in d.audit_log
    assert d.audit_log["oanda_enable_live_trading"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 7 — Backward-compatible error keys (existing tests must still pass)
# ═══════════════════════════════════════════════════════════════════════════════

def test_live_firewall_denied_error_key_contains_reason():
    """
    The new error key format is 'live_firewall_denied:<reason>'.
    Tests that previously checked for 'live_execution_blocked_by_firewall'
    must be updated; this test documents the new canonical format.
    """
    import os
    old_val = os.environ.pop("OANDA_ENABLE_LIVE_TRADING", None)
    try:
        adapter = OandaAdapter()
        result = adapter.place_order(symbol="EUR_USD")
        assert result["error"].startswith("live_firewall_denied:")
    finally:
        if old_val is not None:
            os.environ["OANDA_ENABLE_LIVE_TRADING"] = old_val
