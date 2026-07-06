from __future__ import annotations

import json

from backend.app.accounting.real_balance_engine import RealBalanceEngine
from backend.app.risk.equity_drawdown_guard import EquityDrawdownPolicy, evaluate_equity_drawdown
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials
from backend.runtime.capital_state import canonical_drawdown_display


class _ZeroFundedOandaAdapter:
    def get_account_summary(self):
        return {"ok": True, "data": {"account": {"balance": "0.0", "NAV": "0.0"}}}

    def extract_balance_nav(self, summary):
        _ = summary
        return {"balance": "0.0", "nav": "0.0"}


def _valid_gate_inputs() -> tuple[dict, dict, dict]:
    candidate = {
        "asset_class": "crypto",
        "expected_value": 1.5,
        "cost": 0.2,
        "probability": 0.8,
        "symbol": "BTC-USD",
    }
    session = {
        "created": 1e9,
        "role": "TRADER",
    }
    portfolio_state = {
        "crypto": 0,
    }
    return candidate, session, portfolio_state


def test_phase156c_missing_coinbase_credentials_are_not_reported_as_true_drawdown(monkeypatch) -> None:
    for name in (
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_API_KEY",
        "COINBASE_API_SECRET",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    balance = RealBalanceEngine("COINBASE", None).get_balance()
    decision = evaluate_equity_drawdown(
        current_equity=0.0,
        peak_equity=200.0,
        policy=EquityDrawdownPolicy(max_drawdown_pct=5.0),
        capital_state=balance["capital_state"],
        drawdown_reason=balance["drawdown_reason"],
    )

    assert balance["drawdown_status"] == "NOT_COMPUTABLE"
    assert balance["trade_gate_decision"] == "BLOCK"
    assert decision["drawdown_status"] == "NOT_COMPUTABLE"
    assert decision["drawdown_pct"] is None
    assert "credential" in str(balance["drawdown_reason"]).lower() or "unavailable" in str(balance["drawdown_reason"]).lower()


def test_phase156c_broker_balance_unavailable_maps_to_not_computable_drawdown() -> None:
    balance = RealBalanceEngine("COINBASE", None).get_balance()

    assert balance["balance"] is None
    assert balance["equity"] is None
    assert balance["capital_state"] in {
        "BROKER_BALANCE_UNAVAILABLE",
        "BROKER_CREDENTIALS_MISSING",
        "BROKER_CREDENTIALS_INVALID",
    }
    assert balance["drawdown_status"] == "NOT_COMPUTABLE"
    assert balance["trade_gate_reason"] == "CAPITAL_STATE_UNAVAILABLE"
    assert balance["live_execution_authority"] == "NO"


def test_phase156c_zero_funded_account_is_distinct_from_unavailable_balance() -> None:
    balance = RealBalanceEngine("OANDA", _ZeroFundedOandaAdapter()).get_balance()

    assert balance["capital_state"] == "ZERO_FUNDED_ACCOUNT"
    assert balance["drawdown_status"] == "NOT_COMPUTABLE"
    assert "zero funded" in str(balance["drawdown_reason"]).lower()


def test_phase157a_simulated_capital_drawdown_computes_normally() -> None:
    decision = evaluate_equity_drawdown(
        current_equity=80.0,
        peak_equity=100.0,
        policy=EquityDrawdownPolicy(max_drawdown_pct=50.0),
        capital_state="SIMULATED_CAPITAL_READY",
    )

    assert decision["allowed"] is True
    assert decision["drawdown_status"] == "COMPUTED"
    assert decision["drawdown_pct"] == 20.0


def test_phase157a_real_funded_capital_drawdown_computes_normally() -> None:
    decision = evaluate_equity_drawdown(
        current_equity=90.0,
        peak_equity=100.0,
        policy=EquityDrawdownPolicy(max_drawdown_pct=25.0),
        capital_state="CAPITAL_READY",
    )

    assert decision["allowed"] is True
    assert decision["drawdown_status"] == "COMPUTED"
    assert decision["capital_state"] == "CAPITAL_READY"


def test_phase156c_unavailable_capital_blocks_unified_trade_gate() -> None:
    candidate, session, portfolio_state = _valid_gate_inputs()
    candidate["capital_state"] = "BROKER_BALANCE_UNAVAILABLE"

    decision = CSSUnifiedTradeGate().approve_trade(
        candidate=candidate,
        session=session,
        portfolio_state=portfolio_state,
        engine_mode="SAFE",
    )

    assert decision.approved is False
    assert "CAPITAL_STATE_UNAVAILABLE" in decision.reason


def test_phase156c_unknown_capital_state_fails_closed() -> None:
    candidate, session, portfolio_state = _valid_gate_inputs()
    candidate["capital_state"] = "UNKNOWN_CAPITAL_STATE"

    decision = CSSUnifiedTradeGate().approve_trade(
        candidate=candidate,
        session=session,
        portfolio_state=portfolio_state,
        engine_mode="SAFE",
    )

    assert decision.approved is False
    assert "CAPITAL_STATE_UNAVAILABLE" in decision.reason


def test_phase156c_diagnostics_and_capital_payloads_do_not_leak_secrets() -> None:
    diagnostics = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "organizations/hidden/apiKeys/top-secret",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----hidden-----END PRIVATE KEY-----",
        },
    ).as_dict()
    balance = RealBalanceEngine("COINBASE", None).get_balance()
    payload = json.dumps({"diagnostics": diagnostics, "balance": balance})

    assert "top-secret" not in payload
    assert "BEGIN PRIVATE KEY" not in payload
    assert "hidden" not in payload.lower()


def test_phase156d_missing_credentials_display_not_computable_instead_of_100_pct() -> None:
    display = canonical_drawdown_display(
        current_equity=0.0,
        peak_equity=200.0,
        max_drawdown_pct=5.0,
        capital_state="BROKER_CREDENTIALS_MISSING",
        drawdown_reason="Broker credentials missing",
    )

    assert display["drawdown_display"] == "NOT COMPUTABLE"
    assert display["drawdown_status"] == "NOT_COMPUTABLE"
    assert display["capital_state"] == "BROKER_CREDENTIALS_MISSING"
    assert "credential" in display["drawdown_reason"].lower()


def test_phase156d_broker_balance_unavailable_display_not_computable() -> None:
    display = canonical_drawdown_display(
        current_equity=0.0,
        peak_equity=200.0,
        max_drawdown_pct=5.0,
        capital_state="BROKER_BALANCE_UNAVAILABLE",
        drawdown_reason="Broker balance unavailable",
    )

    assert display["drawdown_display"] == "NOT COMPUTABLE"
    assert display["drawdown_status"] == "NOT_COMPUTABLE"
    assert display["capital_state"] == "BROKER_BALANCE_UNAVAILABLE"


def test_phase156d_simulated_drawdown_display_remains_numeric() -> None:
    display = canonical_drawdown_display(
        current_equity=80.0,
        peak_equity=100.0,
        max_drawdown_pct=50.0,
        capital_state="SIMULATED_CAPITAL_READY",
    )

    assert display["drawdown_status"] == "COMPUTED"
    assert display["drawdown_display"] == "20.0000%"


def test_phase156d_real_funded_drawdown_display_remains_numeric() -> None:
    display = canonical_drawdown_display(
        current_equity=90.0,
        peak_equity=100.0,
        max_drawdown_pct=25.0,
        capital_state="CAPITAL_READY",
    )

    assert display["drawdown_status"] == "COMPUTED"
    assert display["drawdown_display"] == "10.0000%"


def test_phase156d_runtime_display_uses_canonical_capital_state_fields() -> None:
    display = canonical_drawdown_display(
        current_equity=0.0,
        peak_equity=200.0,
        max_drawdown_pct=5.0,
        capital_state="ACCOUNT_DATA_NOT_READY",
        drawdown_reason="Account data not ready",
    )

    assert set(display) >= {
        "drawdown_display",
        "drawdown_status",
        "drawdown_reason",
        "capital_state",
        "evaluation",
    }
    assert display["drawdown_display"] == "NOT COMPUTABLE"
    assert display["capital_state"] == "ACCOUNT_DATA_NOT_READY"
