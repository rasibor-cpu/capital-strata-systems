"""Phase 178A — Options Income advisory data integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.brokers.broker_registry import get_adapter
from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry
from backend.app.brokers.plugins import questrade as questrade_plugin
from backend.brokers.questrade import QuestradeAdvisoryAdapter, questrade_advisory_readiness
from backend.options.options_income_advisory_contracts import broker_capability_truth
from backend.options.options_income_advisory_cache import wrap_cache_entry
from backend.options.options_income_api import OPTIONS_INCOME_API_ROUTES, build_options_income_api_payload, create_options_income_router
from backend.options.options_income_collateral_authority import resolve_collateral_authority
from backend.options.options_income_data_resolver import (
    build_runtime_context_from_advisory,
    resolve_options_income_advisory_data,
)
from backend.options.options_income_eligibility import (
    evaluate_cash_secured_put_eligibility,
    evaluate_covered_call_eligibility,
)
from backend.options.options_income_freshness import evaluate_freshness
from backend.options.options_income_holdings_adapter import fetch_account_holdings
from backend.options.options_income_market_data_adapter import fetch_underlying_market_data
from backend.options.options_income_market_events import resolve_market_event_context
from backend.options.options_income_option_chain_adapter import fetch_option_chain
from backend.options.options_income_provider_registry import (
    clear_provider_plugins,
    provider_registry_status,
    register_option_chain_provider,
)
from backend.options.options_income_runtime_service import (
    OptionsIncomeRuntimeContext,
    STATUS_DATA_DEPENDENCY_BLOCKED,
    build_options_income_runtime_snapshot,
)
from backend.options.options_income_symbol_normalization import normalize_equity_symbol, parse_occ_option_symbol
from backend.runtime.runtime_mode import resolve_runtime_mode


class _FakeQuote:
    name = "fake_md"

    def readiness(self):
        return {"status": "READY"}

    def get_underlying_quote(self, symbol: str):
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "bid": 100.0,
            "ask": 100.2,
            "last": 100.1,
            "timestamp": now,
            "provenance": "MARKET_DATA_PROVIDER",
            "currency": "USD",
        }


class _FakeChain:
    name = "fake_chain"

    def readiness(self):
        return {"status": "READY"}

    def get_option_chain(self, underlying: str):
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "status": "READY",
            "expirations": ["2099-01-17"],
            "strikes": [100.0],
            "calls": [{"strike": 100.0, "bid": 1.0, "ask": 1.2, "volume": 10, "open_interest": 100}],
            "puts": [{"strike": 100.0, "bid": 1.1, "ask": 1.3, "volume": 8, "open_interest": 90}],
            "quote_timestamp": now,
            "greeks_origin": "PROVIDER",
            "provenance": "OPTION_CHAIN_PROVIDER",
            "multiplier": 100,
            "currency": "USD",
        }


class _FakeHoldings:
    name = "fake_holdings"

    def readiness(self):
        return {"status": "READY"}

    def get_holdings_snapshot(self):
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "status": "READY",
            "broker": "QUESTRADE",
            "account_id": "12345678",
            "account_type": "MARGIN",
            "base_currency": "CAD",
            "cash": 25000.0,
            "buying_power": 25000.0,
            "holdings": [{"symbol": "XIU.TO", "quantity": 250, "encumbered_quantity": 0}],
            "timestamp": now,
            "provenance": "ACCOUNT_HOLDINGS",
        }


class _DemoChain:
    name = "demo"

    def readiness(self):
        return {"status": "READY"}

    def get_option_chain(self, underlying: str):
        return {"demonstration": True, "calls": [{"strike": 1}], "puts": [], "expirations": ["2099-01-01"]}


@pytest.fixture(autouse=True)
def _clear_plugins():
    clear_provider_plugins()
    yield
    clear_provider_plugins()


def test_broker_capability_truth_no_crypto_fx_options() -> None:
    truth = broker_capability_truth()
    assert truth["brokers"]["COINBASE"]["listed_equity_options"] is False
    assert truth["brokers"]["BINANCE"]["listed_equity_options"] is False
    assert truth["brokers"]["OANDA"]["listed_equity_options"] is False
    assert truth["brokers"]["QUESTRADE"]["listed_equity_options"] is True
    assert truth["ibkr_registered"] is False


def test_market_data_not_configured() -> None:
    row = fetch_underlying_market_data("SPY", provider=None)
    assert row["status"] == "NOT_CONFIGURED"
    assert row["failure_reason"] == "MARKET_DATA_PROVIDER_NOT_CONFIGURED"
    assert row["bid"] is None


def test_option_chain_provider_not_configured() -> None:
    row = fetch_option_chain("SPY", provider=None)
    assert row["status"] == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"
    assert row["failure_reason"] == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"
    assert row["contract_count"] == 0


def test_demo_chain_rejected() -> None:
    row = fetch_option_chain("SPY", provider=_DemoChain())
    assert row["status"] == "FAILED"
    assert row["provenance"] == "DEMONSTRATION"


def test_crypto_symbol_not_listed_options_eligible() -> None:
    assert normalize_equity_symbol("BTC_USD")["listed_options_eligible_symbol"] is False
    assert normalize_equity_symbol("BTC-USD")["asset_class"] == "CRYPTO"
    row = fetch_option_chain("BTC-USD", provider=_FakeChain())
    assert row["status"] == "SYMBOL_UNSUPPORTED"


def test_occ_and_ca_normalization() -> None:
    ca = normalize_equity_symbol("XIU.TO")
    assert ca["canonical"] == "XIU.TO"
    assert ca["currency_hint"] == "CAD"
    occ = parse_occ_option_symbol("AAPL250117C00150000")
    assert occ["status"] == "OK"
    assert occ["option_type"] == "CALL"
    assert occ["strike"] == 150.0


def test_freshness_stale() -> None:
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fresh = evaluate_freshness("option_chain_quote", provider_timestamp=old)
    assert fresh["stale"] is True


def test_holdings_sanitizes_account_id() -> None:
    row = fetch_account_holdings(provider=_FakeHoldings(), broker="QUESTRADE")
    assert row["account_id_sanitized"] == "***5678"
    assert "12345678" not in str(row["account_id_sanitized"])


def test_collateral_rejects_fixture_markers() -> None:
    blocked = resolve_collateral_authority(
        holdings={"status": "READY", "cash": 10000.0, "source": "css_smoke_cash", "provenance": "DEMONSTRATION"}
    )
    assert blocked["authority_level"] == "UNAVAILABLE"
    ok = resolve_collateral_authority(
        holdings={"status": "READY", "cash": 10000.0, "base_currency": "CAD", "provenance": "ACCOUNT_HOLDINGS"}
    )
    assert ok["authority_level"] == "ACCOUNT_HOLDINGS_CASH"
    assert ok["value"] == 10000.0


def test_covered_call_eligibility() -> None:
    holdings = fetch_account_holdings(provider=_FakeHoldings())
    chain = fetch_option_chain("XIU.TO", provider=_FakeChain())
    ok = evaluate_covered_call_eligibility(
        underlying="XIU.TO",
        holdings=holdings,
        chain=chain,
        broker_supports_listed_options=True,
    )
    assert ok["eligible"] is True
    assert ok["contracts_available"] == 2
    assert ok["execution_allowed"] is False

    encumbered = dict(holdings)
    encumbered["holdings"] = [{"symbol": "XIU.TO", "quantity": 250, "encumbered_quantity": 200}]
    bad = evaluate_covered_call_eligibility(
        underlying="XIU.TO",
        holdings=encumbered,
        chain=chain,
        broker_supports_listed_options=True,
    )
    assert bad["eligible"] is False
    assert "insufficient_unencumbered_shares" in bad["exclusion_reasons"]


def test_csp_requires_traceable_collateral() -> None:
    unavailable = resolve_collateral_authority()
    row = evaluate_cash_secured_put_eligibility(
        strike=50.0,
        collateral=unavailable,
        broker_supports_listed_options=True,
    )
    assert row["eligible"] is False
    assert "collateral_unavailable" in row["exclusion_reasons"]

    coll = resolve_collateral_authority(
        holdings={"status": "READY", "cash": 20000.0, "base_currency": "USD", "provenance": "ACCOUNT_HOLDINGS"}
    )
    ok = evaluate_cash_secured_put_eligibility(
        strike=50.0,
        collateral=coll,
        chain={"status": "READY"},
        broker_supports_listed_options=True,
        currency="USD",
    )
    assert ok["eligible"] is True
    assert ok["required_collateral"] == 5000.0


def test_coinbase_not_broker_compatible() -> None:
    data = resolve_options_income_advisory_data(broker="COINBASE", underlying_symbols=["SPY"])
    assert data["broker_listed_options_compatible"] is False
    assert data["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"


def test_questrade_configuration_required() -> None:
    adapter = QuestradeAdvisoryAdapter()
    assert adapter.health_check()["status"] == "CONFIGURATION_REQUIRED"
    assert adapter.get_option_chain("XIU.TO")["status"] == "OPTION_CHAIN_PROVIDER_REQUIRED"
    ready = questrade_advisory_readiness(probe_env=True)
    assert ready["adapter_state"] == "CONFIGURATION_REQUIRED"
    assert ready["authentication_activated"] is False
    assert adapter.require_configured()["state"] == "CONFIGURATION_REQUIRED"
    info = questrade_plugin.plugin_info()
    assert info["executable_via_get_adapter"] is False


def test_get_adapter_questrade_returns_structured_state_adapter() -> None:
    readiness = get_adapter("questrade")().readiness()
    assert readiness["state"] == "CONFIGURATION_REQUIRED"
    assert readiness["expected_condition"] is True


def test_missing_provider_blocks_runtime() -> None:
    advisory = resolve_options_income_advisory_data()
    assert advisory["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"
    assert "OPTION_CHAIN" in advisory["missing_dependencies"]
    ctx = build_runtime_context_from_advisory(advisory, persist=False)
    ctx.advisory_data = advisory
    snap = build_options_income_runtime_snapshot(ctx)
    assert snap["engine_status"] == STATUS_DATA_DEPENDENCY_BLOCKED
    assert snap["execution_authority"] == "BLOCKED"
    assert snap["certification"]["execution_ready"] is False
    assert snap["certification"]["live_ready"] is False


def test_advisory_ready_when_providers_supply_data() -> None:
    from backend.options.options_income_provider_registry import (
        register_holdings_provider,
        register_market_data_provider,
    )

    register_market_data_provider(_FakeQuote())
    register_option_chain_provider(_FakeChain())
    register_holdings_provider(_FakeHoldings())
    advisory = resolve_options_income_advisory_data(underlying_symbols=["XIU.TO"], broker="QUESTRADE")
    assert advisory["option_chain_available"] is True
    assert advisory["market_data_available"] is True
    assert advisory["account_holdings_available"] is True
    assert advisory["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"
    assert "BROKER_OPERATIONAL_READINESS" in advisory["missing_dependencies"]
    assert advisory["broker_listed_options_compatible"] is False
    ctx = build_runtime_context_from_advisory(advisory, persist=False, opportunities=[])
    ctx.advisory_data = advisory
    snap = build_options_income_runtime_snapshot(ctx)
    assert snap["engine_status"] == STATUS_DATA_DEPENDENCY_BLOCKED
    assert snap["opportunity_count"] == 0
    # No executable order object
    assert all("order" not in str(o).lower() or o.get("execution_allowed") is False for o in snap.get("opportunities") or [])


def test_provider_exception_text_is_not_exposed() -> None:
    class _FailingQuote:
        def get_underlying_quote(self, symbol: str):
            raise RuntimeError("access_token=secret-value account_number=123456")

    row = fetch_underlying_market_data("SPY", provider=_FailingQuote())
    assert row["failure_reason"] == "UNEXPECTED_PROVIDER_FAULT"
    assert row["correlation_id"]
    assert "secret-value" not in str(row)
    assert "123456" not in str(row)


def test_cache_recursively_redacts_nested_credentials() -> None:
    entry = wrap_cache_entry(
        provider="test",
        data_type="holdings",
        payload={"nested": {"access_token": "secret-value", "account_number": "123456"}, "status": "READY"},
    )
    assert entry["payload"]["nested"]["access_token"] == "[REDACTED]"
    assert entry["payload"]["nested"]["account_number"] == "[REDACTED]"
    assert "secret-value" not in str(entry)
    assert "123456" not in str(entry)


def test_broker_collateral_requires_reliable_metadata() -> None:
    rejected = resolve_collateral_authority(
        broker_collateral={"value": 10000.0, "status": "READY", "provenance": "BROKER"}
    )
    assert rejected["authority_level"] == "UNAVAILABLE"
    accepted = resolve_collateral_authority(
        broker_collateral={
            "value": 10000.0,
            "status": "READY",
            "provenance": "BROKER",
            "currency": "CAD",
            "timestamp": "2026-07-20T20:00:00Z",
        }
    )
    assert accepted["authority_level"] == "BROKER_REPORTED"


def test_stale_chain_status() -> None:
    class _StaleChain(_FakeChain):
        def get_option_chain(self, underlying: str):
            row = super().get_option_chain(underlying)
            old = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0)
            row["quote_timestamp"] = old.isoformat().replace("+00:00", "Z")
            return row

    chain = fetch_option_chain("SPY", provider=_StaleChain())
    assert chain["status"] == "STALE"
    advisory = resolve_options_income_advisory_data(
        underlying_symbols=["SPY"],
        option_chain_provider=_StaleChain(),
        market_data_provider=_FakeQuote(),
        holdings_provider=_FakeHoldings(),
        broker="QUESTRADE",
    )
    assert advisory["stale"] is True
    assert advisory["readiness_status"] == "STALE"


def test_greeks_origin_distinction() -> None:
    chain = fetch_option_chain("SPY", provider=_FakeChain())
    assert chain["greeks_origin"] == "PROVIDER"
    empty = fetch_option_chain("SPY", provider=None)
    assert empty["greeks_origin"] == "MISSING"


def test_event_data_limitation_disclosed() -> None:
    events = resolve_market_event_context(underlying="SPY")
    assert events["status"] == "EVENT_DATA_UNAVAILABLE"
    assert events["invented_dates"] is False


def test_provider_registry_empty() -> None:
    status = provider_registry_status()
    assert status["option_chain_status"] == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"
    assert status["paid_vendor_registered"] is False
    assert status["scraping_enabled"] is False


def test_api_readonly_178a_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    for path in OPTIONS_INCOME_API_ROUTES.values():
        assert path.startswith("/api/options-income")
    assert "/api/options-income/data-readiness" in OPTIONS_INCOME_API_ROUTES.values()
    assert "/api/options-income/providers" in OPTIONS_INCOME_API_ROUTES.values()
    advisory = resolve_options_income_advisory_data()
    ctx = build_runtime_context_from_advisory(advisory, persist=False)
    ctx.advisory_data = advisory
    snap = build_options_income_runtime_snapshot(ctx)
    readiness = build_options_income_api_payload(snap, "data_readiness")
    assert readiness["section"] == "data_readiness"
    assert readiness["data"]["execution_ready"] is False
    holdings = build_options_income_api_payload(snap, "holdings")
    assert "access_token" not in holdings["data"]
    assert "cash" not in holdings["data"]
    assert "buying_power" not in holdings["data"]
    assert "holdings" not in holdings["data"]
    assert holdings["data"]["monetary_values_redacted"] is True
    collateral = build_options_income_api_payload(snap, "collateral_summary")
    assert "value" not in collateral["data"]
    assert collateral["data"]["monetary_value_redacted"] is True
    router = create_options_income_router(payload_provider=lambda: snap)
    methods = set()
    for route in getattr(router, "routes", []):
        methods |= set(getattr(route, "methods", set()) or set())
    assert not methods or methods == {"GET"} or "GET" in methods

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    assert client.get("/api/options-income/holdings").status_code == 401
    headers = {"x-css-user-id": "phase178-test", "x-css-role": "SUPER_USER"}
    response = client.get("/api/options-income/holdings", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["monetary_values_redacted"] is True
    assert client.post("/api/options-income/holdings", headers=headers).status_code == 405
    assert "POST" not in methods
    assert "PUT" not in methods
    assert "PATCH" not in methods
    assert "DELETE" not in methods


def test_runtime_resolver_and_tier1_unchanged() -> None:
    resolution = resolve_runtime_mode()
    assert resolution.runtime_mode.value == "DISABLED"
    assert resolution.execution_enabled is False
    brokers = get_canonical_broker_registry().list_brokers()
    assert brokers == list(TIER1_BROKERS)
    assert "IBKR" not in brokers


def test_empty_context_still_dependency_blocked() -> None:
    snap = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=False))
    assert snap["engine_status"] == STATUS_DATA_DEPENDENCY_BLOCKED
    assert snap["certification"]["execution_ready"] is False
