"""Phase 193 — offline operational qualification precheck (no auth / no HTTP)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.audit_matrix import (
    BROKER_AUDIT_MATRIX,
    get_capability_profile,
)
from backend.app.brokers.multi_broker_readiness.precheck import (
    ACCOUNT_KEYS,
    CREDENTIAL_KEYS,
    ENDPOINT_KEYS,
    run_controlled_online_precheck,
)
from backend.app.brokers.multi_broker_readiness.rc004 import evaluate_rc004_readiness
from backend.app.governance.enterprise_certification_registry.claim import (
    CertificationClaimError,
    assert_valid_certification_claim,
)
from backend.app.governance.enterprise_certification_registry.models import CertificationRegistryEntry
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository
from backend.app.governance.enterprise_certification_registry.seed import seed_phase_registry

FRAMEWORK_VERSION = "193.1"
SCHEMA_VERSION = "193.1"
EXPECTED_PROVIDER_FRAMEWORK = "MULTI_BROKER_OPERATIONAL_READINESS_FRAMEWORK"

SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret",
    "Authorization: Bearer",
    "refresh_token=",
)


@dataclass(frozen=True)
class OperationalQualificationPrecheck:
    schema_id: str = "OPERATIONAL_QUALIFICATION_PRECHECK"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    asset_class: str = ""
    status: str = "BLOCKED"
    credentials_configured: bool = False
    endpoint_configured: bool = False
    provider_compatible: bool = False
    schema_compatible: bool = False
    capability_profile_ok: bool = False
    registry_entry_ok: bool = False
    governance_aligned: bool = False
    rc004_live_denied: bool = False
    authorization_ttl_classified: bool = False
    authentication_performed: bool = False
    network_contact_performed: bool = False
    execution_authority: bool = False
    blockers: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["authentication_performed"] = False
        payload["network_contact_performed"] = False
        payload["execution_authority"] = False
        return payload

    def __post_init__(self) -> None:
        if self.authentication_performed:
            raise ValueError("precheck must not authenticate")
        if self.network_contact_performed:
            raise ValueError("precheck must not contact network")
        if self.execution_authority:
            raise ValueError("precheck must not grant execution_authority")


def _env_has_any(env: Mapping[str, Any], keys: Sequence[str]) -> bool:
    for key in keys:
        value = env.get(key)
        if value is None:
            continue
        if str(value).strip():
            return True
    return False


def _registry_id_for(broker: str) -> str:
    return f"broker:{broker.upper()}"


def run_operational_qualification_precheck(
    broker: str,
    env: Mapping[str, Any] | None = None,
    *,
    asset_class: str = "",
    repository: RegistryRepository | None = None,
    expected_schema_version: str = "189.1",
    expected_provider_name: str = "",
    expected_provider_version: str = "",
    expected_min_generation: int = 1,
    repo_root: Any = None,
) -> OperationalQualificationPrecheck:
    """Deterministic offline validation only — no HTTP, sockets, or authentication."""
    broker_key = str(broker or "").upper()
    source = dict(env or {})
    blockers: list[str] = []
    diagnostics: dict[str, Any] = {
        "redacted": True,
        "authentication_performed": False,
        "network_contact_performed": False,
        "credential_keys_checked": list(CREDENTIAL_KEYS.get(broker_key, ())),
        "endpoint_keys_checked": list(ENDPOINT_KEYS.get(broker_key, ())),
        "secret_values_captured": False,
    }

    audit = BROKER_AUDIT_MATRIX.get(broker_key)
    profile = get_capability_profile(broker_key)
    capability_ok = bool(profile.broker_type) and profile.execution_authority is False
    if not capability_ok:
        blockers.append("capability_profile_invalid")

    provider_compatible = False
    if audit is None:
        blockers.append("unknown_broker")
    else:
        classification = str(audit.get("classification", "NOT_STARTED"))
        provider_compatible = classification in {"COMPLETE", "PARTIAL"}
        if classification == "BLOCKED":
            blockers.append(f"broker_blocked:{broker_key}")
            provider_compatible = False
        if classification == "NOT_STARTED":
            blockers.append(f"broker_ops_not_started:{broker_key}")

    # Reuse Phase 189 precheck surface (still no auth).
    base = run_controlled_online_precheck(
        broker_key,
        source,
        asset_class=asset_class or "NONE",
        expected_schema_version=expected_schema_version,
    )
    credentials_configured = _env_has_any(source, CREDENTIAL_KEYS.get(broker_key, ()))
    endpoint_configured = _env_has_any(source, ENDPOINT_KEYS.get(broker_key, ()))
    if not credentials_configured:
        blockers.append("credentials_not_configured")
    if not endpoint_configured:
        blockers.append("endpoint_not_configured")

    schema_compatible = expected_schema_version.startswith(("187", "188", "189", "190", "191", "192", "193"))
    if not schema_compatible:
        blockers.append("schema_incompatible")

    # Asset scope (declared only).
    asset_key = str(asset_class or "").upper()
    if asset_key and asset_key not in {"", "NONE", "MULTI"}:
        if not profile.supports_asset_class(asset_key):
            blockers.append(f"asset_scope_incompatible:{asset_key}")

    # Registry + claim guard.
    repo = repository if repository is not None else seed_phase_registry()
    registry_ok = False
    registry_entry: CertificationRegistryEntry | None = None
    registry_id = _registry_id_for(broker_key)
    try:
        registry_entry = assert_valid_certification_claim(repo, registry_id=registry_id)
        registry_ok = True
        if registry_entry.certification_generation < int(expected_min_generation):
            blockers.append("stale_registry_generation")
            registry_ok = False
        if expected_provider_name and registry_entry.provider_name != expected_provider_name:
            blockers.append("provider_fingerprint_mismatch:name")
            registry_ok = False
        if expected_provider_version and registry_entry.provider_version != expected_provider_version:
            blockers.append("provider_fingerprint_mismatch:version")
            registry_ok = False
        if asset_key and registry_entry.asset_class and asset_key not in {
            registry_entry.asset_class.upper(),
            "MULTI",
            "NONE",
        }:
            if registry_entry.asset_class.upper() != "MULTI":
                blockers.append("registry_asset_scope_inconsistent")
                registry_ok = False
        if registry_entry.execution_authority:
            blockers.append("registry_execution_authority_forbidden")
            registry_ok = False
    except CertificationClaimError as exc:
        blockers.append(f"registry_claim_invalid:{exc}")
        registry_ok = False

    # RC-004 posture — live must remain denied.
    rc004 = evaluate_rc004_readiness(broker_key, repo_root=repo_root)
    rc004_live_denied = (
        rc004.live_trading_authorized is False
        and rc004.explicit_statement == "LIVE_TRADING_NOT_AUTHORIZED"
    )
    if not rc004_live_denied:
        blockers.append("rc004_live_not_denied")

    # Authorization TTL classification (RO TTL ≠ live authority).
    ttl_status = "NONE"
    if registry_entry is not None:
        ttl_status = registry_entry.authorization_ttl_status or "NONE"
    ttl_classified = ttl_status in {"NONE", "ACTIVE", "EXPIRED", "N/A"}
    if not ttl_classified:
        blockers.append("authorization_ttl_unclassified")
    diagnostics["authorization_ttl_status"] = ttl_status
    diagnostics["read_only_ttl_is_not_live_authority"] = True
    diagnostics["rc004_status"] = rc004.status
    diagnostics["phase189_precheck_status"] = base.status
    diagnostics["account_keys_checked"] = list(ACCOUNT_KEYS.get(broker_key, ()))
    if registry_entry is not None:
        diagnostics["registry_id"] = registry_entry.registry_id
        diagnostics["registry_generation"] = registry_entry.certification_generation
        diagnostics["registry_provider_name"] = registry_entry.provider_name
        diagnostics["registry_provider_version"] = registry_entry.provider_version
        diagnostics["suspension_status"] = registry_entry.suspension_status

    governance_aligned = rc004_live_denied and ttl_classified and profile.execution_authority is False

    hard_block = any(
        b.startswith("broker_blocked:")
        or b.startswith("registry_claim_invalid:")
        or b == "stale_registry_generation"
        or b.startswith("provider_fingerprint_mismatch")
        or b == "rc004_live_not_denied"
        for b in blockers
    )

    status = "READY"
    if hard_block:
        status = "BLOCKED"
    elif not provider_compatible or not registry_ok or not capability_ok:
        status = "BLOCKED"
    elif not credentials_configured or not endpoint_configured:
        status = "PARTIAL"
    else:
        status = "READY"

    # Deduplicate blockers while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in blockers:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    return OperationalQualificationPrecheck(
        broker_type=broker_key,
        asset_class=asset_key or (registry_entry.asset_class if registry_entry else ""),
        status=status,
        credentials_configured=credentials_configured,
        endpoint_configured=endpoint_configured,
        provider_compatible=provider_compatible,
        schema_compatible=schema_compatible,
        capability_profile_ok=capability_ok,
        registry_entry_ok=registry_ok,
        governance_aligned=governance_aligned,
        rc004_live_denied=rc004_live_denied,
        authorization_ttl_classified=ttl_classified,
        authentication_performed=False,
        network_contact_performed=False,
        execution_authority=False,
        blockers=tuple(ordered),
        diagnostics=diagnostics,
    )
