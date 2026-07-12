from __future__ import annotations

import socket

from backend.runtime.live_connectivity_certifier import certify_live_connectivity
from backend.runtime.oanda_authentication_trace import (
    trace_oanda_authentication,
    validate_oanda_credential_material,
)
from backend.runtime.oanda_connectivity_certificate import (
    certify_oanda_read_only_connectivity,
    oanda_connectivity_certificate_json,
)


def _env(**overrides):
    data = {
        "OANDA_API_KEY": "test-token",
        "OANDA_ACCOUNT_ID": "001-001-1234567-001",
        "OANDA_ENV": "live",
        "OANDA_BASE_URL": "https://localhost",
    }
    data.update(overrides)
    return data


class FakeOandaReadOnlyAdapter:
    def __init__(self):
        self.calls: list[str] = []
        self.account_id = "redacted-test-account"

    def get_account_summary(self):
        self.calls.append("get_account_summary")
        return {
            "ok": True,
            "status": 200,
            "data": {
                "account": {
                    "id": "redacted-test-account",
                    "alias": "primary",
                    "currency": "USD",
                    "balance": "1000.00",
                    "NAV": "1001.00",
                    "marginAvailable": "900.00",
                }
            },
        }

    def get_open_trades(self):
        self.calls.append("get_open_trades")
        return {"ok": True, "status": 200, "data": {"trades": []}}

    def get_open_positions(self):
        self.calls.append("get_open_positions")
        return {"ok": True, "status": 200, "data": {"positions": []}}

    def _request_json(self, method, path, payload=None):
        self.calls.append(f"_request_json:{method}:{path}")
        assert method == "GET"
        assert payload is None
        if path.endswith("/instruments"):
            return {"ok": True, "status": 200, "data": {"instruments": [{"name": "EUR_USD"}, {"name": "USD_JPY"}]}}
        if "pricing?instruments=EUR_USD" in path:
            return {"ok": True, "status": 200, "data": {"prices": [{"instrument": "EUR_USD", "time": "2026-07-11T12:00:00Z"}]}}
        if path.endswith("/openTrades"):
            return {"ok": True, "status": 200, "data": {"trades": []}}
        if path.endswith("/openPositions"):
            return {"ok": True, "status": 200, "data": {"positions": []}}
        return {
            "ok": True,
            "status": 200,
            "data": {
                "account": {
                    "id": "redacted-test-account",
                    "alias": "primary",
                    "currency": "USD",
                    "balance": "1000.00",
                    "NAV": "1001.00",
                    "marginAvailable": "900.00",
                }
            },
        }

    def place_order(self, *_args, **_kwargs):
        raise AssertionError("orders must not be submitted by read-only certification")

    def close_trade(self, *_args, **_kwargs):
        raise AssertionError("trades must not be closed by read-only certification")

    def close_position(self, *_args, **_kwargs):
        raise AssertionError("positions must not be closed by read-only certification")


class MalformedAccountAdapter(FakeOandaReadOnlyAdapter):
    def get_account_summary(self):
        self.calls.append("get_account_summary")
        return {"ok": True, "status": 200, "data": {"account": {"id": "redacted-test-account"}}}

    def _request_json(self, method, path, payload=None):
        self.calls.append(f"_request_json:{method}:{path}")
        if path.endswith("/instruments"):
            return {"ok": True, "status": 200, "data": {"instruments": [{"name": "EUR_USD"}, {"name": "USD_JPY"}]}}
        if "pricing?instruments=EUR_USD" in path:
            return {"ok": True, "status": 200, "data": {"prices": [{"instrument": "EUR_USD", "time": "2026-07-11T12:00:00Z"}]}}
        if path.endswith("/openTrades"):
            return {"ok": True, "status": 200, "data": {"trades": []}}
        if path.endswith("/openPositions"):
            return {"ok": True, "status": 200, "data": {"positions": []}}
        return {"ok": True, "status": 200, "data": {"account": {"id": "redacted-test-account"}}}


class FailingOandaAdapter:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def get_account_summary(self):
        self.calls += 1
        raise self.exc


class HttpError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def _phase156a_green(_broker: str, **_kwargs):
    return {
        "broker": "OANDA",
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


def test_phase165b_validates_oanda_token_account_and_endpoint_pairing():
    report = validate_oanda_credential_material(_env())

    assert report["status"] == "PASS"
    assert report["token_present"] is True
    assert report["account_id_present"] is True
    assert report["token_account_pairing_structurally_valid"] is True
    assert report["endpoint_alignment"]["status"] == "PASS"
    assert report["execution_allowed"] is False


def test_phase165b_missing_token_fails_before_adapter_reads():
    adapter = FailingOandaAdapter(AssertionError("adapter should not be called"))
    trace = trace_oanda_authentication(
        adapter,
        env=_env(OANDA_API_KEY=""),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert "oanda_token_missing" in trace["blockers"]
    assert adapter.calls == 0
    assert trace["endpoint_verification"]["account_summary"]["oanda_error_code"] == "NOT_ATTEMPTED"
    assert trace["live_trading_blocked"] is True


def test_phase165b_missing_account_id_fails_closed():
    trace = trace_oanda_authentication(
        FailingOandaAdapter(AssertionError("adapter should not be called")),
        env=_env(OANDA_ACCOUNT_ID="", OANDA_LIVE_ACCOUNT_ID="", OANDA_PRACTICE_ACCOUNT_ID=""),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert "oanda_account_id_missing" in trace["blockers"]
    assert trace["execution_allowed"] is False


def test_phase165c_practice_live_mismatch_reports_precise_failure():
    trace = trace_oanda_authentication(
        FakeOandaReadOnlyAdapter(),
        env=_env(OANDA_BASE_URL="https://api-fxpractice.oanda.com"),
        mode="live",
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert "oanda_endpoint_mode_mismatch" in trace["blockers"]
    assert trace["endpoint_alignment"]["sandbox_live_mismatch"] is True
    assert trace["failure_stage"] == "oanda_endpoint_mode_mismatch"


def test_phase165a_replaces_generic_broker_unavailable_with_http_401_trace():
    trace = trace_oanda_authentication(
        FailingOandaAdapter(HttpError(401)),
        env=_env(),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert trace["oanda_error_code"] == "OANDA_HTTP_401"
    assert trace["failure_stage"] == "authentication"
    assert "BROKER_UNAVAILABLE" not in str(trace)


def test_phase165a_reports_http_403_404_and_429_without_generic_failure():
    for status in (403, 404, 429):
        trace = trace_oanda_authentication(
            FailingOandaAdapter(HttpError(status)),
            env=_env(),
            require_credentials=True,
        )
        assert trace["oanda_error_code"] == f"OANDA_HTTP_{status}"
        assert "BROKER_UNAVAILABLE" not in str(trace)


def test_phase165a_reports_timeout_stage():
    trace = trace_oanda_authentication(
        FailingOandaAdapter(socket.timeout("timed out")),
        env=_env(),
        require_credentials=True,
    )

    assert trace["authentication"] == "FAIL"
    assert trace["oanda_error_code"] == "OANDA_TIMEOUT"


def test_phase165d_malformed_account_response_blocks_certificate():
    certificate = certify_oanda_read_only_connectivity(MalformedAccountAdapter(), env=_env())

    assert certificate["authentication"] == "PASS"
    assert certificate["account_access"] == "PASS"
    assert certificate["balance_access"] == "FAIL"
    assert certificate["margin_access"] == "FAIL"
    assert certificate["read_only_certification"] == "FAIL"
    assert certificate["canonical_broker_state"] == "READ_ONLY_BLOCKED"
    assert certificate["health_color"] == "RED"


def test_phase165d_successful_oanda_read_only_connectivity_certificate():
    adapter = FakeOandaReadOnlyAdapter()
    certificate = certify_oanda_read_only_connectivity(adapter, env=_env())

    assert certificate["credential_validation"] == "PASS"
    assert certificate["authentication"] == "PASS"
    assert certificate["account_access"] == "PASS"
    assert certificate["balance_access"] == "PASS"
    assert certificate["nav_access"] == "PASS"
    assert certificate["margin_access"] == "PASS"
    assert certificate["instrument_access"] == "PASS"
    assert certificate["pricing_access"] == "PASS"
    assert certificate["open_trades_access"] == "PASS"
    assert certificate["open_positions_access"] == "PASS"
    assert certificate["execution_authority"] == "BLOCKED"
    assert certificate["canonical_broker_state"] == "READ_ONLY_CERTIFIED"
    assert certificate["read_only_certification"] == "PASS"
    assert certificate["execution_allowed"] is False
    assert certificate["live_trading_blocked"] is True
    assert certificate["broker_execution_armed"] is False
    assert not any("order" in call.lower() for call in adapter.calls)


def test_phase165d_latency_degradation_does_not_grant_or_block_read_only_certificate(monkeypatch):
    import backend.runtime.oanda_connectivity_certificate as oanda_certificate

    monkeypatch.setattr(oanda_certificate, "_latency_status", lambda _latency: "RED")
    certificate = certify_oanda_read_only_connectivity(FakeOandaReadOnlyAdapter(), env=_env())

    assert certificate["read_only_certification"] == "PASS"
    assert certificate["canonical_broker_state"] == "READ_ONLY_CERTIFIED"
    assert certificate["health_color"] == "AMBER"
    assert certificate["execution_allowed"] is False
    assert certificate["live_trading_blocked"] is True


def test_phase165e_oanda_certificate_json_report_generation():
    report = certify_oanda_read_only_connectivity(FakeOandaReadOnlyAdapter(), env=_env())
    payload = oanda_connectivity_certificate_json(report)

    assert '"broker": "OANDA"' in payload
    assert '"advisory_only": true' in payload
    assert "test-token" not in payload


def test_phase165_oanda_trace_is_embedded_in_phase156b_authentication(monkeypatch):
    import backend.runtime.oanda_authentication_trace as oanda_trace

    monkeypatch.setattr(oanda_trace, "load_credentials", lambda _broker, mode="live": _env())
    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: FakeOandaReadOnlyAdapter(),
    )

    auth = report["stage_results"]["authentication"]
    trace = auth["details"]["oanda_authentication_trace"]
    assert report["authentication"] == "PASS"
    assert trace["authentication"] == "PASS"
    assert trace["endpoint_verification"]["account_summary"]["status"] == "PASS"
    assert report["execution_allowed"] is False
    assert report["broker_execution_armed"] is False
