"""Phase 179B — certification-first Enterprise OAuth Manager."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security.credential_vault import CredentialVault, InMemoryEncryptedStorage
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.oauth import (
    DuplicateOAuthRegistration,
    EnterpriseOAuthManager,
    OAuthDiscovery,
    OAuthProvider,
    OAuthStatus,
    OAuthTokenType,
    certify_oauth_manager,
    oauth_governance_payload,
)
from backend.security.oauth.oauth_api import create_oauth_security_router
from backend.security.oauth.oauth_reporting import OAUTH_REPORT_TITLES, build_oauth_report_suite
from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_crypto import StaticKeyProvider, VaultCrypto
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, resolve_section_slug


def _platform():
    vault = CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"o" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )
    secrets = EnterpriseSecretService(vault=vault)
    manager = EnterpriseOAuthManager(secrets=secrets)
    return secrets, manager


def _secret(secrets: EnterpriseSecretService, name: str):
    return secrets.register(
        bytearray(f"synthetic-phase179b-{name}".encode()),
        provider="ENTERPRISE_VAULT",
        secret_type=name,
        owner="platform-security",
        environment="TEST",
        operator="phase179b-admin",
        broker="QUESTRADE",
    )


def _registration(manager: EnterpriseOAuthManager, secrets: EnterpriseSecretService):
    client_id = _secret(secrets, "OAUTH_CLIENT_ID")
    client_secret = _secret(secrets, "OAUTH_CLIENT_SECRET")
    return manager.register(
        provider=OAuthProvider.QUESTRADE,
        environment="TEST",
        owner="platform-security",
        scopes=("read", "accounts"),
        token_type=OAuthTokenType.AUTHORIZATION_CODE,
        client_id_secret_uuid=client_id.secret_uuid,
        client_secret_uuid=client_secret.secret_uuid,
        redirect_uri="https://css.example.test/oauth/callback",
        pkce_configured=True,
    )


def test_provider_registry_and_opaque_handle_model() -> None:
    secrets, manager = _platform()
    registration = _registration(manager, secrets)
    assert {row["provider"] for row in manager.registry.inventory()} == {
        provider.value for provider in OAuthProvider
    }
    assert registration.status is OAuthStatus.REGISTERED
    handle = manager.handle(registration.oauth_id)
    assert handle["handle"].startswith("OH-")
    assert all(value.startswith("secret-handle:SUUID-") for value in handle["secret_handles"])
    assert handle["plaintext_tokens_returned"] is False
    assert handle["authorization_enabled"] is False
    assert "synthetic-phase179b" not in str(handle)


def test_state_machine_blocks_live_authorization_and_refresh() -> None:
    secrets, manager = _platform()
    registration = _registration(manager, secrets)
    pending = manager.transition(
        registration.oauth_id,
        OAuthStatus.AUTHORIZATION_PENDING,
        reason="OFFLINE_READINESS_REVIEW",
    )
    assert pending.status is OAuthStatus.AUTHORIZATION_PENDING
    with pytest.raises(PermissionError, match="LIVE_AUTHORIZATION_PROHIBITED"):
        manager.transition(
            registration.oauth_id,
            OAuthStatus.AUTHORIZED,
            reason="MUST_NOT_AUTHORIZE",
        )
    disabled = manager.transition(
        registration.oauth_id,
        OAuthStatus.DISABLED,
        reason="CERTIFICATION_SAFETY",
    )
    assert disabled.disabled is True
    assert all(not event.authorization_performed for event in manager.events.snapshot())
    assert all(not event.refresh_performed for event in manager.events.snapshot())


def test_duplicate_unsafe_redirect_scope_and_pkce_policy() -> None:
    secrets, manager = _platform()
    registration = _registration(manager, secrets)
    with pytest.raises(DuplicateOAuthRegistration):
        manager.register(
            provider="QUESTRADE",
            environment="TEST",
            owner="platform-security",
            redirect_uri="https://css.example.test/oauth/callback",
            pkce_configured=True,
        )
    client_id = _secret(secrets, "SECOND_OAUTH_CLIENT_ID")
    with pytest.raises(ValueError, match="UNSAFE_REDIRECT_URI"):
        manager.register(
            provider="GOOGLE",
            environment="TEST",
            owner="unsafe-owner",
            scopes=("openid",),
            client_id_secret_uuid=client_id.secret_uuid,
            redirect_uri="http://localhost/callback",
            pkce_configured=True,
        )
    with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
        manager.register(
            provider="MICROSOFT",
            environment="TEST",
            owner="scope-owner",
            scopes=("broker.trade.write",),
            client_id_secret_uuid=client_id.secret_uuid,
            redirect_uri="https://css.example.test/callback",
            pkce_configured=True,
        )
    incomplete = manager.register(
        provider="GOOGLE",
        environment="TEST",
        owner="pkce-owner",
        scopes=("openid",),
        client_id_secret_uuid=client_id.secret_uuid,
        redirect_uri="https://css.example.test/callback",
        pkce_configured=False,
    )
    assert incomplete.status is OAuthStatus.CONFIGURATION_REQUIRED
    assert incomplete.risk_score >= 70
    assert registration.oauth_id


def test_offline_discovery_reports_duplicate_and_policy_findings() -> None:
    secrets, manager = _platform()
    registration = _registration(manager, secrets)
    client_id = _secret(secrets, "DISCOVERED_CLIENT_ID")
    discovery = OAuthDiscovery(manager)
    result = discovery.discover(
        [
            {
                "provider": "QUESTRADE",
                "environment": "TEST",
                "owner": "platform-security",
            },
            {
                "provider": "GOOGLE",
                "environment": "TEST",
                "owner": "discovery-owner",
                "scopes": ["openid"],
                "client_id_secret_uuid": client_id.secret_uuid,
                "redirect_uri": "http://127.0.0.1/callback",
                "pkce_configured": False,
            },
        ]
    )
    assert result["results"][0]["issues"] == ["DUPLICATE_REGISTRATION"]
    assert "PKCE_REQUIRED" in result["results"][1]["issues"]
    assert "UNSAFE_REDIRECT_URI" in result["results"][1]["issues"]
    assert result["live_validation_performed"] is False
    assert result["authorization_performed"] is False
    assert registration.oauth_id


def test_certification_reports_and_mission_control_are_metadata_only() -> None:
    secrets, manager = _platform()
    _registration(manager, secrets)
    certification = certify_oauth_manager(manager)
    assert certification["outcome"] == "NOT_CERTIFIED"
    assert certification["checks"]["legacy_oauth_lifecycles_retired"] is False
    assert certification["checks"]["execution_blocked"] is True
    reports = build_oauth_report_suite(manager)
    assert set(reports) == set(OAUTH_REPORT_TITLES)
    for report in reports.values():
        assert report["document"]["presentation"]["page_size"] == "A4"
        assert report["viewer_compatible"] is True
        assert report["execution_allowed"] is False
        assert "synthetic-phase179b" not in str(report)
    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "oauth_governance": oauth_governance_payload(manager),
    }
    html = render_mission_control_shell(state, active_section="enterprise_oauth")
    assert "Enterprise OAuth" in html
    assert "QUESTRADE" in html
    assert "BLOCKED" in html
    assert "synthetic-phase179b" not in html
    assert resolve_section_slug("enterprise-oauth").key == "enterprise_oauth"
    assert len(MISSION_CONTROL_SECTIONS) == 16
    denied = render_mission_control_shell({}, active_section="enterprise_oauth")
    assert "Administrator authentication is required" in denied


def test_get_only_oauth_api(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets, manager = _platform()
    _registration(manager, secrets)
    app = FastAPI()
    router = create_oauth_security_router(manager=manager)
    app.include_router(router)
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "true")
    client = TestClient(app)
    assert client.get("/api/security/oauth").status_code == 403
    assert client.get(
        "/api/security/oauth",
        headers={"x-css-user-id": "unsupported", "x-css-role": "ANALYST"},
    ).status_code == 403
    headers = {"x-css-user-id": "phase179b-admin", "x-css-role": "SUPER_USER"}
    admin_headers = {"x-css-user-id": "phase179b-admin-2", "x-css-role": "ADMIN"}
    assert client.get("/api/security/oauth", headers=admin_headers).status_code == 200
    for path in (
        "/api/security/oauth",
        "/api/security/oauth/providers",
        "/api/security/oauth/QUESTRADE",
        "/api/security/oauth/certification",
        "/api/security/oauth/report",
        "/api/security/oauth/risk",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        assert "synthetic-phase179b" not in response.text
    assert all(route.methods == {"GET"} for route in router.routes)
    assert client.post("/api/security/oauth", headers=headers).status_code == 405
    assert client.delete("/api/security/oauth/QUESTRADE", headers=headers).status_code == 405
