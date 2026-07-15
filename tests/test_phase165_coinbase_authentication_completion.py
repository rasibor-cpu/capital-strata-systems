from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from backend.runtime.coinbase_authentication_trace import (
    trace_coinbase_authentication,
    validate_coinbase_credential_material,
)
from backend.runtime.coinbase_connectivity_certificate import certify_coinbase_read_only_connectivity
from backend.runtime.live_connectivity_certifier import certify_live_connectivity


def _pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")


def _env(**overrides):
    data = {
        "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example-key",
        "COINBASE_CDP_PRIVATE_KEY": _pem(),
        "COINBASE_API_PERMISSIONS": "view,wallet:accounts:read,trade:read",
        "COINBASE_BASE_URL": "https://api.coinbase.com",
    }
    data.update(overrides)
    return data


class FakeCoinbaseReadOnlyAdapter:
    def __init__(self):
        self.calls: list[str] = []

    def get_server_time(self):
        self.calls.append("get_server_time")
        return {"status": 200, "iso": "2026-07-11T12:00:00Z"}

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {
            "accounts": [
                {
                    "uuid": "account-1",
                    "currency": "USD",
                    "available_balance": {"value": "100.00"},
                }
            ]
        }

    def get_balances(self):
        self.calls.append("get_balances")
        return [{"currency": "USD", "available_balance": {"value": "100.00"}}]

    def get_portfolios(self):
        self.calls.append("get_portfolios")
        return {"portfolios": [{"uuid": "portfolio-1", "portfolio_value": "100.00"}]}

    def get_products(self):
        self.calls.append("get_products")
        return {"products": [{"product_id": "BTC-USD"}, {"product_id": "ETH-USD"}]}

    def get_ticker(self, product_id="BTC-USD"):
        self.calls.append(f"get_ticker:{product_id}")
        return {"product_id": product_id, "price": "50000.00", "time": "2026-07-11T12:00:00Z"}


class FailingCoinbaseAdapter:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def get_server_time(self):
        self.calls += 1
        raise self.exc


class Http503(RuntimeError):
    status_code = 503


def _phase156a_green(_broker: str, **_kwargs):
    return {
        "broker": "COINBASE",
        "overall": "GREEN",
        "credentials": "PASS",
        "bootstrap": "PASS",
        "authentication": "PASS",
        "account": "PASS",
        "market_data": "PASS",
        "execution_firewall": "PASS",
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "blocker_reasons": [],
    }


def test_phase165b_validates_coinbase_key_pem_jwt_signature_and_permissions():
    report = validate_coinbase_credential_material(_env())

    assert report["status"] == "PASS"
    assert report["api_key_format_valid"] is True
    assert report["pem_valid"] is True
    assert report["ec_private_key"] is True
    assert report["jwt_generated"] is True
    assert report["signature_status"] == "PASS"
    assert report["permissions"]["status"] == "PASS"
    assert report["execution_allowed"] is False


def test_phase165b_invalid_credentials_fail_before_adapter_reads():
    adapter = FailingCoinbaseAdapter(AssertionError("adapter should not be called"))
    trace = trace_coinbase_authentication(
        adapter,
        env=_env(COINBASE_CDP_PRIVATE_KEY="not a pem"),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert "coinbase_private_key_pem_invalid" in trace["blockers"]
    assert adapter.calls == 0
    assert trace["endpoint_verification"]["accounts"]["coinbase_error_code"] == "NOT_ATTEMPTED"
    assert trace["execution_allowed"] is False


def test_phase165c_endpoint_mismatch_reports_precise_failure():
    trace = trace_coinbase_authentication(
        FakeCoinbaseReadOnlyAdapter(),
        env=_env(COINBASE_BASE_URL="https://api-public.sandbox.exchange.coinbase.com"),
        mode="live",
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert "coinbase_endpoint_mode_mismatch" in trace["blockers"]
    assert trace["endpoint_alignment"]["sandbox_live_mismatch"] is True
    assert trace["failure_stage"] == "coinbase_endpoint_mode_mismatch"


def test_phase165_live_test_order_environment_contamination_fails_closed():
    trace = trace_coinbase_authentication(
        FakeCoinbaseReadOnlyAdapter(),
        env=_env(COINBASE_TEST_ORDER_USD="1.00"),
        mode="live",
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert trace["environment"]["status"] == "FAIL"
    assert trace["environment"]["contamination_keys"] == ["COINBASE_TEST_ORDER_USD"]
    assert "COINBASE_TEST_ORDER_USD" in trace["blockers"]
    assert trace["execution_allowed"] is False


def test_phase165a_replaces_generic_broker_unavailable_with_http_trace():
    trace = trace_coinbase_authentication(
        FailingCoinbaseAdapter(Http503("Service Unavailable")),
        env=_env(),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert trace["coinbase_error_code"] == "COINBASE_HTTP_503"
    assert trace["failure_stage"] == "authentication"
    assert "BROKER_UNAVAILABLE" not in str(trace)


def test_phase165d_e_successful_read_only_connectivity_certificate():
    adapter = FakeCoinbaseReadOnlyAdapter()
    certificate = certify_coinbase_read_only_connectivity(adapter, env=_env())

    assert certificate["credential_validation"] == "PASS"
    assert certificate["authentication"] == "PASS"
    assert certificate["account_access"] == "PASS"
    assert certificate["balances"] == "PASS"
    assert certificate["portfolio_information"] == "PASS"
    assert certificate["products"] == "PASS"
    assert certificate["products_loaded"] > 0
    assert certificate["market_data"] == "PASS"
    assert certificate["execution_authority"] == "BLOCKED"
    assert certificate["read_only_certification"] == "PASS"
    assert certificate["execution_allowed"] is False
    assert certificate["live_trading_blocked"] is True
    assert certificate["broker_execution_armed"] is False
    assert not any("order" in call.lower() for call in adapter.calls)


def test_phase165_trace_is_embedded_in_phase156b_coinbase_authentication(monkeypatch):
    monkeypatch.delenv("COINBASE_TEST_ORDER_USD", raising=False)
    monkeypatch.delenv("COINBASE_PRACTICE_ORDER_USD", raising=False)

    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: FakeCoinbaseReadOnlyAdapter(),
    )

    auth = report["stage_results"]["authentication"]
    trace = auth["details"]["coinbase_authentication_trace"]
    assert report["authentication"] == "PASS"
    assert trace["authentication"] == "PASS"
    assert trace["endpoint_verification"]["accounts"]["status"] == "PASS"
    assert report["execution_allowed"] is False
    assert report["broker_execution_armed"] is False
