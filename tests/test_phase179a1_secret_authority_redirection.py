"""Phase 179A.1 — Enterprise Secret Authority redirection certification."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.brokers.credential_loader import load_credentials_for_broker
from backend.security.credential_vault import CredentialVault, InMemoryEncryptedStorage
from backend.security.identity import (
    BrokerSecretCompatibilityAdapter,
    EnterpriseAuthorityRedirector,
    EnterpriseIdentityService,
    EnterpriseSecretService,
    IdentityType,
    OwnershipStatus,
    SecretAccessRequest,
    calculate_vault_health_score,
    identity_governance_payload,
)
from backend.security.identity.authority_certification import certify_secret_authority
from backend.security.identity.authority_reporting import (
    AUTHORITY_REPORT_TITLES,
    build_authority_report_suite,
)
from backend.security.identity.broker_secret_adapter import (
    clear_broker_secret_adapter,
    install_broker_secret_adapter,
)
from backend.security.identity.identity_api import create_identity_security_router
from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_crypto import StaticKeyProvider, VaultCrypto
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.safety import validate_no_secret_payload


def _platform():
    vault = CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"r" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )
    identities = EnterpriseIdentityService()
    secrets = EnterpriseSecretService(vault=vault)
    admin = identities.register(
        identity_id="phase179a1-admin",
        display_name="Authority Admin",
        identity_type=IdentityType.HUMAN,
        role="SUPER_USER",
        owner="platform-security",
        environment="TEST",
    )
    redirector = EnterpriseAuthorityRedirector(secrets)
    adapter = BrokerSecretCompatibilityAdapter(redirector)
    return identities, secrets, admin, redirector, adapter


def _request(admin):
    return SecretAccessRequest(
        identity=admin,
        purpose="BROKER_COMPATIBILITY_HANDLE_LOOKUP",
        component="BrokerSecretCompatibilityAdapter",
        duration_seconds=60,
    )


def test_compatibility_adapter_registers_and_resolves_handles_only() -> None:
    _, _, admin, redirector, adapter = _platform()
    registered = adapter.register_legacy_mapping(
        "questrade",
        {"QUESTRADE_REFRESH_TOKEN": "synthetic-authority-value"},
        component="legacy-test",
        source_path=".env.questrade",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    assert registered["ownership_status"] == "LEGACY_COMPATIBILITY"
    assert registered["plaintext_returned"] is False
    assert "synthetic-authority-value" not in str(registered)
    handles = adapter.request_handles(
        "questrade",
        ("QUESTRADE_REFRESH_TOKEN",),
        request=_request(admin),
    )
    assert handles["authority"] == "EnterpriseSecretService"
    assert handles["plaintext_returned"] is False
    assert "synthetic-authority-value" not in str(handles)
    assert redirector.dependency_graph()["canonical_path"].startswith("Broker ->")


def test_credential_loader_wiring_preserves_legacy_shape_and_reports_violation(tmp_path: Path) -> None:
    _, _, admin, redirector, adapter = _platform()
    credential_file = tmp_path / ".env.oanda"
    credential_file.write_text(
        "OANDA_API_KEY=synthetic-oanda-token\nOANDA_ACCOUNT_ID=synthetic-account\n",
        encoding="utf-8",
    )
    install_broker_secret_adapter(adapter)
    try:
        loaded = load_credentials_for_broker("oanda", base_dir=str(tmp_path))
    finally:
        clear_broker_secret_adapter()
    assert loaded["OANDA_API_KEY"] == "synthetic-oanda-token"
    assert loaded["OANDA_ACCOUNT_ID"] == "synthetic-account"
    assert loaded["legacy_compatibility"] is True
    assert loaded["enterprise_secret_authority"]["plaintext_returned"] is False
    assert redirector.direct_access_violations()
    certification = certify_secret_authority(redirector)
    assert certification["outcome"] == "NOT_CERTIFIED"
    assert "direct_broker_access_absent" in certification["blockers"]


def test_ownership_classification_and_single_authority_certification() -> None:
    _, secrets, admin, redirector, adapter = _platform()
    adapter.register_legacy_mapping(
        "coinbase",
        {"COINBASE_API_KEY": "synthetic-managed-key"},
        component="coinbase-compatibility",
        source_path="credential-loader",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    redirector.certify_binding(
        "COINBASE", "COINBASE_API_KEY", native_handle_consumer=True
    )
    secrets.register(
        bytearray(b"synthetic-orphan"),
        provider="ENTERPRISE_VAULT",
        secret_type="CERTIFICATE",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    redirector.record_unknown_credential(
        broker="BINANCE",
        credential_name="UNMAPPED_SECRET",
        component="unknown-loader",
        source_path="unknown",
    )
    statuses = {row["status"] for row in redirector.ownership_inventory()}
    assert statuses == {
        OwnershipStatus.ENTERPRISE_MANAGED.value,
        OwnershipStatus.ORPHANED.value,
        OwnershipStatus.UNKNOWN.value,
    }
    migration = redirector.migration_status()
    assert migration["enterprise_managed"] == 1
    assert migration["orphaned"] == 1
    assert migration["unknown"] == 1


def test_vault_health_score_has_bounded_weighted_rationale() -> None:
    _, _, admin, redirector, adapter = _platform()
    adapter.register_legacy_mapping(
        "oanda",
        {"OANDA_API_KEY": "synthetic-health-token"},
        component="compatibility",
        source_path=".env.oanda",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    degraded = calculate_vault_health_score(redirector)
    assert 0 <= degraded["score"] <= 100
    assert sum(row["weight"] for row in degraded["factors"].values()) == 100
    assert degraded["rationale"]
    with pytest.raises(PermissionError, match="NATIVE_SECRET_HANDLE_CONSUMER_REQUIRED"):
        redirector.certify_binding("OANDA", "OANDA_API_KEY")
    redirector.certify_binding(
        "OANDA", "OANDA_API_KEY", native_handle_consumer=True
    )
    healthy = calculate_vault_health_score(redirector)
    assert healthy["score"] > degraded["score"]
    assert certify_secret_authority(redirector)["outcome"] == "CERTIFIED"


def test_direct_access_scanner_detects_broker_environment_bypass(tmp_path: Path) -> None:
    _, _, _, redirector, _ = _platform()
    source = tmp_path / "legacy_broker.py"
    source.write_text(
        'import os\nvalue = os.getenv("OANDA_ACCESS_TOKEN", "")\n',
        encoding="utf-8",
    )
    violations = redirector.scan_direct_access_paths((source,))
    assert len(violations) == 1
    assert violations[0]["broker"] == "OANDA"
    assert violations[0]["violation"] == "DIRECT_BROKER_CREDENTIAL_ACCESS"
    assert redirector.dependency_graph()["automatic_rewrites"] is False


def test_authority_reports_are_a4_and_viewer_compatible() -> None:
    _, _, admin, redirector, adapter = _platform()
    adapter.register_legacy_mapping(
        "questrade",
        {"QUESTRADE_TOKEN_STORE_ID": "synthetic-store-reference"},
        component="compatibility",
        source_path="profile",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    reports = build_authority_report_suite(redirector)
    assert set(reports) == set(AUTHORITY_REPORT_TITLES)
    for report in reports.values():
        assert report["document"]["presentation"]["page_size"] == "A4"
        assert report["document"]["pages"][0]["page_type"] == "cover"
        assert any(page["page_type"] == "toc" for page in report["document"]["pages"])
        assert report["viewer_compatible"] is True
        assert "synthetic-store-reference" not in str(report)


def test_authority_api_is_authenticated_and_get_only(monkeypatch: pytest.MonkeyPatch) -> None:
    identities, secrets, admin, redirector, adapter = _platform()
    adapter.register_legacy_mapping(
        "coinbase",
        {"COINBASE_API_KEY": "synthetic-api-key"},
        component="compatibility",
        source_path="profile",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    app = FastAPI()
    router = create_identity_security_router(
        identities=identities,
        secrets=secrets,
        authority_redirector=redirector,
    )
    app.include_router(router)
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    paths = (
        "/api/security/authority",
        "/api/security/ownership",
        "/api/security/vault-health",
        "/api/security/migration",
        "/api/security/direct-access",
    )
    for path in paths:
        assert client.get(path).status_code == 403
    assert client.get(
        "/api/security/authority",
        headers={"x-css-user-id": "unsupported", "x-css-role": "ANALYST"},
    ).status_code == 403
    headers = {"x-css-user-id": admin.identity_id, "x-css-role": "SUPER_USER"}
    admin_headers = {"x-css-user-id": "phase179a1-admin-2", "x-css-role": "ADMIN"}
    assert client.get("/api/security/authority", headers=admin_headers).status_code == 200
    for path in paths:
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert "synthetic-api-key" not in response.text
        assert client.post(path, headers=headers).status_code == 405
        assert client.put(path, headers=headers).status_code == 405
        assert client.delete(path, headers=headers).status_code == 405


def test_mission_control_displays_authority_migration_metadata() -> None:
    identities, secrets, admin, redirector, adapter = _platform()
    adapter.register_legacy_mapping(
        "questrade",
        {"QUESTRADE_REFRESH_TOKEN": "synthetic-mc-token"},
        component="compatibility",
        source_path="profile",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "identity_governance": identity_governance_payload(
            identities,
            secrets,
            authority_redirector=redirector,
        ),
    }
    html = render_mission_control_shell(state, active_section="enterprise_identity")
    for title in (
        "Secret Authority",
        "Legacy Compatibility",
        "Ownership Coverage",
        "Orphaned Secrets",
        "Direct Access Violations",
        "Migration Progress",
        "Vault Health Score",
    ):
        assert title in html
    assert "synthetic-mc-token" not in html
    safe, reasons = validate_no_secret_payload(state["identity_governance"])
    assert safe, reasons
