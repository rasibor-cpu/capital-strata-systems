from __future__ import annotations

from datetime import datetime, timezone

from backend.runtime.coinbase_live_adapter import CoinbaseLiveReadOnlyAdapter
from backend.runtime.coinbase_live_read_only_operational_validation import (
    CoinbaseLiveReadOnlyOperationalValidator,
)


class FakeCoinbaseReadClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_time(self):
        self.calls.append("get_time")
        return {"iso": "2026-07-05T12:00:00Z"}

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {"accounts": [{"uuid": "acct", "available_balance": {"value": "100.00", "currency": "CAD"}}]}

    def get_portfolios(self):
        self.calls.append("get_portfolios")
        return {"portfolios": [{"uuid": "portfolio"}]}

    def get_products(self):
        self.calls.append("get_products")
        return {"products": [{"product_id": "BTC-USD"}]}

    def get_product_ticker(self, product_id: str):
        self.calls.append(f"get_product_ticker:{product_id}")
        return {"product_id": product_id, "price": "100000.00"}


def test_security_error_publishes_and_skips_broker_reads(tmp_path) -> None:
    client = FakeCoinbaseReadClient()
    adapter = CoinbaseLiveReadOnlyAdapter(
        env={
            "COINBASE_CDP_KEY_NAME": "organizations/test/apiKeys/test",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----redacted-----END PRIVATE KEY-----",
        },
        read_client=client,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )
    validator = CoinbaseLiveReadOnlyOperationalValidator(
        adapter_factory=lambda: adapter,
        artifacts_dir=tmp_path,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )
    validator._should_validate_startup_security = lambda: True  # type: ignore[method-assign]

    def _raise(*_args, **_kwargs):
        raise RuntimeError("startup security blocked")

    import backend.app.security.environment_validator as env_validator

    original = env_validator.validate_startup_security_environment
    env_validator.validate_startup_security_environment = _raise
    try:
        result = validator.validate()
    finally:
        env_validator.validate_startup_security_environment = original

    assert result["validation_status"] == "FAIL_CLOSED"
    assert result["failure_reasons"][0]["reason"] == "SECURITY_ERROR"
    assert result["execution_allowed"] is False
    assert result["read_checks"]["server_time"] == "NOT_ATTEMPTED"
    assert result["read_checks"]["account_retrieval"] == "NOT_ATTEMPTED"
    assert client.calls == []
    assert (tmp_path / "broker_validation.json").exists()
