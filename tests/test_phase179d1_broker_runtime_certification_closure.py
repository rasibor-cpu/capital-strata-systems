"""Phase 179D.1 — Enterprise Broker Runtime certification closure."""

from __future__ import annotations

import pytest

from backend.app.brokers.broker_bootstrap import BrokerBootstrapError, initialize_broker
from backend.brokers.runtime import (
    BINANCE_CAPABILITIES,
    COINBASE_CAPABILITIES,
    OANDA_CAPABILITIES,
    QUESTRADE_READ_ONLY_CAPABILITIES,
    EnterpriseBrokerBinding,
    canonical_broker_consumer,
    certify_enterprise_authority_closure,
    compose_enterprise_broker_runtime,
    scan_active_runtime_authority_bypasses,
)
from backend.reports_center.producers import (
    produce,
    registered_producer_codes,
)
from backend.reports_center.registry import by_code
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


REPORT_CODES = {
    "enterprise_broker_readiness",
    "enterprise_provider_readiness",
    "enterprise_holdings_certification",
    "enterprise_market_data_certification",
    "enterprise_runtime_dependency_matrix",
    "enterprise_options_income_readiness",
    "enterprise_advisory_runtime_certification",
}


def _composition():
    vault = CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"c" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )
    identities = EnterpriseIdentityService()
    secrets = EnterpriseSecretService(vault=vault)
    admin = identities.register(
        identity_id="phase179d1-admin",
        display_name="Phase 179D.1 Admin",
        identity_type=IdentityType.HUMAN,
        role="SUPER_USER",
        owner="platform-security",
        environment="TEST",
    )
    oauth = EnterpriseOAuthManager(secrets=secrets)
    composition = compose_enterprise_broker_runtime(
        identities=identities,
        secrets=secrets,
        oauth=oauth,
    )
    requirements = {
        "QUESTRADE": (QUESTRADE_READ_ONLY_CAPABILITIES, ("OAUTH_ACCESS_TOKEN",)),
        "COINBASE": (COINBASE_CAPABILITIES, ("API_KEY_NAME", "PRIVATE_KEY")),
        "BINANCE": (BINANCE_CAPABILITIES, ("API_KEY", "API_SECRET")),
        "OANDA": (OANDA_CAPABILITIES, ("ACCESS_TOKEN",)),
    }
    for broker, (capabilities, secret_types) in requirements.items():
        consumer = canonical_broker_consumer(broker)
        runtime_identity = identities.register(
            identity_id=consumer,
            display_name=f"{broker} Enterprise Read-Only Runtime",
            identity_type=IdentityType.SERVICE,
            role="ADMIN",
            owner="platform-security",
            environment="TEST",
        )
        client = secrets.register(
            bytearray(f"synthetic-{broker}-client".encode()),
            provider="ENTERPRISE_VAULT",
            secret_type="OAUTH_CLIENT_ID",
            owner="platform-security",
            environment="TEST",
            operator=admin.identity_id,
            broker=broker,
        )
        metadata = [
            secrets.register(
                bytearray(f"synthetic-{broker}-{secret_type}".encode()),
                provider="ENTERPRISE_VAULT",
                secret_type=secret_type,
                owner="platform-security",
                environment="TEST",
                operator=admin.identity_id,
                broker=broker,
            )
            for secret_type in secret_types
        ]
        oauth_registration = oauth.register(
            provider=OAuthProvider(broker),
            environment="TEST",
            owner=f"platform-security-{broker}",
            scopes=("read",),
            token_type=OAuthTokenType.ACCESS_TOKEN,
            client_id_secret_uuid=client.secret_uuid,
            access_token_uuid=metadata[0].secret_uuid,
            pkce_configured=broker == "QUESTRADE",
        )
        request = SecretAccessRequest(
            identity=runtime_identity,
            purpose="ENTERPRISE_BROKER_RUNTIME",
            component=consumer,
            duration_seconds=60,
        )
        handles = tuple(
            secrets.issue_handle(row.secret_uuid, request=request) for row in metadata
        )
        composition.brokers.register(
            EnterpriseBrokerBinding(
                broker=broker,
                consumer=consumer,
                secret_handles=handles,
                oauth_handle=issue_oauth_handle(oauth_registration),
                capabilities=capabilities,
            ),
            operator=admin.identity_id,
        )
    return composition, admin


def test_native_broker_migration_uses_only_handles_and_runtime_leases() -> None:
    composition, admin = _composition()
    for broker in ("COINBASE", "BINANCE", "OANDA"):
        adapter = composition.native_adapter(broker, operator=admin.identity_id)
        health = adapter.runtime_health()
        assert health["status"] == "READY"
        assert health["credential_fields_present"] is False
        assert health["oauth_state_owned_by_broker"] is False
        assert health["secret_storage_present"] is False
        assert health["execution_allowed"] is False
        result = adapter.read(next(iter(adapter.capabilities.operations)))
        assert result["status"] == "PROVIDER_UNAVAILABLE"
        assert result["fabricated"] is False
        assert not hasattr(adapter, "api_key")
        assert not hasattr(adapter, "token")
        assert not hasattr(adapter, "client_secret")

    questrade = composition.brokers.binding("QUESTRADE")
    composition.brokers.lease(
        "QUESTRADE",
        secret_uuid=questrade.secret_handles[0].secret_uuid,
        capability="OAUTH_ACCESS_TOKEN",
        operator=admin.identity_id,
    )
    assert {
        row["broker"]
        for row in composition.brokers.health()["secret_lease_health"]
    } == {"QUESTRADE", "COINBASE", "BINANCE", "OANDA"}


def test_composition_is_inactive_and_authority_certification_closes() -> None:
    composition, admin = _composition()
    with pytest.raises(BrokerBootstrapError, match="ENTERPRISE_BROKER_RUNTIME_REQUIRED"):
        initialize_broker("coinbase")
    for broker in ("COINBASE", "BINANCE", "OANDA"):
        initialize_broker(
            broker,
            mode="disabled",
            enterprise_runtime=composition,
            operator=admin.identity_id,
        )
    initialize_broker(
        "QUESTRADE",
        mode="disabled",
        enterprise_runtime=composition,
        operator=admin.identity_id,
    )
    status = composition.status()
    assert status["authentication_activated"] is False
    assert status["oauth_authorization_activated"] is False
    assert status["market_data_activated"] is False
    assert status["live_apis_activated"] is False
    bypasses = scan_active_runtime_authority_bypasses(".")
    assert bypasses == []
    certification = certify_enterprise_authority_closure(
        composition,
        registered_report_codes=registered_producer_codes(),
        compatibility_paths=[
            {
                "path": "backend/app/brokers/credential_loader.py",
                "ownership_status": "LEGACY_COMPATIBILITY",
            }
        ],
        active_bypass_paths=bypasses,
    )
    assert certification["outcome"] == "CERTIFIED"
    assert certification["compatibility_certified_enterprise_managed"] is False
    assert certification["native_brokers"] == [
        "BINANCE",
        "COINBASE",
        "OANDA",
        "QUESTRADE",
    ]
    assert certification["execution_allowed"] is False


def test_reports_center_registration_and_fail_closed_generation(tmp_path) -> None:
    assert REPORT_CODES <= registered_producer_codes()
    for report_code in REPORT_CODES:
        definition = by_code(report_code)
        assert definition is not None
        assert definition.status == "AVAILABLE_WITH_LIMITATIONS"
        assert definition.advisory_only is True
        result = produce(report_code, filters={}, repo_root=tmp_path)
        assert result["report_status"] == "FAILED"
        assert result["content"]["status"] == "EVIDENCE_UNAVAILABLE"
        assert result["execution_allowed"] is False
