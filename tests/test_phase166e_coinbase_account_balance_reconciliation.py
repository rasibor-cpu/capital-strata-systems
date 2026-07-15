from __future__ import annotations

from types import SimpleNamespace

from backend.runtime.canonical_account_snapshot import (
    CanonicalAccountSnapshot,
    build_canonical_account_snapshot,
    validate_account_snapshot_consumer_hash,
)
from backend.runtime.canonical_broker_runtime_state import OVERALL_FAIL_CLOSED, OVERALL_GREEN, STATUS_PASS, STATUS_UNAVAILABLE
from backend.runtime.canonical_broker_state_adapter import adapt_canonical_state_to_legacy_broker_payload
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.coinbase_live_read_only_operational_validation import CoinbaseLiveReadOnlyOperationalValidator
from dashboard.runtime.frontend_contract import build_frontend_payload
from engine.risk.margin_trade_gate import MarginTradeGate


def _runtime_success() -> dict:
    return {
        "selected_broker": "COINBASE",
        "broker": "COINBASE",
        "broker_mode": "live",
        "credential_status": "PRESENT",
        "api_reachable": True,
        "broker_authenticated": True,
        "broker_connected": True,
        "account_loaded": True,
        "portfolio_loaded": True,
        "balances_loaded": True,
        "market_data_loaded": True,
        "market_data_status": "PASS",
        "products_loaded": 9,
        "account_equity": 50.25,
        "cash": 50.25,
        "balance": 50.25,
        "buying_power": 50.25,
        "available_balance": 50.25,
        "margin_available": 50.25,
        "currency": "USD",
        "account_id": "acct-live",
        "portfolio_id": "portfolio-live",
        "order_submission_status": "DISABLED",
        "execution_scope": "READ_ONLY",
        "live_micro_pilot_state": "DISARMED",
    }


def test_phase166e_builds_single_immutable_account_snapshot_for_success() -> None:
    snapshot = build_canonical_account_snapshot(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        margin_snapshot={
            "margin_source": "LIVE",
            "account_id": "acct-live",
            "margin_available": 50.25,
            "required_margin": 0.0,
            "free_margin": 50.25,
        },
        timestamp="2026-07-15T00:00:00+00:00",
    )

    payload = snapshot.to_dict()

    assert snapshot.authenticated is True
    assert snapshot.connected is True
    assert snapshot.account_loaded is True
    assert snapshot.portfolio_loaded is True
    assert snapshot.balances_loaded is True
    assert snapshot.equity_loaded is True
    assert snapshot.buying_power_loaded is True
    assert snapshot.margin_loaded is True
    assert snapshot.market_data_loaded is True
    assert snapshot.currency == "USD"
    assert snapshot.provenance["buying_power"] == "LIVE"
    assert payload["state_hash"] == snapshot.state_hash
    assert validate_account_snapshot_consumer_hash(payload, snapshot.state_hash) is True


def test_phase166e_missing_balance_suppresses_margin_buying_power_and_equity() -> None:
    snapshot = build_canonical_account_snapshot(
        broker="COINBASE",
        mode="live",
        runtime_payload={
            **_runtime_success(),
            "balances_loaded": False,
            "balance_status": "UNAVAILABLE",
            "buying_power": 50.25,
            "margin_available": 50.25,
        },
        margin_snapshot={"margin_source": "LIVE_UNAVAILABLE", "buying_power": 0.0, "margin_available": 0.0},
    )

    assert snapshot.balances_loaded is False
    assert snapshot.equity_loaded is False
    assert snapshot.buying_power_loaded is False
    assert snapshot.margin_loaded is False
    assert snapshot.equity is None
    assert snapshot.buying_power is None
    assert snapshot.margin_available is None
    assert snapshot.provenance["equity"] == "UNAVAILABLE"
    assert snapshot.provenance["buying_power"] == "UNAVAILABLE"
    assert snapshot.provenance["margin_available"] == "UNAVAILABLE"


def test_phase166e_canonical_broker_state_embeds_account_snapshot_and_remains_advisory_only() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        margin_snapshot={"margin_source": "LIVE", "account_id": "acct-live", "buying_power": 50.25, "margin_available": 50.25},
        timestamp="2026-07-15T00:00:00+00:00",
    )
    legacy = adapt_canonical_state_to_legacy_broker_payload(state)

    assert state.overall_status == OVERALL_GREEN
    assert state.balance_status == STATUS_PASS
    assert state.account_snapshot["state_hash"]
    assert legacy["canonical_account_snapshot"]["state_hash"] == state.account_snapshot["state_hash"]
    assert legacy["buying_power"] == 50.25
    assert legacy["execution_allowed"] is False
    assert legacy["live_trading_blocked"] is True
    assert legacy["broker_execution_armed"] is False
    assert legacy["advisory_only"] is True


def test_phase166e_unavailable_balance_fails_closed_and_legacy_payload_hides_live_numbers() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False, "buying_power": 50.25, "margin_available": 50.25},
        margin_snapshot={"margin_source": "LIVE_UNAVAILABLE", "buying_power": 0.0, "margin_available": 0.0},
    )
    legacy = adapt_canonical_state_to_legacy_broker_payload(state)

    assert state.overall_status == OVERALL_FAIL_CLOSED
    assert state.balance_status == STATUS_UNAVAILABLE
    assert state.buying_power_status == STATUS_UNAVAILABLE
    assert state.margin_status == STATUS_UNAVAILABLE
    assert state.account_snapshot["balances_loaded"] is False
    assert legacy["buying_power"] is None
    assert legacy["margin_available"] is None


def test_phase166e_account_or_portfolio_mismatch_rejected() -> None:
    snapshot = build_canonical_account_snapshot(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "account_id": "acct-a", "portfolio_id": "portfolio-a"},
        adapter_status={"account_id": "acct-a", "portfolio_id": "portfolio-b"},
        margin_snapshot={"margin_source": "LIVE", "account_id": "acct-b", "margin_available": 50.25},
    )
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "canonical_account_snapshot": snapshot.to_dict()},
    )

    assert "account_identity_mismatch" in snapshot.contradiction_reasons
    assert "portfolio_identity_mismatch" in snapshot.contradiction_reasons
    assert state.overall_status == OVERALL_FAIL_CLOSED


def test_phase166e_frontend_uses_account_snapshot_to_suppress_unavailable_values() -> None:
    snapshot = CanonicalAccountSnapshot(
        broker="COINBASE",
        mode="live",
        authenticated=True,
        connected=True,
        account_loaded=True,
        portfolio_loaded=True,
        balances_loaded=False,
        market_data_loaded=True,
        currency="USD",
        buying_power=999.0,
        margin_available=999.0,
    ).to_dict()
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False, "canonical_account_snapshot": snapshot},
        margin_snapshot={"margin_source": "LIVE_UNAVAILABLE"},
    )
    frontend = build_frontend_payload(
        {
            "broker_summary": {
                **_runtime_success(),
                "buying_power": 999.0,
                "canonical_broker_runtime_state": state.to_dict(),
            }
        }
    )
    broker_section = frontend["sections"]["broker"]

    assert broker_section["canonical_account_snapshot"]["balances_loaded"] is False
    assert broker_section["buying_power"] == "DATA UNAVAILABLE"
    assert broker_section["available_balance"] == "DATA UNAVAILABLE"


def test_phase166e_operational_validator_publishes_snapshot_and_margin_parity() -> None:
    class Credentials:
        ready = True

    class FakeAdapter:
        credentials = Credentials()
        _env = {}
        authenticated = False
        connected = False
        health = "UNKNOWN"
        connection_error = ""
        last_successful_sync = ""

        def server_time(self):
            return {"status": "OK", "iso": "2026-07-15T00:00:00+00:00"}

        def account_summary(self):
            return {"balance": 75.0, "equity": 75.0, "buying_power": 75.0, "currency": "USD", "account_id": "acct-live"}

        def market_data(self):
            return {"status": "OK", "symbol": "BTC-USD", "price": 50000.0}

    result = CoinbaseLiveReadOnlyOperationalValidator(
        adapter_factory=FakeAdapter,
        now=lambda: __import__("datetime").datetime(2026, 7, 15, tzinfo=__import__("datetime").timezone.utc),
    ).validate()

    op_status = result["broker_operational_status"]
    snapshot = op_status["canonical_account_snapshot"]

    assert result["validation_status"] == "PASS"
    assert op_status["balance_status"] == "AVAILABLE"
    assert op_status["margin_status"] == "AVAILABLE"
    assert snapshot["balances_loaded"] is True
    assert snapshot["buying_power"] == 75.0
    assert snapshot["margin_available"] == 75.0
    assert result["execution_allowed"] is False
    assert result["broker_execution_status"] == "DISABLED"
    assert result["live_micro_pilot_state"] == "DISARMED"


def test_phase166e_trade_gate_consumes_account_snapshot_without_recomputing_balance() -> None:
    snapshot = build_canonical_account_snapshot(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        margin_snapshot={"margin_source": "LIVE", "account_id": "acct-live", "margin_available": 50.25, "required_margin": 0.0},
    )
    gate_snapshot = SimpleNamespace(
        buying_power=snapshot.free_margin,
        margin_state="NORMAL",
        margin_ratio=0.0,
    )
    decision = MarginTradeGate().evaluate(gate_snapshot, broker_mode="live")

    assert decision.decision == "ALLOW"
    assert decision.reason == "margin_ok"
