"""Phase 179D — Enterprise Broker and Questrade read-only runtime."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from backend.brokers.runtime import (
    BROKER_RUNTIME_REPORT_TITLES,
    COINBASE_CAPABILITIES,
    EnterpriseBrokerBinding,
    EnterpriseBrokerRuntime,
    QUESTRADE_READ_ONLY_CAPABILITIES,
    QuestradeEnterpriseReadOnlyRuntime,
    broker_runtime_governance_payload,
    build_broker_runtime_report_suite,
    canonical_broker_consumer,
    certify_enterprise_broker_runtime,
    resolve_advisory_state,
)
from backend.options.options_income_collateral_authority import resolve_collateral_authority
from backend.options.options_income_data_resolver import resolve_options_income_advisory_data
from backend.options.options_income_freshness import evaluate_freshness
from backend.options.options_income_holdings_adapter import resolve_holdings_authority
from backend.security.credential_vault import CredentialVault, InMemoryEncryptedStorage
from backend.security.identity import (
    EnterpriseIdentityService,
    EnterpriseSecretService,
    IdentityType,
    SecretAccessRequest,
)
from backend.security.oauth import EnterpriseOAuthManager, OAuthProvider, OAuthTokenType
from backend.security.oauth.oauth_handles import issue_oauth_handle
from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_crypto import StaticKeyProvider, VaultCrypto
from dashboard.mission_control.layout import render_mission_control_shell


def _platform():
    vault = CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"d" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )
    identities = EnterpriseIdentityService()
    secrets = EnterpriseSecretService(vault=vault)
    admin = identities.register(
        identity_id="phase179d-admin",
        display_name="Phase 179D Admin",
        identity_type=IdentityType.HUMAN,
        role="SUPER_USER",
        owner="platform-security",
        environment="TEST",
    )
    consumer = canonical_broker_consumer("QUESTRADE")
    runtime_identity = identities.register(
        identity_id=consumer,
        display_name="Questrade Enterprise Read-Only Runtime",
        identity_type=IdentityType.SERVICE,
        role="ADMIN",
        owner="platform-security",
        environment="TEST",
    )
    client = secrets.register(
        bytearray(b"synthetic-phase179d-client"),
        provider="ENTERPRISE_VAULT",
        secret_type="OAUTH_CLIENT_ID",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
        broker="QUESTRADE",
    )
    access = secrets.register(
        bytearray(b"synthetic-phase179d-access"),
        provider="ENTERPRISE_VAULT",
        secret_type="OAUTH_ACCESS_TOKEN",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
        broker="QUESTRADE",
    )
    oauth = EnterpriseOAuthManager(secrets=secrets)
    registration = oauth.register(
        provider=OAuthProvider.QUESTRADE,
        environment="TEST",
        owner="platform-security",
        scopes=("read", "accounts", "market_data"),
        token_type=OAuthTokenType.ACCESS_TOKEN,
        client_id_secret_uuid=client.secret_uuid,
        access_token_uuid=access.secret_uuid,
        pkce_configured=True,
    )
    request = SecretAccessRequest(
        identity=runtime_identity,
        purpose="ENTERPRISE_BROKER_RUNTIME",
        component=consumer,
        duration_seconds=60,
    )
    handle = secrets.issue_handle(access.secret_uuid, request=request)
    runtime = EnterpriseBrokerRuntime(secrets=secrets)
    runtime.register(
        EnterpriseBrokerBinding(
            broker="QUESTRADE",
            consumer=consumer,
            secret_handles=(handle,),
            oauth_handle=issue_oauth_handle(registration),
            capabilities=QUESTRADE_READ_ONLY_CAPABILITIES,
        ),
        operator=admin.identity_id,
    )
    lease = runtime.lease(
        "QUESTRADE",
        secret_uuid=access.secret_uuid,
        capability="OAUTH_ACCESS_TOKEN",
        operator=admin.identity_id,
    )
    return runtime, lease


class _OfflineQuestradeProvider:
    def __init__(self):
        self.calls: list[str] = []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def fetch(
        self,
        dataset: str,
        *,
        authorization: memoryview,
        parameters: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        assert bytes(authorization) == b"synthetic-phase179d-access"
        self.calls.append(dataset)
        if dataset == "ACCOUNTS":
            return {
                "timestamp": self.timestamp,
                "accounts": [
                    {
                        "number": "12345678",
                        "type": "MARGIN",
                        "status": "ACTIVE",
                        "currency": "CAD",
                        "alias": "Primary",
                    }
                ],
            }
        if dataset == "POSITIONS":
            return {
                "timestamp": self.timestamp,
                "positions": [
                    {
                        "symbol": "XIU.TO",
                        "securityType": "ETF",
                        "currentQuantity": 200,
                        "encumberedQuantity": 0,
                        "currency": "CAD",
                    }
                ],
            }
        if dataset == "BALANCES":
            return {
                "timestamp": self.timestamp,
                "perCurrencyBalances": [
                    {
                        "currency": "CAD",
                        "cash": 15000,
                        "buyingPower": 25000,
                        "maintenanceExcess": 18000,
                        "totalEquity": 50000,
                    }
                ],
            }
        if dataset == "QUOTES":
            return {
                "timestamp": self.timestamp,
                "quotes": [
                    {
                        "symbol": "XIU.TO",
                        "bidPrice": 34.0,
                        "askPrice": 34.1,
                        "lastTradePrice": 34.05,
                        "volume": 1000,
                        "lastTradeTime": self.timestamp,
                        "currency": "CAD",
                    }
                ],
            }
        if dataset == "OPTION_CHAINS":
            return {
                "timestamp": self.timestamp,
                "optionChain": [
                    {
                        "expiryDate": "2026-08-21",
                        "chainPerRoot": [
                            {
                                "chainPerStrikePrice": [
                                    {
                                        "strikePrice": 34,
                                        "callSymbolId": 101,
                                        "putSymbolId": 102,
                                        "bidPrice": 1.0,
                                        "askPrice": 1.1,
                                        "openInterest": 50,
                                        "impliedVolatility": 0.2,
                                        "delta": 0.5,
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        if dataset == "MARKET_PERMISSIONS":
            return {"timestamp": self.timestamp, "permissions": {"options": "READ_ONLY"}}
        if dataset == "WATCHLISTS":
            return {"timestamp": self.timestamp, "watchlists": [{"name": "Income", "symbols": ["XIU.TO"]}]}
        raise RuntimeError("unsupported offline fixture dataset")


def test_runtime_uses_secret_oauth_handles_and_capability_bound_lease() -> None:
    runtime, lease = _platform()
    binding = runtime.binding("QUESTRADE")
    assert binding.oauth_handle is not None
    assert binding.secret_handles[0].secret_uuid.startswith("SUUID-")
    assert runtime.health()["legacy_compatibility_count"] == 0
    assert lease.health()["plaintext_returned"] is False
    with pytest.raises(PermissionError, match="CONSUMER_MISMATCH"):
        with lease.open(consumer="WrongConsumer", capability="OAUTH_ACCESS_TOKEN"):
            pass
    with pytest.raises(PermissionError, match="CAPABILITY_MISMATCH"):
        with lease.open(
            consumer="QuestradeEnterpriseReadOnlyRuntime",
            capability="ORDER_SUBMISSION",
        ):
            pass


def test_secret_handle_consumer_and_broker_binding_remain_strict() -> None:
    runtime, lease = _platform()
    binding = runtime.binding("QUESTRADE")
    handle = binding.secret_handles[0]
    assert handle.issued_to == binding.consumer
    normalized = EnterpriseBrokerBinding(
        broker=" questrade ",
        consumer="  QuestradeEnterpriseReadOnlyRuntime  ",
        secret_handles=(handle,),
        oauth_handle=binding.oauth_handle,
        capabilities=QUESTRADE_READ_ONLY_CAPABILITIES,
    )
    assert normalized.broker == "QUESTRADE"
    assert normalized.consumer == "QuestradeEnterpriseReadOnlyRuntime"

    with pytest.raises(PermissionError, match="BROKER_RUNTIME_CONSUMER_MISMATCH"):
        runtime.register(
            replace(binding, consumer="questradeenterprisereadonlyruntime"),
            operator="phase179d-admin",
        )

    mismatched = replace(handle, issued_to="WrongConsumer")
    with pytest.raises(PermissionError, match="SECRET_HANDLE_CONSUMER_MISMATCH"):
        runtime.register(
            replace(binding, secret_handles=(mismatched,)),
            operator="phase179d-admin",
        )

    cross_broker = replace(
        handle,
        issued_to="CoinbaseEnterpriseReadOnlyRuntime",
    )
    with pytest.raises(PermissionError, match="SECRET_HANDLE_BROKER_MISMATCH"):
        runtime.register(
            EnterpriseBrokerBinding(
                broker="COINBASE",
                consumer="CoinbaseEnterpriseReadOnlyRuntime",
                secret_handles=(cross_broker,),
                oauth_handle=None,
                capabilities=COINBASE_CAPABILITIES,
            ),
            operator="phase179d-admin",
        )

    with pytest.raises(
        ValueError,
        match="LEGACY_COMPATIBILITY_CANNOT_BE_ENTERPRISE_RUNTIME",
    ):
        runtime.register(
            replace(binding, legacy_compatibility=True),
            operator="phase179d-admin",
        )
    assert lease.metadata.consumer == binding.consumer


def test_questrade_read_only_runtime_and_provider_backed_options_advisory() -> None:
    runtime, lease = _platform()
    provider = _OfflineQuestradeProvider()
    questrade = QuestradeEnterpriseReadOnlyRuntime(
        access_token_lease=lease,
        provider=provider,
        account_reference="opaque-account-reference",
    )
    accounts = questrade.discover_accounts()
    assert accounts["account_aliases"][0]["alias"] == "Primary"
    assert "12345678" not in str(accounts)
    holdings = questrade.get_holdings_snapshot()
    assert holdings["buying_power"] == 25000
    assert holdings["maintenance_excess"] == 18000
    assert holdings["holdings"][0]["provenance"] == "QUESTRADE_POSITIONS"
    assert questrade.watchlists()["watchlists"]
    assert questrade.market_permissions(account_reference="opaque-account-reference")[
        "broker_confirmed"
    ] is True

    advisory = resolve_options_income_advisory_data(
        underlying_symbols=["XIU.TO"],
        broker="QUESTRADE",
        enterprise_broker_provider=questrade,
    )
    assert advisory["readiness_status"] == "ADVISORY_READY"
    assert advisory["market_data_available"] is True
    assert advisory["option_chain_available"] is True
    assert advisory["account_holdings_available"] is True
    assert advisory["collateral"]["authority_level"] == "BROKER_BUYING_POWER"
    assert advisory["option_chain_rows"][0]["calls"][0]["open_interest"] == 50
    assert advisory["option_chain_rows"][0]["calls"][0]["implied_volatility"] == 0.2
    assert advisory["opportunities_fabricated"] is False

    certification = certify_enterprise_broker_runtime(
        runtime,
        advisory_evidence=advisory,
        legacy_broker_credential_paths_retired=True,
    )
    assert certification["outcome"] == "CERTIFIED"
    assert certification["execution_posture"] == "DISABLED"
    assert "synthetic-phase179d-access" not in str(certification)


def test_authority_hierarchies_freshness_and_state_priority() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    holdings = resolve_holdings_authority(
        broker_holdings={
            "status": "READY",
            "provenance": "BROKER",
            "holdings": [{"symbol": "SPY", "quantity": 10, "provenance": "BROKER"}],
        },
        enterprise_cache={
            "status": "READY",
            "provenance": "CACHE",
            "holdings": [{"symbol": "QQQ", "quantity": 5}],
        },
    )
    assert holdings["authority_level"] == "BROKER_HOLDINGS"
    assert holdings["fabricated"] is False

    collateral = resolve_collateral_authority(
        broker_buying_power={
            "status": "READY",
            "provenance": "BROKER",
            "currency": "USD",
            "timestamp": ts,
            "value": 100,
        },
        broker_margin={
            "status": "READY",
            "provenance": "BROKER",
            "currency": "USD",
            "timestamp": ts,
            "value": 200,
        },
    )
    assert collateral["authority_level"] == "BROKER_BUYING_POWER"
    missing = evaluate_freshness("holdings", provider_timestamp=None, now=ts)
    assert missing["freshness"] == "UNKNOWN"
    assert missing["stale"] is False
    assert missing["advisory_status"] == "TIMESTAMP_REQUIRED"
    assert resolve_advisory_state(
        ["PARTIAL_DATA", "PROVIDER_UNAVAILABLE", "STALE"]
    ).value == "PROVIDER_UNAVAILABLE"


def test_mission_control_reports_and_certification_remain_fail_closed() -> None:
    runtime, lease = _platform()
    provider = _OfflineQuestradeProvider()
    questrade = QuestradeEnterpriseReadOnlyRuntime(
        access_token_lease=lease,
        provider=provider,
        account_reference="opaque-account-reference",
    )
    advisory = resolve_options_income_advisory_data(
        underlying_symbols=["XIU.TO"],
        broker="QUESTRADE",
        enterprise_broker_provider=questrade,
    )
    reports = build_broker_runtime_report_suite(
        runtime=runtime,
        advisory_evidence=advisory,
    )
    assert set(reports) == set(BROKER_RUNTIME_REPORT_TITLES)
    assert all(report["document"]["presentation"]["page_size"] == "A4" for report in reports.values())
    assert all(report["execution_allowed"] is False for report in reports.values())

    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "enterprise_broker_runtime": broker_runtime_governance_payload(
            runtime,
            advisory_evidence=advisory,
        ),
    }
    html = render_mission_control_shell(state, active_section="broker_management")
    for label in (
        "Enterprise Broker Health",
        "OAuth Status",
        "Secret Lease Health",
        "Provider Health",
        "Holdings Readiness",
        "Market Data Readiness",
        "Options Readiness",
        "Advisory Readiness",
    ):
        assert label in html
    assert "synthetic-phase179d-access" not in html
    assert "EXECUTION_BLOCKED" in html
