"""R8 — Questrade LIVE READ-ONLY activation. Injected transports only."""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from backend.brokers.questrade.contracts import map_balances, map_positions
from backend.brokers.questrade.dpapi_refresh_token_store import WindowsDpapiRefreshTokenStore
from backend.brokers.questrade.errors import TokenStoreError, WriteMethodBlockedError
from backend.brokers.questrade.get_only_transport import QuestradeGetOnlyHttpTransport
from backend.brokers.questrade.live_readonly_activation import compose_questrade_live_read_only_activation
from backend.brokers.questrade.oauth_refresh import (
    QUESTRADE_TOKEN_URL,
    QuestradeBoundedOAuthRefresh,
    QuestradeOAuthHttpResponse,
)
from backend.brokers.questrade.readonly_client import QuestradeHttpResponse, QuestradeReadOnlyClient
from backend.brokers.questrade.token_lifecycle import (
    InMemoryRefreshTokenStore,
    QuestradeTokenBundle,
    TokenLifecycle,
)
from backend.runtime.canonical_broker_portfolio import (
    EXPOSURE_HOLDING,
    EXPOSURE_POSITION,
    apply_canonical_broker_portfolio_bridge,
)


NOW = datetime(2026, 9, 5, 0, 10, tzinfo=timezone.utc)
SYNTHETIC_REFRESH = "SYNTHETIC_QT_REFRESH_TOKEN_ALPHA"
SYNTHETIC_REFRESH_ROTATED = "SYNTHETIC_QT_REFRESH_TOKEN_BETA"
SYNTHETIC_ACCESS = "SYNTHETIC_QT_ACCESS_TOKEN_GAMMA"
VALID_API_SERVER = "https://api01.iq.questrade.com/"
ACCOUNT_REF = "acct-primary"


class _NetworkGuard:
    def __init__(self) -> None:
        self.attempts: list[object] = []
        self._connect = socket.socket.connect
        self._create = socket.create_connection

    def __enter__(self) -> "_NetworkGuard":
        guard = self

        def connect(self_sock, address, *args, **kwargs):
            guard.attempts.append(address)
            raise OSError("external network blocked")

        def create_connection(address, *args, **kwargs):
            guard.attempts.append(address)
            raise OSError("external network blocked")

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.create_connection = create_connection  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        socket.socket.connect = self._connect  # type: ignore[method-assign]
        socket.create_connection = self._create  # type: ignore[assignment]


class _FakeDpapi:
    def __init__(self, *, fail_decrypt: bool = False) -> None:
        self.fail_decrypt = fail_decrypt
        self.encrypt_calls = 0

    def encrypt(self, plaintext: str) -> bytes:
        self.encrypt_calls += 1
        return b"CIPHER:" + plaintext.encode("utf-8")

    def decrypt(self, ciphertext: bytes) -> str:
        if self.fail_decrypt:
            raise RuntimeError("decrypt boom")
        prefix = b"CIPHER:"
        if not ciphertext.startswith(prefix):
            raise RuntimeError("bad ciphertext")
        return ciphertext[len(prefix) :].decode("utf-8")


class _FakeOAuth:
    def __init__(self, payload: Mapping[str, Any] | None = None, status_code: int = 200) -> None:
        self.calls: list[dict[str, Any]] = []
        self.payload = dict(payload or _valid_oauth_payload())
        self.status_code = status_code

    def post_form(self, **request: Any) -> QuestradeOAuthHttpResponse:
        self.calls.append(request)
        return QuestradeOAuthHttpResponse(status_code=self.status_code, payload=self.payload)


class _FakeGet:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send(self, **request: Any) -> QuestradeHttpResponse:
        self.calls.append(request)
        path = str(request.get("url") or "")
        if path.endswith("/accounts"):
            return QuestradeHttpResponse(200, {"accounts": [{"number": ACCOUNT_REF, "type": "Margin", "status": "Active"}]})
        if path.endswith("/balances"):
            return QuestradeHttpResponse(
                200,
                {
                    "perCurrencyBalances": [
                        {
                            "currency": "CAD",
                            "cash": 0.0,
                            "totalEquity": 250.0,
                            "buyingPower": 100.0,
                            "availableCash": 0.0,
                            "marketValue": 250.0,
                        }
                    ]
                },
            )
        if path.endswith("/positions"):
            return QuestradeHttpResponse(
                200,
                {
                    "positions": [
                        {
                            "symbol": "SHOP",
                            "securityType": "Stock",
                            "currentQuantity": 5,
                            "currentMarketValue": 200.0,
                            "openPnl": 12.0,
                            "currency": "CAD",
                        },
                        {
                            "symbol": "SHOP21JAN26C100",
                            "securityType": "Option",
                            "currentQuantity": 1,
                            "expiryDate": "2026-01-21",
                            "strikePrice": 100.0,
                            "optionType": "Call",
                            "currentMarketValue": 50.0,
                            "openPnl": -3.0,
                            "currency": "CAD",
                        },
                    ]
                },
            )
        return QuestradeHttpResponse(404, {"message": "unexpected"})


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_: Any) -> Any:
        self.calls.append((method, url))

        class _Resp:
            status_code = 200
            content = b'{"ok":true}'
            headers = {"X-RateLimit-Remaining": "8"}

        return _Resp()


def _valid_oauth_payload() -> dict[str, Any]:
    return {
        "access_token": SYNTHETIC_ACCESS,
        "refresh_token": SYNTHETIC_REFRESH_ROTATED,
        "expires_in": 1800,
        "api_server": VALID_API_SERVER,
    }


def _seed_store(path: Path, backend: _FakeDpapi, token: str = SYNTHETIC_REFRESH) -> WindowsDpapiRefreshTokenStore:
    store = WindowsDpapiRefreshTokenStore(path, protect_backend=backend, now=NOW)
    store.save_refresh_token(token)
    return store


def _assert_no_secrets(*values: Any) -> None:
    blob = " ".join(repr(value) for value in values)
    for secret in (SYNTHETIC_REFRESH, SYNTHETIC_REFRESH_ROTATED, SYNTHETIC_ACCESS):
        assert secret not in blob


def _activated(tmp_path: Path, **overrides: Any):
    path = tmp_path / "questrade_refresh_token.dpapi"
    backend = overrides.pop("protect_backend", _FakeDpapi())
    _seed_store(path, backend)
    options = {
        "refresh_token_store_path": path,
        "account_reference": ACCOUNT_REF,
        "activation_authorized": True,
        "protect_backend": backend,
        "oauth_transport": _FakeOAuth(),
        "http_transport": _FakeGet(),
        "now": NOW,
    }
    options.update(overrides)
    return compose_questrade_live_read_only_activation(**options)


def test_1_dpapi_store_load(tmp_path: Path) -> None:
    with _NetworkGuard() as guard:
        path = tmp_path / "questrade_refresh_token.dpapi"
        backend = _FakeDpapi()
        store = _seed_store(path, backend)
        assert store.load() == SYNTHETIC_REFRESH
        meta = store.metadata()
        assert meta["token_present"] is True
        assert meta["provider"] == "WINDOWS_DPAPI"
        assert meta["token_values_returned"] is False
        assert SYNTHETIC_REFRESH not in repr(store)
        assert SYNTHETIC_REFRESH not in str(meta)
    assert guard.attempts == []


def test_2_missing_dpapi_token_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "missing.dpapi"
    store = WindowsDpapiRefreshTokenStore(path, protect_backend=_FakeDpapi(), now=NOW)
    with pytest.raises(TokenStoreError) as exc:
        store.load()
    assert exc.value.code == "QUESTRADE_TOKEN_FILE_MISSING"


def test_3_decryption_failure_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    path.write_bytes(b"not-valid-ciphertext")
    store = WindowsDpapiRefreshTokenStore(path, protect_backend=_FakeDpapi(), now=NOW)
    with pytest.raises(TokenStoreError) as exc:
        store.load()
    assert exc.value.code == "QUESTRADE_TOKEN_DECRYPTION_FAILED"
    _assert_no_secrets(exc.value)


def test_4_atomic_rotated_token_replacement(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    backend = _FakeDpapi()
    store = _seed_store(path, backend)
    original = path.read_bytes()
    store.replace(
        QuestradeTokenBundle(
            access_token=SYNTHETIC_ACCESS,
            refresh_token=SYNTHETIC_REFRESH_ROTATED,
            api_server=VALID_API_SERVER,
            expires_at=NOW,
            acquired_at=NOW,
        )
    )
    assert store.load() == SYNTHETIC_REFRESH_ROTATED
    assert path.read_bytes() != original
    assert SYNTHETIC_ACCESS.encode() not in path.read_bytes()
    assert not (tmp_path / "questrade_refresh_token.dpapi.tmp").exists()
    assert store.metadata()["last_rotation_timestamp"] == NOW.isoformat()


def test_5_oauth_refresh_uses_post_only(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    store = _seed_store(path, _FakeDpapi())
    transport = _FakeOAuth()
    result = QuestradeBoundedOAuthRefresh(store, transport=transport, now=NOW).refresh()
    assert result["success"] is True
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == QUESTRADE_TOKEN_URL
    assert call["allow_redirects"] is False
    assert call["data"]["grant_type"] == "refresh_token"
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert "GET" not in str(call.get("method") or "POST")


def test_6_oauth_response_validation(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    store = _seed_store(path, _FakeDpapi())
    transport = _FakeOAuth({"access_token": SYNTHETIC_ACCESS, "expires_in": 1800, "api_server": VALID_API_SERVER})
    result = QuestradeBoundedOAuthRefresh(store, transport=transport, now=NOW).refresh()
    assert result["success"] is False
    assert result["reason"] == "QUESTRADE_OAUTH_RESPONSE_INVALID"
    _assert_no_secrets(result)


def test_7_rejected_untrusted_api_server(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    store = _seed_store(path, _FakeDpapi())
    transport = _FakeOAuth(
        {
            "access_token": SYNTHETIC_ACCESS,
            "refresh_token": SYNTHETIC_REFRESH_ROTATED,
            "expires_in": 1800,
            "api_server": "https://evil.example.com/",
        }
    )
    result = QuestradeBoundedOAuthRefresh(store, transport=transport, now=NOW).refresh()
    assert result["success"] is False
    assert "API_SERVER" in str(result["reason"])
    _assert_no_secrets(result)


def test_8_access_token_is_memory_only(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    backend = _FakeDpapi()
    store = _seed_store(path, backend)
    refresher = QuestradeBoundedOAuthRefresh(store, transport=_FakeOAuth(), now=NOW)
    result = refresher.refresh()
    assert result["success"] is True
    assert result["access_token_persisted"] is False
    assert result["access_token_memory_only"] is True
    persisted = store.load()
    assert persisted == SYNTHETIC_REFRESH_ROTATED
    assert SYNTHETIC_ACCESS not in persisted
    assert SYNTHETIC_ACCESS.encode() not in path.read_bytes()
    assert "access_token" not in result


def test_9_no_token_leakage_in_repr_result_or_error(tmp_path: Path) -> None:
    path = tmp_path / "questrade_refresh_token.dpapi"
    activation = _activated(tmp_path)
    payload = activation.as_dict()
    _assert_no_secrets(activation, payload, payload.get("token_store"), payload.get("metadata"))
    store = WindowsDpapiRefreshTokenStore(path, protect_backend=_FakeDpapi(fail_decrypt=True), now=NOW)
    path.write_bytes(b"CIPHER:not-used")
    with pytest.raises(TokenStoreError) as exc:
        store.load()
    _assert_no_secrets(exc.value, repr(exc.value))


def test_10_get_only_transport_accepts_get() -> None:
    session = _RecordingSession()
    transport = QuestradeGetOnlyHttpTransport(session=session)
    response = transport.send(
        method="GET",
        url="https://api01.iq.questrade.com/v1/accounts",
        headers={"Authorization": f"Bearer {SYNTHETIC_ACCESS}"},
        params={},
        timeout_seconds=5,
    )
    assert response.status_code == 200
    assert response.payload == {"ok": True}
    assert "Authorization" not in response.headers
    assert session.calls == [("GET", "https://api01.iq.questrade.com/v1/accounts")]


def test_11_write_methods_rejected_before_dispatch() -> None:
    session = _RecordingSession()
    transport = QuestradeGetOnlyHttpTransport(session=session)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(WriteMethodBlockedError):
            transport.send(
                method=method,
                url="https://api01.iq.questrade.com/v1/accounts",
                headers={"Authorization": f"Bearer {SYNTHETIC_ACCESS}"},
                params={},
                timeout_seconds=5,
            )
    assert session.calls == []


def test_12_endpoint_path_allowlist_remains_enforced() -> None:
    tokens = TokenLifecycle(InMemoryRefreshTokenStore(), now=NOW)
    tokens.record_external_token_response(
        {
            "access_token": SYNTHETIC_ACCESS,
            "refresh_token": SYNTHETIC_REFRESH,
            "api_server": VALID_API_SERVER,
            "expires_in": 1800,
        },
        allow_record=True,
    )
    transport = _FakeGet()
    client = QuestradeReadOnlyClient(tokens, transport=transport)
    blocked = client.request("/orders", method="GET")
    assert blocked.success is False
    assert blocked.failure_code == "QUESTRADE_PATH_NOT_ALLOWLISTED"
    write = client.request("/accounts", method="POST")
    assert write.success is False
    assert write.failure_code == "QUESTRADE_WRITE_METHOD_BLOCKED"
    assert transport.calls == []


def test_13_accounts_provider_mapping(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    payload = activation.provider.fetch("ACCOUNTS", authorization=memoryview(b"lease"), parameters={})
    assert payload["accounts"][0]["type"] == "Margin"


def test_14_balances_provider_mapping(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    payload = activation.provider.fetch(
        "BALANCES",
        authorization=memoryview(b"lease"),
        parameters={"account_reference": ACCOUNT_REF},
    )
    assert payload["perCurrencyBalances"][0]["cash"] == 0.0
    assert payload["perCurrencyBalances"][0]["totalEquity"] == 250.0


def test_15_positions_provider_mapping(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    payload = activation.provider.fetch(
        "POSITIONS",
        authorization=memoryview(b"lease"),
        parameters={"account_reference": ACCOUNT_REF},
    )
    symbols = {row["symbol"] for row in payload["positions"]}
    assert symbols == {"SHOP", "SHOP21JAN26C100"}


def test_16_unsupported_dataset_fails_closed(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    with pytest.raises(Exception) as exc:
        activation.provider.fetch("ORDERS", authorization=memoryview(b"lease"), parameters={})
    blob = f"{getattr(exc.value, 'code', '')} {exc.value}"
    assert "UNSUPPORTED" in blob


def test_17_missing_account_reference_fails_closed(tmp_path: Path) -> None:
    activation = _activated(tmp_path, account_reference=None)
    with pytest.raises(Exception) as exc:
        activation.provider.fetch("BALANCES", authorization=memoryview(b"lease"), parameters={})
    blob = f"{getattr(exc.value, 'code', '')} {exc.value}"
    assert "ACCOUNT_REFERENCE" in blob


def test_18_zero_survives_normalization(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    raw = activation.provider.fetch(
        "BALANCES",
        authorization=memoryview(b"lease"),
        parameters={"account_reference": ACCOUNT_REF},
    )
    mapped = map_balances(raw, account_type="MARGIN", generated_at=NOW.isoformat())
    assert mapped["balances"][0]["cash"] == 0.0
    assert mapped["balances"][0]["available_cash"] == 0.0
    bridged = apply_canonical_broker_portfolio_bridge(
        {
            "selected_broker": "QUESTRADE",
            "questrade_read_only": {
                "status": "HOLDINGS_READY",
                "timestamp": NOW.isoformat(),
                "provider_timestamp": NOW.isoformat(),
                "balances": mapped["balances"],
                "holdings": [],
                "option_positions": [],
            },
        },
        now=NOW,
    )
    assert bridged["canonical_broker_portfolio"]["metrics"]["cash"]["value"] == 0.0
    assert bridged["canonical_broker_portfolio"]["metrics"]["cash"]["availability"] == "AVAILABLE"


def test_19_option_expiry_survives_when_supplied(tmp_path: Path) -> None:
    activation = _activated(tmp_path)
    raw = activation.provider.fetch(
        "POSITIONS",
        authorization=memoryview(b"lease"),
        parameters={"account_reference": ACCOUNT_REF},
    )
    mapped = map_positions(raw, generated_at=NOW.isoformat())
    option = mapped["option_positions"][0]
    assert option["expiry"] == "2026-01-21"
    holding = mapped["holdings"][0]
    assert holding.get("expiry") in (None, "")
    bridged = apply_canonical_broker_portfolio_bridge(
        {
            "selected_broker": "QUESTRADE",
            "questrade_read_only": {
                "status": "HOLDINGS_READY",
                "timestamp": NOW.isoformat(),
                "provider_timestamp": NOW.isoformat(),
                "balances": [{"currency": "CAD", "cash": 0.0, "equity": 250.0, "buying_power": 100.0}],
                "holdings": mapped["holdings"],
                "option_positions": mapped["option_positions"],
            },
        },
        now=NOW,
    )
    exposures = bridged["canonical_broker_portfolio"]["exposures"]
    option_row = next(row for row in exposures if row["exposure_kind"] == EXPOSURE_POSITION)
    holding_row = next(row for row in exposures if row["exposure_kind"] == EXPOSURE_HOLDING)
    assert option_row["maturity"] == "2026-01-21"
    assert holding_row["maturity_availability"] == "UNAVAILABLE"


def test_20_21_22_execution_remains_fail_closed(tmp_path: Path) -> None:
    disabled = compose_questrade_live_read_only_activation(activation_authorized=False)
    enabled = _activated(tmp_path)
    for payload in (disabled.as_dict(), enabled.as_dict()):
        assert payload["execution_allowed"] is False
        assert payload["live_trading_blocked"] is True
        assert payload["broker_execution_armed"] is False
        assert payload["advisory_only"] is True
    assert enabled.provider.execution_allowed is False
    assert enabled.provider.live_trading_blocked is True
    assert enabled.provider.broker_execution_armed is False


def test_23_no_network_when_activation_disabled(tmp_path: Path) -> None:
    oauth = _FakeOAuth()
    http = _FakeGet()
    with _NetworkGuard() as guard:
        result = compose_questrade_live_read_only_activation(
            refresh_token_store_path=tmp_path / "questrade_refresh_token.dpapi",
            account_reference=ACCOUNT_REF,
            activation_authorized=False,
            protect_backend=_FakeDpapi(),
            oauth_transport=oauth,
            http_transport=http,
            now=NOW,
        )
        payload = result.as_dict()
        assert payload["activated"] is False
        assert payload["status"] == "DISABLED"
        assert payload["network_call_performed"] is False
        assert oauth.calls == []
        assert http.calls == []
    assert guard.attempts == []


def test_24_no_real_network_calls_in_suite(tmp_path: Path) -> None:
    with _NetworkGuard() as guard:
        _activated(tmp_path)
        compose_questrade_live_read_only_activation(activation_authorized=False)
        QuestradeGetOnlyHttpTransport(session=_RecordingSession()).send(
            method="GET",
            url="https://api01.iq.questrade.com/v1/accounts",
            headers={"Authorization": "Bearer synthetic"},
            params={},
            timeout_seconds=1,
        )
    assert guard.attempts == []


def test_non_windows_without_backend_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.brokers.questrade.dpapi_refresh_token_store.sys.platform", "linux")
    with pytest.raises(TokenStoreError) as exc:
        WindowsDpapiRefreshTokenStore(tmp_path / "token.dpapi")
    assert exc.value.code == "WINDOWS_DPAPI_REQUIRED"


def test_repository_relative_secret_path_rejected() -> None:
    with pytest.raises(Exception) as exc:
        WindowsDpapiRefreshTokenStore("secrets/questrade_refresh_token.dpapi", protect_backend=_FakeDpapi())
    assert "ABSOLUTE" in str(getattr(exc.value, "code", exc.value)) or "ABSOLUTE" in str(exc.value)


def test_25_production_oauth_transport_preserves_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error
    import urllib.request

    class _HttpErrorOpener:
        def open(self, request: Any, timeout: float) -> Any:
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"error":"invalid_grant"}'),
            )

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: _HttpErrorOpener())
    from backend.brokers.questrade.oauth_refresh import QuestradeOAuthFormTransportImpl
    response = QuestradeOAuthFormTransportImpl().post_form(
        url=QUESTRADE_TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": SYNTHETIC_REFRESH},
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        timeout_seconds=10.0,
        allow_redirects=False,
    )
    assert response.status_code == 400
    assert response.payload == {"error": "invalid_grant"}


def test_26_http_401_reaches_oauth_authorization_classifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error
    import urllib.request

    class _UnauthorizedOpener:
        def open(self, request: Any, timeout: float) -> Any:
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"invalid_token"}'))

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: _UnauthorizedOpener())
    from backend.brokers.questrade.oauth_refresh import QuestradeOAuthFormTransportImpl
    store = _seed_store(tmp_path / "questrade_refresh_token.dpapi", _FakeDpapi())
    result = QuestradeBoundedOAuthRefresh(store, transport=QuestradeOAuthFormTransportImpl(), now=NOW).refresh()
    assert result["success"] is False
    assert result["reason"] == "QUESTRADE_AUTHORIZATION_REVOKED"
    assert result["oauth_refresh_attempted"] is True
    assert result["refresh_token_persisted"] is False
    _assert_no_secrets(result)
