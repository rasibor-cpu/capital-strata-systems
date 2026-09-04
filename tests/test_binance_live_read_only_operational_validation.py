from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from backend.app.brokers.binance_live_read_only_adapter import (
    SOURCE_BINANCE_LIVE_READ_ONLY,
    BinanceLiveReadOnlyAdapter,
)
from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy
from backend.runtime.binance_live_read_only_operational_validation import (
    FAILURE_REASONS,
    BinanceLiveReadOnlyOperationalValidator,
    validate_binance_live_read_only_operational,
)
from tests.test_binance_live_read_only_adapter import (
    API_SECRET,
    FakeResponse,
    RecordingTransport,
    _adapter,
)


NOW = datetime(2026, 9, 4, 22, 0, tzinfo=timezone.utc)


def _fresh_millis(now: datetime = NOW) -> int:
    return int(now.timestamp() * 1000)


def _success_handler(now: datetime = NOW, *, extra_account=None):
    def handler(call):
        url = call["url"]
        if url.endswith("/api/v3/time"):
            return FakeResponse({"serverTime": _fresh_millis(now)})
        if url.endswith("/api/v3/account"):
            payload = {
                "accountType": "SPOT",
                "uid": 99,
                "balances": [
                    {"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
                    {"asset": "USDT", "free": "25.5", "locked": "1.5"},
                ],
            }
            if extra_account:
                payload.update(extra_account)
            return FakeResponse(payload)
        if url.endswith("/api/v3/exchangeInfo"):
            return FakeResponse(
                {"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"}]}
            )
        if url.endswith("/api/v3/ticker/price"):
            return FakeResponse({"symbol": "BTCUSDT", "price": "65000"})
        raise AssertionError(url)

    return handler


def _validate(transport, *, now=NOW, policy=None, artifacts_dir=None, adapter=None):
    built = adapter or _adapter(transport)
    built._now = lambda: now
    return validate_binance_live_read_only_operational(
        adapter_factory=lambda: built,
        artifacts_dir=artifacts_dir,
        now=lambda: now,
        policy=policy,
    )


def test_missing_credentials_fail_closed_before_network(tmp_path) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1}))
    result = validate_binance_live_read_only_operational(
        adapter_factory=lambda: BinanceLiveReadOnlyAdapter(env={}, transport=transport, now=lambda: NOW),
        artifacts_dir=tmp_path,
        now=lambda: NOW,
    )
    assert result["validation_status"] == "FAIL_CLOSED"
    assert result["failure_reasons"][0]["reason"] == "MISSING_CREDENTIALS"
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True
    assert transport.calls == []
    assert (tmp_path / "broker_validation.json").exists()


def test_successful_validation_parses_balances_not_positions(tmp_path) -> None:
    transport = RecordingTransport(_success_handler())
    result = _validate(transport, artifacts_dir=tmp_path)
    assert result["validation_status"] == "PASS"
    assert result["api_reachable"] is True
    assert result["authenticated"] is True
    assert result["account_loaded"] is True
    assert result["balances_loaded"] is True
    assert result["products_loaded"] == 1
    assert result["market_data_loaded"] is True
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True
    assert result["open_positions_availability"] == "UNAVAILABLE"
    assert result["session_pnl_availability"] == "UNAVAILABLE"
    assert result["maturity_availability"] == "UNAVAILABLE"
    rows = result["broker_validation"]["account_asset_balances"]
    assert result["broker_validation"]["section_label"] == "Account Asset Balances"
    assert {row["asset"] for row in rows} == {"BTC", "USDT"}
    btc = next(row for row in rows if row["asset"] == "BTC")
    assert btc["available_quantity"] == 0.0
    assert btc["held_quantity"] == 0.0
    assert btc["provenance"] == SOURCE_BINANCE_LIVE_READ_ONLY
    assert btc["market_value"] is None
    assert result["broker_validation"]["open_positions_availability"] == "UNAVAILABLE"
    assert "open_positions" not in result["broker_validation"]
    assert all(call["method"] == "GET" for call in transport.calls)


def test_authentication_network_and_malformed_fail_closed() -> None:
    auth = RecordingTransport(lambda call: FakeResponse({"code": -2015, "msg": "Invalid API-key"}, 401))
    auth_result = _validate(auth)
    assert auth_result["validation_status"] == "FAIL_CLOSED"
    assert any(item["reason"] == "AUTH_FAILED" for item in auth_result["failure_reasons"])
    assert auth_result["execution_allowed"] is False

    def network(_call):
        raise ConnectionError("connection refused")

    net_result = _validate(RecordingTransport(network))
    assert net_result["validation_status"] == "FAIL_CLOSED"
    assert any(item["reason"] == "NETWORK_ERROR" for item in net_result["failure_reasons"])

    def malformed(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": _fresh_millis()})
        return FakeResponse({"not": "account"})

    bad = _validate(RecordingTransport(malformed))
    assert bad["validation_status"] == "FAIL_CLOSED"
    assert {item["reason"] for item in bad["failure_reasons"]} <= set(FAILURE_REASONS)


def test_stale_future_and_malformed_timestamps_fail_closed() -> None:
    max_age = float(gate_config(load_freshness_policy(), "broker_snapshot")["max_age_seconds"])

    def stale(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": int((NOW - timedelta(seconds=max_age + 5)).timestamp() * 1000)})
        return _success_handler()(call)

    stale_result = _validate(RecordingTransport(stale))
    assert stale_result["validation_status"] == "FAIL_CLOSED"
    assert any(item["reason"] == "STALE_TIMESTAMP" for item in stale_result["failure_reasons"])

    def future(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": int((NOW + timedelta(hours=1)).timestamp() * 1000)})
        return _success_handler()(call)

    future_result = _validate(RecordingTransport(future))
    assert future_result["validation_status"] == "FAIL_CLOSED"
    assert any(item["reason"] == "FUTURE_TIMESTAMP" for item in future_result["failure_reasons"])

    def malformed(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": "not-a-time"})
        return _success_handler()(call)

    malformed_result = _validate(RecordingTransport(malformed))
    assert malformed_result["validation_status"] == "FAIL_CLOSED"
    assert any(
        item["reason"] in {"MALFORMED_TIMESTAMP", "API_ERROR"}
        for item in malformed_result["failure_reasons"]
    )


def test_freshness_uses_injected_canonical_policy() -> None:
    policy = {"gates": {"broker_snapshot": {"max_age_seconds": 90}}}

    def exact(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": int((NOW - timedelta(seconds=90)).timestamp() * 1000)})
        return _success_handler()(call)

    def stale(call):
        if call["url"].endswith("/api/v3/time"):
            return FakeResponse({"serverTime": int((NOW - timedelta(seconds=91)).timestamp() * 1000)})
        return _success_handler()(call)

    assert _validate(RecordingTransport(exact), policy=policy)["validation_status"] == "PASS"
    stale_result = _validate(RecordingTransport(stale), policy=policy)
    assert stale_result["validation_status"] == "FAIL_CLOSED"
    assert any(item["reason"] == "STALE_TIMESTAMP" for item in stale_result["failure_reasons"])


def test_artifacts_redact_secrets_and_keep_safety_flags(tmp_path) -> None:
    transport = RecordingTransport(_success_handler())
    result = _validate(transport, artifacts_dir=tmp_path)
    dumped = json.dumps(result)
    assert API_SECRET not in dumped
    assert "test-binance-api-key" not in dumped
    for name in ("broker_validation.json", "broker_health.json", "broker_market_snapshot.json"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert API_SECRET not in text
        assert "X-MBX-APIKEY" not in text
        payload = json.loads(text)
        assert payload.get("execution_allowed", False) in {False, None} or name != "broker_validation.json"
    assert result["broker_validation"]["execution_allowed"] is False
    assert result["broker_health"]["live_trading_blocked"] is True
    assert result["broker_health"]["broker_execution_armed"] is False
    assert result["broker_health"]["advisory_only"] is True


def test_balances_are_never_relabeled_as_positions() -> None:
    result = _validate(RecordingTransport(_success_handler()))
    blob = json.dumps(result).lower()
    assert "account asset balances" in blob
    assert result["broker_validation"]["section_label"] != "Open Positions"
    assert "open positions" not in result["broker_validation"]["section_label"].lower()
    assert result["open_positions_availability"] == "UNAVAILABLE"
    for row in result["broker_validation"]["account_asset_balances"]:
        assert "position" not in row
        assert row["market_value_availability"] == "UNAVAILABLE"


def test_security_error_skips_broker_reads(tmp_path) -> None:
    transport = RecordingTransport(_success_handler())
    adapter = _adapter(transport)
    validator = BinanceLiveReadOnlyOperationalValidator(
        adapter_factory=lambda: adapter,
        artifacts_dir=tmp_path,
        now=lambda: NOW,
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
    assert result["read_checks"]["server_time"] == "NOT_ATTEMPTED"
    assert result["read_checks"]["account_retrieval"] == "NOT_ATTEMPTED"
    assert transport.calls == []
    assert result["execution_allowed"] is False
