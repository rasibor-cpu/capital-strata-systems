from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION = "css.live_credential_attestation.v1"
LIVE_CREDENTIALS_ATTESTED = "LIVE_CREDENTIALS_ATTESTED"
LIVE_CREDENTIALS_INCOMPLETE = "LIVE_CREDENTIALS_INCOMPLETE"
LIVE_CREDENTIALS_NOT_CONFIGURED = "LIVE_CREDENTIALS_NOT_CONFIGURED"


@dataclass(frozen=True)
class CredentialRequirement:
    code: str
    env_keys: tuple[str, ...] = ()
    path_keys: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class CredentialRequirementResult:
    code: str
    present: bool
    source_keys: tuple[str, ...] = ()
    path_declared: bool = False
    path_exists: bool = False
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "present": self.present,
            "source_keys": list(self.source_keys),
            "path_declared": self.path_declared,
            "path_exists": self.path_exists,
            "message": self.message,
        }


@dataclass(frozen=True)
class BrokerCredentialAttestation:
    broker: str
    status: str
    requirements: tuple[CredentialRequirementResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "status": self.status,
            "requirement_count": len(self.requirements),
            "missing_requirement_count": sum(
                1 for requirement in self.requirements if not requirement.present
            ),
            "requirements": [
                requirement.as_dict() for requirement in self.requirements
            ],
        }


@dataclass(frozen=True)
class LiveCredentialAttestationReport:
    status: str
    broker_attestations: tuple[BrokerCredentialAttestation, ...]
    generated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION,
            "generated_utc": self.generated_utc,
            "status": self.status,
            "broker_count": len(self.broker_attestations),
            "ready_broker_count": sum(
                1
                for attestation in self.broker_attestations
                if attestation.status == LIVE_CREDENTIALS_ATTESTED
            ),
            "broker_attestations": [
                attestation.as_dict() for attestation in self.broker_attestations
            ],
            "security": {
                "contains_secret_values": False,
                "checks_are_local_only": True,
                "network_calls_performed": False,
            },
        }


BROKER_CREDENTIAL_REQUIREMENTS: Mapping[str, tuple[CredentialRequirement, ...]] = {
    "coinbase": (
        CredentialRequirement(
            code="coinbase_key_name",
            env_keys=(
                "COINBASE_CDP_KEY_NAME",
                "COINBASE_KEY_NAME",
                "COINBASE_API_KEY",
            ),
            message="Coinbase key name/API key identifier must be present.",
        ),
        CredentialRequirement(
            code="coinbase_private_key",
            env_keys=("COINBASE_API_SECRET", "COINBASE_PRIVATE_KEY"),
            path_keys=(
                "COINBASE_CDP_PRIVATE_KEY_PATH",
                "COINBASE_PRIVATE_KEY_PATH",
            ),
            message="Coinbase private key must be present as an env value or existing local file path.",
        ),
    ),
    "oanda": (
        CredentialRequirement(
            code="oanda_token",
            env_keys=(
                "OANDA_API_KEY",
                "OANDA_API_TOKEN",
                "OANDA_PRACTICE_TOKEN",
                "OANDA_LIVE_TOKEN",
            ),
            message="OANDA API token must be present.",
        ),
        CredentialRequirement(
            code="oanda_account_id",
            env_keys=(
                "OANDA_ACCOUNT_ID",
                "OANDA_PRACTICE_ACCOUNT_ID",
                "OANDA_LIVE_ACCOUNT_ID",
            ),
            message="OANDA account id must be present.",
        ),
    ),
    "alpaca": (
        CredentialRequirement(
            code="alpaca_key",
            env_keys=("ALPACA_API_KEY", "ALPACA_KEY_ID"),
            message="Alpaca API key must be present.",
        ),
        CredentialRequirement(
            code="alpaca_secret",
            env_keys=("ALPACA_API_SECRET", "ALPACA_SECRET_KEY"),
            message="Alpaca API secret must be present.",
        ),
    ),
}


def attest_live_credentials(
    *,
    brokers: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> LiveCredentialAttestationReport:
    env_map = env if env is not None else os.environ
    broker_names = tuple(
        _normalize_broker_name(name)
        for name in (brokers or tuple(BROKER_CREDENTIAL_REQUIREMENTS))
    )
    attestations = tuple(
        _attest_broker(name, env_map)
        for name in broker_names
        if name in BROKER_CREDENTIAL_REQUIREMENTS
    )
    return LiveCredentialAttestationReport(
        status=_report_status(attestations),
        broker_attestations=attestations,
    )


def build_live_credential_attestation_payload() -> dict[str, Any]:
    return attest_live_credentials().as_dict()


def _attest_broker(
    broker: str,
    env: Mapping[str, str],
) -> BrokerCredentialAttestation:
    results = tuple(
        _evaluate_requirement(requirement, env)
        for requirement in BROKER_CREDENTIAL_REQUIREMENTS[broker]
    )
    status = (
        LIVE_CREDENTIALS_ATTESTED
        if all(result.present for result in results)
        else LIVE_CREDENTIALS_INCOMPLETE
    )
    return BrokerCredentialAttestation(
        broker=broker,
        status=status,
        requirements=results,
    )


def _evaluate_requirement(
    requirement: CredentialRequirement,
    env: Mapping[str, str],
) -> CredentialRequirementResult:
    env_sources = tuple(key for key in requirement.env_keys if _has_value(env, key))
    path_sources = tuple(key for key in requirement.path_keys if _has_value(env, key))
    path_exists = any(_path_exists(env.get(key, "")) for key in path_sources)
    present = bool(env_sources or path_exists)
    return CredentialRequirementResult(
        code=requirement.code,
        present=present,
        source_keys=env_sources or path_sources,
        path_declared=bool(path_sources),
        path_exists=path_exists,
        message=requirement.message,
    )


def _report_status(
    attestations: Sequence[BrokerCredentialAttestation],
) -> str:
    if not attestations:
        return LIVE_CREDENTIALS_NOT_CONFIGURED
    if all(
        attestation.status == LIVE_CREDENTIALS_ATTESTED
        for attestation in attestations
    ):
        return LIVE_CREDENTIALS_ATTESTED
    return LIVE_CREDENTIALS_INCOMPLETE


def _normalize_broker_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_value(env: Mapping[str, str], key: str) -> bool:
    return bool(str(env.get(key, "") or "").strip())


def _path_exists(value: str) -> bool:
    try:
        return Path(str(value or "")).expanduser().exists()
    except Exception:
        return False


__all__ = [
    "BROKER_CREDENTIAL_REQUIREMENTS",
    "LIVE_CREDENTIALS_ATTESTED",
    "LIVE_CREDENTIALS_INCOMPLETE",
    "LIVE_CREDENTIALS_NOT_CONFIGURED",
    "LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION",
    "BrokerCredentialAttestation",
    "CredentialRequirement",
    "CredentialRequirementResult",
    "LiveCredentialAttestationReport",
    "attest_live_credentials",
    "build_live_credential_attestation_payload",
]
