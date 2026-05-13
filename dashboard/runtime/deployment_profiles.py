from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping


DEPLOYMENT_PROFILE_VERSION = "css.deployment.profiles.v1"


@dataclass(frozen=True)
class DeploymentProfile:
    name: str
    host: str
    port: int
    allow_lan: bool
    allow_live_mode: bool
    require_tls: bool
    require_persistent_sessions: bool
    require_db_users: bool
    description: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILES: Dict[str, DeploymentProfile] = {
    "local_desktop": DeploymentProfile(
        name="local_desktop",
        host="127.0.0.1",
        port=8000,
        allow_lan=False,
        allow_live_mode=False,
        require_tls=False,
        require_persistent_sessions=True,
        require_db_users=False,
        description="Single-machine paper-first desktop profile.",
    ),
    "lan_mobile": DeploymentProfile(
        name="lan_mobile",
        host="0.0.0.0",
        port=8000,
        allow_lan=True,
        allow_live_mode=False,
        require_tls=False,
        require_persistent_sessions=True,
        require_db_users=False,
        description="Trusted LAN/mobile access profile; paper-first by default.",
    ),
    "vps_cloud": DeploymentProfile(
        name="vps_cloud",
        host="0.0.0.0",
        port=8443,
        allow_lan=True,
        allow_live_mode=False,
        require_tls=True,
        require_persistent_sessions=True,
        require_db_users=True,
        description="Cloud test profile with TLS and persistent identity requirements.",
    ),
    "production": DeploymentProfile(
        name="production",
        host="0.0.0.0",
        port=8443,
        allow_lan=True,
        allow_live_mode=True,
        require_tls=True,
        require_persistent_sessions=True,
        require_db_users=True,
        description="Restricted live-capable production profile.",
    ),
}


def get_deployment_profiles() -> dict[str, Any]:
    return {
        "payload_version": DEPLOYMENT_PROFILE_VERSION,
        "profiles": {name: profile.as_dict() for name, profile in PROFILES.items()},
    }


def get_deployment_profile(name: str) -> dict[str, Any]:
    key = str(name or "").strip().lower()
    if key not in PROFILES:
        raise KeyError(f"Unknown CSS deployment profile: {name}")
    return PROFILES[key].as_dict()


def validate_deployment_environment(
    profile_name: str,
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    profile = PROFILES[str(profile_name or "").strip().lower()]
    findings: list[str] = []

    if profile.require_tls and not _truthy(environment.get("tls_enabled")):
        findings.append("TLS_REQUIRED")
    if profile.require_persistent_sessions and not _truthy(environment.get("persistent_sessions")):
        findings.append("PERSISTENT_SESSIONS_REQUIRED")
    if profile.require_db_users and not _truthy(environment.get("db_users")):
        findings.append("DB_USER_STORE_REQUIRED")
    if profile.allow_live_mode and not _truthy(environment.get("kill_switch_available")):
        findings.append("LIVE_KILL_SWITCH_REQUIRED")

    return {
        "profile": profile.name,
        "ready": not findings,
        "findings": findings,
        "fail_closed": bool(findings),
    }


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"} or value is True
