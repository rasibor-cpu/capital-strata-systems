"""Phase 178E — ESMS-001 and ESMS-002 source-only certification."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.broker_reporting.page_layout import build_paginated_document
from backend.brokers.auth import (
    AuthorizationStateStore,
    BrokerOnboarding,
    CallbackValidator,
    OAuthManager,
    OnboardingState,
    TokenHealth,
    TokenLifecycleMetadata,
    TokenRefreshPlanner,
)
from backend.security.credential_dependency_map import CredentialDependencyMap
from backend.security.credential_discovery import CredentialDiscovery
from backend.security.credential_vault import CredentialVault, InMemoryEncryptedStorage
from backend.security.rotation_impact import analyze_rotation
from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_backup import VaultBackupManager
from backend.security.vault_certification import certify_vault, credential_governance_payload
from backend.security.vault_crypto import StaticKeyProvider, VaultCrypto
from backend.security.vault_models import CredentialHealth
from backend.security.vault_redaction import REDACTED, redact_value
from backend.security.vault_rotation import VaultRotationManager
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, resolve_section_slug


def _vault() -> CredentialVault:
    return CredentialVault(
        crypto=VaultCrypto(StaticKeyProvider(b"k" * 32)),
        storage=InMemoryEncryptedStorage(),
        audit=VaultAuditLog(),
    )


def _registered(vault: CredentialVault):
    material = bytearray(b"synthetic-test-credential")
    metadata = vault.register(
        material,
        broker="QUESTRADE",
        credential_type="REFRESH_TOKEN",
        owner="platform-security",
        operator="phase178e-test",
    )
    material[:] = b"\x00" * len(material)
    return metadata


def test_aes_256_encryption_integrity_and_corruption_detection() -> None:
    vault = _vault()
    metadata = _registered(vault)
    record = vault.storage.get(metadata.vcid)
    assert record is not None
    serialized = str(record.as_dict())
    assert "synthetic-test-credential" not in serialized
    assert record.metadata.encryption_algorithm == "AES-256-GCM"
    assert vault.validate_integrity(metadata.vcid)

    vault.storage.put(replace(record, record_sha256="0" * 64))
    assert vault.validate_integrity(metadata.vcid) is False


def test_vcid_metadata_handle_lease_and_zeroization() -> None:
    vault = _vault()
    metadata = _registered(vault)
    assert metadata.vcid == "VCID-BRK-QT-000001"
    with pytest.raises(PermissionError, match="CONSUMER_NOT_AUTHORIZED"):
        vault.issue_runtime_handle(
            metadata.vcid, consumer="UntrustedComponent", operator="phase178e-test"
        )
    vault.authorize_consumer(
        metadata.vcid,
        consumer="QuestradeBrokerAdapter",
        operator="phase178e-test",
    )
    handle = vault.issue_runtime_handle(
        metadata.vcid, consumer="QuestradeBrokerAdapter", operator="phase178e-test"
    )
    assert "synthetic-test-credential" not in repr(handle)
    with vault.open_runtime_lease(handle, consumer="QuestradeBrokerAdapter") as lease:
        assert bytes(lease) == b"synthetic-test-credential"
    assert bytes(lease) == b"\x00" * len(lease)
    assert "get_secret" not in {name.lower() for name in dir(vault)}


def test_discovery_encrypts_and_reports_references_without_deleting_sources() -> None:
    vault = _vault()
    source = {"QUESTRADE_REFRESH_TOKEN": "synthetic-migration-value", "NORMAL_SETTING": "safe"}
    report = CredentialDiscovery().migrate(
        "environment",
        source,
        vault=vault,
        owner="platform-security",
        operator="phase178e-test",
    )
    assert source["QUESTRADE_REFRESH_TOKEN"] == "synthetic-migration-value"
    assert report["original_sources_deleted"] is False
    assert report["entries"][0]["runtime_reference"].startswith("vault-handle:VCID-BRK-QT-")
    assert "synthetic-migration-value" not in str(report)
    assert "synthetic-migration-value" not in str(vault.inventory())


def test_rotation_backup_dependency_and_impact_analysis() -> None:
    vault = _vault()
    metadata = _registered(vault)
    graph = CredentialDependencyMap()
    graph.register(metadata.vcid, "Broker Adapter")
    graph.register(metadata.vcid, "Options Income")
    graph.register(metadata.vcid, "Risk Engine", safe_to_pause=False)
    blocked = analyze_rotation(metadata.vcid, graph)
    assert blocked.blocked_rotation is True
    assert blocked.rollback_available is True
    safe = analyze_rotation(metadata.vcid, graph, maintenance_window=True)
    assert safe.safe_rotation is True

    rotation = VaultRotationManager(vault).rotate(
        metadata.vcid, bytearray(b"replacement-test-value"), operator="phase178e-test"
    )
    assert rotation.new_version == 2
    assert vault.metadata(metadata.vcid).health is CredentialHealth.HEALTHY
    backup_metadata, body = VaultBackupManager(vault).create_manifest()
    assert backup_metadata.contains_plaintext is False
    assert VaultBackupManager.verify(body)
    assert body["restore_supported"] is False
    assert body["restore_performed"] is False
    assert body["execution_allowed"] is False
    assert body["advisory_only"] is True
    assert "replacement-test-value" not in str(body)


def test_vault_backup_restore_is_explicitly_unsupported_and_non_destructive() -> None:
    result = VaultBackupManager.restore_manifest({"records": []})

    assert result["status"] == "UNSUPPORTED"
    assert result["restore_performed"] is False
    assert result["production_filesystem_touched"] is False
    assert result["execution_allowed"] is False
    assert result["advisory_only"] is True


def test_vault_backup_manifest_rejects_tampering_and_plaintext_claims() -> None:
    vault = _vault()
    _registered(vault)

    _, body = VaultBackupManager(vault).create_manifest()
    assert VaultBackupManager.verify(body)

    tampered = dict(body)
    tampered["contains_plaintext"] = True
    assert VaultBackupManager.verify(tampered) is False

    tampered = dict(body)
    tampered["record_count"] = 99
    assert VaultBackupManager.verify(tampered) is False


def test_audit_redaction_and_enterprise_report_redaction() -> None:
    audit = VaultAuditLog()
    event = audit.record(
        operator="operator-1",
        service="Options Income",
        broker="QUESTRADE",
        credential_id="VCID-BRK-QT-000017",
        action="VALIDATE",
        success=True,
        reason_code="VALID",
    )
    assert set(event.as_dict()) == {
        "timestamp", "operator", "service", "broker", "credential_id",
        "correlation_id", "action", "success", "reason_code",
    }
    payload = redact_value(
        {
            "api_key": "one",
            "oauth_code": "two",
            "refresh_token": "three",
            "access_token": "four",
            "client_secret": "five",
            "private_key": "six",
            "password": "seven",
            "certificate": "eight",
            "account_number": "nine",
            "authorization": "Bearer ten",
        }
    )
    assert set(payload.values()) == {REDACTED}
    document = build_paginated_document(
        title="Redaction",
        report_id="TEST",
        css_version="178E",
        commit_reference=None,
        generated_at="2026-07-20T00:00:00Z",
        executive_summary=["authorization=Bearer secret-value"],
        sections=[("Credentials", {"client_secret": "secret-value", "safe": "visible"})],
    )
    assert "secret-value" not in str(document.as_dict())
    assert "visible" in str(document.as_dict())


def test_oauth_framework_state_replay_and_callback_guards() -> None:
    states = AuthorizationStateStore()
    manager = OAuthManager(states)
    preparation = manager.prepare(
        broker="QUESTRADE", callback_uri="https://localhost.example/oauth/callback"
    )
    assert preparation.metadata()["browser_launch_enabled"] is False
    assert preparation.metadata()["token_exchange_enabled"] is False
    assert preparation.state_value not in str(preparation.metadata())
    validator = CallbackValidator(
        states, approved_callbacks={"https://localhost.example/oauth/callback"}
    )
    with pytest.raises(PermissionError, match="DUPLICATE"):
        validator.validate_parameters(
            callback_uri="https://localhost.example/oauth/callback",
            state_id=preparation.state_id,
            parameters={"state": [preparation.state_value, preparation.state_value], "code": "synthetic-code"},
        )
    with pytest.raises(PermissionError, match="PROVIDER_RETURNED_ERROR"):
        validator.validate_parameters(
            callback_uri="https://localhost.example/oauth/callback",
            state_id=preparation.state_id,
            parameters={"error": "access_denied"},
        )
    result = validator.validate_parameters(
        callback_uri="https://localhost.example/oauth/callback",
        state_id=preparation.state_id,
        parameters={"state": preparation.state_value, "code": "synthetic-code"},
    )
    assert result.valid is True
    assert result.code_returned is False
    with pytest.raises(PermissionError, match="REPLAYED"):
        validator.validate(
            callback_uri="https://localhost.example/oauth/callback",
            state_id=preparation.state_id,
            state_value=preparation.state_value,
            authorization_code="synthetic-code",
        )


def test_token_lifecycle_and_broker_onboarding_are_offline() -> None:
    now = datetime.now(timezone.utc)
    token = TokenLifecycleMetadata(
        vcid="VCID-BRK-QT-000001",
        health=TokenHealth.HEALTHY,
        created=now.isoformat(),
        expiry=(now - timedelta(minutes=1)).isoformat(),
    )
    assessment = TokenRefreshPlanner().assess(token, now=now)
    assert assessment["health"] == "EXPIRED"
    assert assessment["refresh_allowed"] is False
    assert assessment["network_call_performed"] is False
    onboarding = BrokerOnboarding("QUESTRADE").transition(OnboardingState.METADATA_REGISTERED)
    onboarding = onboarding.transition(OnboardingState.AUTHORIZATION_REQUIRED)
    assert onboarding.oauth_performed is False
    assert onboarding.execution_allowed is False


def test_certification_and_mission_control_governance_are_metadata_only() -> None:
    vault = _vault()
    metadata = _registered(vault)
    graph = CredentialDependencyMap()
    graph.register(metadata.vcid, "Mission Control")
    certification = certify_vault(vault, dependency_map=graph)
    assert certification["standards"]["ESMS-001"] == "PASS"
    assert certification["standards"]["ESMS-002"] == "PASS"
    assert certification["execution_allowed"] is False

    state = {
        "authorization_context": {"authenticated": True, "active": True, "role": "SUPER_USER"},
        "reports_authorization": {},
        "credential_governance": credential_governance_payload(
            vault, dependency_map=graph, selected_vcid=metadata.vcid
        ),
    }
    html = render_mission_control_shell(state, active_section="credential_governance")
    assert "Credential Governance" in html
    assert metadata.vcid in html
    assert "synthetic-test-credential" not in html
    assert resolve_section_slug("credential-governance").key == "credential_governance"
    assert len(MISSION_CONTROL_SECTIONS) == 16
    denied = render_mission_control_shell(
        {"credential_governance": state["credential_governance"]},
        active_section="credential_governance",
    )
    assert metadata.vcid not in denied
    assert "Administrator authentication is required" in denied

    contract = build_mission_control_state(
        {
            "credential_governance": {
                "credential_inventory": [{"vcid": metadata.vcid, "credential_type": "REFRESH_TOKEN"}],
                "client_secret": "synthetic-value-that-must-not-render",
            }
        },
        allow_mock=True,
    )
    assert contract["credential_governance"]["credential_inventory"][0]["vcid"] == metadata.vcid
    assert contract["credential_governance"]["client_secret"] == REDACTED
    assert "synthetic-value-that-must-not-render" not in str(contract)


@pytest.mark.parametrize("broker", ["COINBASE", "BINANCE", "OANDA", "QUESTRADE", "FUTURE_BROKER"])
def test_vault_is_broker_independent(broker: str) -> None:
    vault = _vault()
    metadata = vault.register(
        bytearray(f"synthetic-{broker}".encode()),
        broker=broker,
        credential_type="API_CREDENTIAL",
        owner="platform-security",
        operator="phase178e-test",
    )
    assert metadata.broker == broker
    assert metadata.vcid.startswith("VCID-BRK-")
    assert vault.health().advisory_only is True
    assert vault.health().execution_allowed is False
