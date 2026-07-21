"""Phase 179A — certification-first Enterprise Identity & Secrets Platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.security.credential_vault import CredentialVault, InMemoryEncryptedStorage
from backend.security.identity import (
    DuplicateSecretError,
    EnterpriseIdentityService,
    EnterpriseSecretDiscovery,
    EnterpriseSecretService,
    IdentityType,
    SecretAccessRequest,
    SecretClassification,
    SecretStatus,
    certify_identity_platform,
    identity_governance_payload,
)
from backend.security.identity.identity_api import create_identity_security_router
from backend.security.identity.identity_reporting import REPORT_TITLES, build_identity_report_suite
from backend.security.security_api_auth import SecurityAPIAdminDependency
from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_crypto import StaticKeyProvider, VaultCrypto
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, resolve_section_slug


def _platform():
    vault = CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"i" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )
    identities = EnterpriseIdentityService()
    secrets = EnterpriseSecretService(vault=vault)
    admin = identities.register(
        identity_id="phase179a-admin",
        display_name="Phase 179A Admin",
        identity_type=IdentityType.HUMAN,
        role="SUPER_USER",
        owner="platform-security",
        environment="TEST",
    )
    viewer = identities.register(
        identity_id="phase179a-viewer",
        display_name="Phase 179A Viewer",
        identity_type=IdentityType.HUMAN,
        role="VIEWER",
        owner="platform-security",
        environment="TEST",
    )
    return identities, secrets, admin, viewer


def _register_secret(secrets: EnterpriseSecretService, *, secret_type: str = "QUESTRADE_REFRESH_TOKEN"):
    material = bytearray(b"synthetic-phase179a-material")
    metadata = secrets.register(
        material,
        provider="ENTERPRISE_VAULT",
        secret_type=secret_type,
        owner="platform-security",
        environment="TEST",
        operator="phase179a-admin",
        broker="QUESTRADE",
    )
    assert material == bytearray(len(material))
    return metadata


def test_secret_handle_metadata_and_classification_defaults() -> None:
    identities, secrets, admin, _ = _platform()
    refresh = _register_secret(secrets)
    assert refresh.classification is SecretClassification.TOP_SECRET
    assert refresh.secret_uuid.startswith("SUUID-")
    assert refresh.vcid.startswith("VCID-BRK-QT-")
    result = secrets.retrieve(
        refresh.secret_uuid,
        request=SecretAccessRequest(
            identity=admin,
            purpose="BROKER_ADAPTER_METADATA_BINDING",
            component="QuestradeBrokerAdapter",
            duration_seconds=60,
        ),
    )
    assert result["classification"] == "TOP_SECRET"
    assert result["plaintext_returned"] is False
    assert "synthetic-phase179a-material" not in str(result)
    assert {"handle", "metadata", "fingerprint", "hash", "classification"} <= set(result)

    api_key = secrets.register(
        bytearray(b"another-synthetic-value"),
        provider="ENTERPRISE_VAULT",
        secret_type="API_KEY",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
        broker="COINBASE",
    )
    assert api_key.classification is SecretClassification.HIGHLY_RESTRICTED


@pytest.mark.parametrize("classification", list(SecretClassification))
def test_all_secret_classifications_are_supported(classification: SecretClassification) -> None:
    _, secrets, admin, _ = _platform()
    metadata = secrets.register(
        bytearray(f"synthetic-{classification.value}".encode()),
        provider="ENTERPRISE_VAULT",
        secret_type="GENERIC_SECRET",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
        classification=classification,
    )
    assert metadata.classification is classification
    assert metadata.as_dict()["secret_values_returned"] is False


def test_duplicate_discovery_and_registration_are_blocked() -> None:
    _, secrets, admin, _ = _platform()
    _register_secret(secrets)
    duplicate = bytearray(b"synthetic-phase179a-material")
    with pytest.raises(DuplicateSecretError, match="DUPLICATE_SECRET_FINGERPRINT"):
        secrets.register(
            duplicate,
            provider="SECOND_PROVIDER",
            secret_type="API_KEY",
            owner="platform-security",
            environment="TEST",
            operator=admin.identity_id,
        )
    assert duplicate == bytearray(len(duplicate))

    discovery = EnterpriseSecretDiscovery(secrets)
    report = discovery.register_mapping(
        "environment",
        {
            "OANDA_API_KEY": "synthetic-discovery-value",
            "NORMAL_SETTING": "ignored",
        },
        provider="ENTERPRISE_VAULT",
        owner="platform-security",
        environment="TEST",
        operator=admin.identity_id,
    )
    assert len(report["results"]) == 1
    assert report["results"][0]["registered"] is True
    assert "synthetic-discovery-value" not in str(report)


def test_access_policy_and_immutable_audit() -> None:
    _, secrets, admin, viewer = _platform()
    metadata = _register_secret(secrets)
    with pytest.raises(PermissionError, match="ROLE_NOT_AUTHORIZED"):
        secrets.retrieve(
            metadata.secret_uuid,
            request=SecretAccessRequest(
                identity=viewer,
                purpose="UNAUTHORIZED_METADATA_REQUEST",
                component="test",
                duration_seconds=60,
            ),
        )
    secrets.retrieve(
        metadata.secret_uuid,
        request=SecretAccessRequest(
            identity=admin,
            purpose="CERTIFICATION",
            component="identity-certifier",
            duration_seconds=30,
        ),
    )
    entries = secrets.audit.entries(resource_id=metadata.secret_uuid)
    assert isinstance(entries, tuple)
    assert [entry.result for entry in entries] == ["DENIED", "SUCCESS"]
    assert not hasattr(secrets.audit, "delete")
    assert all(
        entry.who
        and entry.timestamp
        and entry.why
        and entry.component
        and entry.reason
        and entry.result
        for entry in entries
    )


def test_rotation_risk_dependency_and_status_governance() -> None:
    _, secrets, admin, _ = _platform()
    metadata = _register_secret(secrets)
    secrets.register_dependency(metadata.secret_uuid, "Broker Adapter", safe_to_pause=False)
    impact = secrets.rotation_impact(metadata.secret_uuid)
    assert impact["blocked_rotation"] is True
    assert impact["automatic_rotation"] is False
    rotation = secrets.rotation_status(
        now=datetime.now(timezone.utc) + timedelta(days=100)
    )
    row = next(item for item in rotation["secrets"] if item["secret_uuid"] == metadata.secret_uuid)
    assert row["effective_status"] == "ROTATION_DUE"
    compromised = secrets.set_status(
        metadata.secret_uuid,
        SecretStatus.COMPROMISED,
        operator=admin.identity_id,
        operator_role=admin.role,
        reason="SYNTHETIC_TEST_EVENT",
    )
    assert compromised.risk_score >= 80
    assert secrets.risk_summary()["high_risk_count"] == 1
    with pytest.raises(PermissionError, match="SECRET_COMPROMISED"):
        secrets.retrieve(
            metadata.secret_uuid,
            request=SecretAccessRequest(
                identity=admin,
                purpose="COMPROMISED_SECRET_TEST",
                component="test",
                duration_seconds=30,
            ),
        )


def test_certification_is_honest_about_legacy_broker_migration() -> None:
    identities, secrets, _, _ = _platform()
    _register_secret(secrets)
    blocked = certify_identity_platform(identities, secrets)
    assert blocked["outcome"] == "NOT_CERTIFIED"
    assert blocked["remaining_blockers"] == ["broker_handle_only_migration_complete"]
    certified = certify_identity_platform(
        identities,
        secrets,
        legacy_broker_migration_complete=True,
    )
    assert certified["outcome"] == "CERTIFIED"
    assert certified["execution_allowed"] is False


def test_reports_are_a4_paginated_and_viewer_compatible() -> None:
    identities, secrets, _, _ = _platform()
    _register_secret(secrets)
    reports = build_identity_report_suite(identities=identities, secrets=secrets)
    assert set(reports) == set(REPORT_TITLES)
    for report in reports.values():
        document = report["document"]
        assert document["presentation"]["page_size"] == "A4"
        assert document["pages"][0]["page_type"] == "cover"
        assert any(page["page_type"] == "toc" for page in document["pages"])
        assert report["report_id"]
        assert report["viewer_compatible"] is True
        assert report["execution_allowed"] is False
        assert "synthetic-phase179a-material" not in str(report)


def test_get_only_security_api_and_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    identities, secrets, _, _ = _platform()
    metadata = _register_secret(secrets)
    app = FastAPI()
    router = create_identity_security_router(identities=identities, secrets=secrets)
    app.include_router(router)
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    assert client.get("/api/security/secrets").status_code == 403
    assert client.get(
        "/api/security/secrets",
        headers={"x-css-user-id": "unsupported", "x-css-role": "ANALYST"},
    ).status_code == 403
    headers = {"x-css-user-id": "phase179a-admin", "x-css-role": "SUPER_USER"}
    admin_headers = {"x-css-user-id": "phase179a-admin-2", "x-css-role": "ADMIN"}
    assert client.get("/api/security/identity", headers=admin_headers).status_code == 200
    for path in (
        "/api/security/identity",
        "/api/security/secrets",
        f"/api/security/secrets/{metadata.secret_uuid}",
        "/api/security/rotation",
        "/api/security/certification",
        "/api/security/risk",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        assert "synthetic-phase179a-material" not in response.text
    for route in router.routes:
        assert route.methods == {"GET"}
    audited_resources = {entry.resource_id for entry in secrets.audit.entries()}
    assert "SECRET_INVENTORY" in audited_resources
    assert metadata.secret_uuid in audited_resources
    assert client.post("/api/security/secrets", headers=headers).status_code == 405
    assert client.delete(f"/api/security/secrets/{metadata.secret_uuid}", headers=headers).status_code == 405


def test_security_auth_dependency_precedes_business_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    require_admin = SecurityAPIAdminDependency("security_auth_contract_test")

    @app.get("/security-auth-contract")
    def validated_business_request(
        limit: int,
        _auth=Depends(require_admin),
    ):
        return {"limit": limit}

    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    assert client.get("/security-auth-contract").status_code == 403
    headers = {"x-css-user-id": "phase179a-admin", "x-css-role": "ADMIN"}
    assert client.get(
        "/security-auth-contract?limit=invalid",
        headers=headers,
    ).status_code == 422
    assert client.get("/security-auth-contract?limit=1", headers=headers).status_code == 200


def test_mission_control_identity_governance_is_read_only() -> None:
    identities, secrets, _, _ = _platform()
    metadata = _register_secret(secrets)
    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "identity_governance": identity_governance_payload(identities, secrets),
    }
    html = render_mission_control_shell(state, active_section="enterprise_identity")
    assert "Enterprise Identity &amp; Secrets" in html
    assert metadata.secret_uuid in html
    assert "synthetic-phase179a-material" not in html
    assert resolve_section_slug("enterprise-identity").key == "enterprise_identity"
    assert len(MISSION_CONTROL_SECTIONS) == 16
    denied = render_mission_control_shell({}, active_section="enterprise_identity")
    assert metadata.secret_uuid not in denied
    assert "Administrator authentication is required" in denied
