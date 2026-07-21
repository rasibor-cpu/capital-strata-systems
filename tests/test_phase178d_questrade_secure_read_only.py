"""Phase 178D — secure Questrade read-only connectivity foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry
from backend.app.brokers.operational_state import BrokerOperationalState
from backend.broker_reporting import build_broker_executive_report_package
from backend.brokers.questrade import (
    QuestradeTokenBundle,
    QuestradeAdvisoryAdapter,
    QuestradeReadOnlyClient,
    QuestradeSecureConfiguration,
    TokenLifecycle,
)
from backend.brokers.questrade.token_lifecycle import InMemoryRefreshTokenStore
from backend.brokers.questrade.contracts import account_restrictions
from backend.brokers.questrade.endpoint_security import validate_api_server
from backend.brokers.questrade.readonly_client import QuestradeHttpResponse
from backend.options.options_income_data_resolver import resolve_options_income_advisory_data
from backend.options.options_income_market_data_adapter import fetch_underlying_market_data
from backend.options.options_income_option_chain_adapter import fetch_option_chain
from backend.options.options_income_reporting import build_options_income_executive_report
from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials
from backend.runtime.broker_environment_profiles import build_broker_environment
from backend.runtime.runtime_mode import resolve_runtime_mode
from dashboard.mission_control.pages.broker_management import render as render_broker_management
from dashboard.mission_control.routes import create_mission_control_router
from dashboard.runtime.frontend_contract import broker as frontend_broker


TOKEN_RESPONSE = {
    "access_token": "test-access-token-not-a-real-credential",
    "refresh_token": "test-refresh-token-not-a-real-credential",
    "api_server": "https://api01.iq.questrade.com/",
    "expires_in": 1800,
}


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send(self, **request):
        self.calls.append(request)
        path = urlsplit(request["url"]).path.removeprefix("/v1")
        params = request["params"]
        if path == "/accounts":
            return QuestradeHttpResponse(
                200,
                {
                    "accounts": [
                        {"number": "11112222", "type": "TFSA", "status": "Active", "currency": "CAD"},
                        {"number": "33334444", "type": "Margin", "status": "Active", "currency": "CAD"},
                    ]
                },
            )
        if path.endswith("/balances"):
            return QuestradeHttpResponse(
                200,
                {
                    "perCurrencyBalances": [
                        {
                            "currency": "CAD",
                            "cash": 25000.0,
                            "totalEquity": 40000.0,
                            "marketValue": 15000.0,
                            "buyingPower": 50000.0,
                            "maintenanceExcess": 20000.0,
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
                            "symbol": "XIU.TO",
                            "securityType": "Stock",
                            "currentQuantity": 200,
                            "openQuantity": 200,
                            "averageEntryPrice": 30.0,
                            "currentPrice": 31.0,
                            "currentMarketValue": 6200.0,
                            "currency": "CAD",
                            "openPnl": 200.0,
                        },
                        {
                            "symbol": "XIU260116C00032000",
                            "securityType": "Option",
                            "currentQuantity": -1,
                            "expiryDate": "2026-01-16",
                            "strikePrice": 32.0,
                            "optionType": "Call",
                            "multiplier": 100,
                            "currency": "CAD",
                        },
                    ]
                },
            )
        if path == "/symbols":
            return QuestradeHttpResponse(
                200,
                {"symbols": [{"symbolId": 1, "symbol": "XIU.TO", "securityType": "Stock", "currency": "CAD"}]},
            )
        if path == "/symbols/1/options":
            return QuestradeHttpResponse(
                200,
                {
                    "optionChain": [
                        {
                            "expiryDate": "2026-01-16",
                            "chainPerRoot": [
                                {"chainPerStrikePrice": [{"strikePrice": 32.0, "callSymbolId": 101, "putSymbolId": 102}]}
                            ],
                        }
                    ]
                },
            )
        if path == "/markets/quotes":
            ids = str(params.get("ids") or "")
            symbol = "XIU.TO" if ids == "1" else "XIU260116C00032000"
            return QuestradeHttpResponse(
                200,
                {
                    "quotes": [
                        {
                            "symbolId": int(ids.split(",")[0]),
                            "symbol": symbol,
                            "bidPrice": 1.0,
                            "askPrice": 1.2,
                            "lastTradePrice": 1.1,
                            "volume": 10,
                            "currency": "CAD",
                        }
                    ]
                },
                {"X-RateLimit-Remaining": "10"},
            )
        if path == "/markets":
            return QuestradeHttpResponse(200, {"markets": [{"name": "TSX", "defaultTradingVenue": "AUTO"}]})
        if path.endswith("/activities"):
            return QuestradeHttpResponse(200, {"activities": []})
        return QuestradeHttpResponse(404, {})


def _configured_adapter() -> tuple[QuestradeAdvisoryAdapter, _FakeTransport]:
    tokens = TokenLifecycle(now=datetime(2026, 7, 20, tzinfo=timezone.utc))
    recorded = tokens.record_external_token_response(TOKEN_RESPONSE, allow_record=True)
    assert recorded["success"] is True
    transport = _FakeTransport()
    client = QuestradeReadOnlyClient(tokens, transport=transport, sleeper=lambda _: None)
    config = QuestradeSecureConfiguration(
        refresh_token_ref="vault:questrade/refresh",
        token_store_id="vault:questrade/tokens",
        secret_store_provider="WINDOWS_CREDENTIAL_MANAGER",
    )
    return QuestradeAdvisoryAdapter(token_lifecycle=tokens, configuration=config, client=client), transport


def test_configuration_presence_only_and_authorization_required() -> None:
    config = QuestradeSecureConfiguration(refresh_token_ref="vault:questrade/refresh")
    summary = config.sanitized_summary()
    assert summary["configuration_present"] is True
    assert "vault:questrade/refresh" not in str(summary)
    adapter = QuestradeAdvisoryAdapter(configuration=config, token_lifecycle=TokenLifecycle())
    assert adapter.readiness()["state"] == "AUTHORIZATION_REQUIRED"
    assert adapter.onboarding_status()["authorization_launch_enabled"] is False


def test_questrade_uses_its_own_canonical_credential_profile(tmp_path) -> None:
    env = {
        "CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_READ_ONLY",
        "QUESTRADE_TOKEN_STORE_ID": "test-token-store-reference",
        "QUESTRADE_ACCOUNT_HASH": "test-account-reference",
    }
    credentials = build_broker_environment(tmp_path, broker="QUESTRADE", env=env)
    assert credentials.broker == "QUESTRADE"
    assert credentials.key_identifier_present is True
    assert credentials.private_key_present is False
    assert credentials.account_identifier_present is True
    assert credentials.credential_source == "SECURE_REFERENCE_ENV"
    assert credentials.permissions_classification == "READ_ONLY"
    assert credentials.validation_status == "PASS"
    assert credentials.execution_allowed is False

    diagnostics = diagnose_broker_credentials("questrade", env=env)
    assert diagnostics.broker_name == "QUESTRADE"
    assert diagnostics.credentials_present is True
    assert diagnostics.key_identifier_present is True
    assert diagnostics.token_present is True
    assert diagnostics.account_present is True
    assert diagnostics.account_identifier_present is True
    assert diagnostics.authentication_attempted is False
    assert diagnostics.authenticated is False
    assert diagnostics.execution_allowed is False
    serialized = str(diagnostics.as_dict())
    assert "test-token-store-reference" not in serialized
    assert "test-account-reference" not in serialized


def test_existing_expired_quote_and_chain_are_stale() -> None:
    generated_at = "2026-07-20T22:00:00Z"
    expired_at = "2026-07-20T20:00:00Z"

    class _ExpiredQuote:
        def get_underlying_quote(self, symbol: str):
            return {"symbol": symbol, "bid": 10, "ask": 11, "last": 10.5, "timestamp": expired_at}

    class _ExpiredChain:
        def get_option_chain(self, underlying: str):
            return {
                "underlying_symbol": underlying,
                "calls": [{"strike": 10}],
                "puts": [{"strike": 10}],
                "expirations": ["2026-08-21"],
                "strikes": [10],
                "quote_timestamp": expired_at,
            }

    quote = fetch_underlying_market_data("XIU.TO", provider=_ExpiredQuote(), generated_at=generated_at)
    chain = fetch_option_chain("XIU.TO", provider=_ExpiredChain(), generated_at=generated_at)
    assert quote["status"] == "STALE"
    assert chain["status"] == "STALE"


def test_existing_broker_credential_mappings_remain_compatible() -> None:
    coinbase = diagnose_broker_credentials(
        "coinbase",
        env={"COINBASE_API_KEY": "test-key", "COINBASE_API_SECRET": "test-secret"},
    )
    assert coinbase.key_present is True
    assert coinbase.key_identifier_present is True

    oanda = diagnose_broker_credentials(
        "oanda",
        env={
            "OANDA_ACCESS_TOKEN": "test-token",
            "OANDA_ACCOUNT_ID": "test-account",
            "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
        },
    )
    assert oanda.token_present is True
    assert oanda.account_present is True
    assert oanda.account_identifier_present is True

    binance = diagnose_broker_credentials(
        "binance",
        env={"BINANCE_API_KEY": "test-key", "BINANCE_API_SECRET": "test-secret"},
    )
    assert binance.credentials_present is False


@pytest.mark.parametrize(
    "value",
    [
        "http://api01.iq.questrade.com/",
        "https://localhost/v1/",
        "https://127.0.0.1/v1/",
        "https://evil.example/v1/",
        "https://api01.iq.questrade.com.evil.example/v1/",
        "https://api01.iq.questrade.com:8443/v1/",
    ],
)
def test_api_server_rejects_unsafe_targets(value: str) -> None:
    with pytest.raises(ValueError):
        validate_api_server(value)


def test_api_server_normalizes_provider_discovery() -> None:
    server = validate_api_server("https://api01.iq.questrade.com/")
    assert server.base_url == "https://api01.iq.questrade.com/v1/"
    assert server.sanitized_metadata()["provider_domain_validated"] is True


def test_token_values_never_appear_in_metadata() -> None:
    tokens = TokenLifecycle(now=datetime(2026, 7, 20, tzinfo=timezone.utc))
    result = tokens.record_external_token_response(TOKEN_RESPONSE, allow_record=True)
    assert result["state"] == "AUTHENTICATED"
    assert TOKEN_RESPONSE["access_token"] not in str(result)
    assert TOKEN_RESPONSE["refresh_token"] not in str(result)
    assert tokens.refresh()["data"]["network_call_performed"] is False


def test_token_expiry_and_malformed_response_are_structured() -> None:
    store = InMemoryRefreshTokenStore()
    store.replace(
        QuestradeTokenBundle(
            access_token="expired-test-access",
            refresh_token="expired-test-refresh",
            api_server="https://api01.iq.questrade.com/v1/",
            acquired_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            expires_at=datetime(2026, 7, 19, 1, tzinfo=timezone.utc),
        )
    )
    lifecycle = TokenLifecycle(store, now=datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert lifecycle.status()["state"] == "TOKEN_EXPIRED"
    malformed = lifecycle.record_external_token_response({"access_token": "x"}, allow_record=True)
    assert malformed["state"] == "AUTHENTICATION_REQUIRED"
    assert malformed["failure_code"] == "TOKEN_RESPONSE_INVALID"


def test_account_discovery_requires_explicit_selection_and_masks_numbers() -> None:
    adapter, _ = _configured_adapter()
    accounts = adapter.get_accounts()
    assert accounts["status"] == "ACCOUNT_SELECTION_REQUIRED"
    assert accounts["account_count"] == 2
    assert "11112222" not in str(accounts)
    assert "33334444" not in str(accounts)
    selected = adapter.select_account(accounts["accounts"][0]["account_hash"])
    assert selected["success"] is True
    assert selected["data"]["masked_identifier"] == "***2222"


def test_balances_holdings_quotes_and_option_chain_mapping() -> None:
    adapter, transport = _configured_adapter()
    accounts = adapter.get_accounts()
    adapter.select_account(accounts["accounts"][0]["account_hash"])
    balances = adapter.get_balances()
    assert balances["status"] == "ACCOUNT_READY"
    assert balances["broker_reported_buying_power_is_cash"] is False
    holdings = adapter.get_holdings_snapshot()
    assert holdings["status"] == "HOLDINGS_READY"
    assert holdings["holdings"][0]["symbol"] == "XIU.TO"
    assert holdings["option_positions"][0]["option_type"] == "CALL"
    quote = adapter.get_underlying_quote("XIU.TO")
    assert quote["status"] == "MARKET_DATA_READY"
    chain = adapter.get_option_chain("XIU.TO")
    assert chain["status"] == "OPTION_CHAIN_READY"
    assert chain["contract_quotes_available"] is True
    assert chain["greeks_origin"] == "MISSING"
    assert all(call["method"] == "GET" for call in transport.calls)
    assert adapter.readiness()["state"] == "READ_ONLY_READY"
    assert adapter.certification()["outcome"] == "CERTIFIED_ADVISORY"


def test_account_type_restrictions_are_fail_closed() -> None:
    tfsa = account_restrictions("TFSA")
    assert tfsa["registered"] is True
    assert tfsa["margin_assumed"] is False
    assert tfsa["cash_secured_puts_assumed"] is False
    assert tfsa["requires_broker_confirmation"] is True


def test_read_only_client_blocks_write_methods_and_paths() -> None:
    adapter, transport = _configured_adapter()
    write = adapter.client.request("/accounts", method="POST")
    assert write.state is BrokerOperationalState.EXECUTION_BLOCKED
    denied_path = adapter.client.request("/orders")
    assert denied_path.state is BrokerOperationalState.EXECUTION_BLOCKED
    assert transport.calls == []


def test_rate_limit_retry_is_bounded() -> None:
    class _RateLimited:
        def __init__(self):
            self.count = 0

        def send(self, **request):
            self.count += 1
            if self.count < 3:
                return QuestradeHttpResponse(429, {}, {"Retry-After": "0"})
            return QuestradeHttpResponse(200, {"accounts": []})

    tokens = TokenLifecycle(now=datetime(2026, 7, 20, tzinfo=timezone.utc))
    tokens.record_external_token_response(TOKEN_RESPONSE, allow_record=True)
    transport = _RateLimited()
    client = QuestradeReadOnlyClient(tokens, transport=transport, max_retries=2, sleeper=lambda _: None)
    result = client.request("/accounts")
    assert result.success is True
    assert result.retries == 2
    assert transport.count == 3


def test_current_no_credential_options_income_stays_blocked() -> None:
    advisory = resolve_options_income_advisory_data(broker="QUESTRADE", underlying_symbols=["XIU.TO"])
    assert advisory["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"
    assert advisory["stale"] is False
    assert advisory["broker_listed_options_compatible"] is False
    assert advisory["holdings"]["holdings"] == []
    assert advisory["option_chains"]["calls"] == []
    assert advisory["collateral"]["authority_level"] == "UNAVAILABLE"
    assert advisory["execution_allowed"] is False


def test_mission_control_mobile_report_and_get_only_api(monkeypatch: pytest.MonkeyPatch) -> None:
    unauthenticated_html = render_broker_management({})
    assert "secret_store_provider" not in unauthenticated_html
    assert "Token Health" not in unauthenticated_html
    html = render_broker_management(
        {"authorization_context": {"authenticated": True, "active": True, "role": "SUPER_USER"}}
    )
    assert "Questrade Secure Read-Only Onboarding" in html
    assert "OAuth Launch Enabled" in html
    mobile = frontend_broker({"broker_summary": {"selected_broker": "QUESTRADE"}})
    assert mobile["questrade_read_only"]["execution_state"] == "EXECUTION_BLOCKED"
    report = build_broker_executive_report_package()
    assert "secure_read_only" in report.per_broker["QUESTRADE"]
    assert "test-access-token" not in str(report.as_dict())

    app = FastAPI()
    router = create_mission_control_router(lambda: {})
    app.include_router(router)
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    path = "/api/brokers/questrade/diagnostics/configuration"
    assert client.get(path).status_code == 403
    headers = {"x-css-user-id": "phase178d-test", "x-css-role": "SUPER_USER"}
    response = client.get(path, headers=headers)
    assert response.status_code == 200
    assert response.json()["secrets_returned"] is False
    assert client.post(path, headers=headers).status_code == 405


def test_options_income_report_redacts_account_rows_and_monetary_values() -> None:
    report = build_options_income_executive_report(
        snapshot={
            "generated_at": "2026-07-20T00:00:00+00:00",
            "advisory_data": {
                "holdings": {
                    "account_id": "sensitive-account",
                    "cash": 12345.67,
                    "holdings": [{"symbol": "SECRET-HOLDING", "quantity": 99}],
                    "option_positions": [{"symbol": "SECRET-OPTION"}],
                },
                "collateral": {"value": 98765.43, "currency": "CAD"},
            },
            "collateral": {"value": 98765.43, "currency": "CAD"},
        }
    )
    serialized = str(report)
    assert "sensitive-account" not in serialized
    assert "SECRET-HOLDING" not in serialized
    assert "SECRET-OPTION" not in serialized
    assert "12345.67" not in serialized
    assert "98765.43" not in serialized
    assert "monetary_values_redacted" in serialized


def test_runtime_registry_and_execution_safety_unchanged() -> None:
    resolution = resolve_runtime_mode()
    assert resolution.runtime_mode.value == "DISABLED"
    assert resolution.execution_enabled is False
    assert get_canonical_broker_registry().list_brokers() == list(TIER1_BROKERS)
    assert "IBKR" not in TIER1_BROKERS
    adapter, _ = _configured_adapter()
    assert adapter.health_check()["execution_allowed"] is False
    assert adapter.certification()["execution_certified"] is False
    assert adapter.certification()["micro_pilot_armed"] is False
