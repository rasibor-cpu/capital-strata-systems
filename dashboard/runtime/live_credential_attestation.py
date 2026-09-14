from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.app.brokers.credential_loader import load_credentials
from backend.app.brokers.broker_registry import list_supported_brokers


REQUIRED_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "coinbase": (
        ("name", "key_name", "api_key_name", "COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY"),
        ("privateKey", "private_key", "COINBASE_CDP_PRIVATE_KEY", "COINBASE_PRIVATE_KEY", "COINBASE_API_SECRET"),
    ),
    "oanda": (
        ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN"),
        ("OANDA_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID"),
    ),
    "alpaca": (
        ("ALPACA_API_KEY", "APCA_API_KEY_ID"),
        ("ALPACA_API_SECRET", "APCA_API_SECRET_KEY"),
    ),
}

PATH_KEY_MARKERS = ("path", "file", "pem")
EXPIRY_KEYS = ("expires_at_utc", "EXPIRES_AT_UTC", "expiry_utc", "EXPIRY_UTC")
ROTATION_KEYS = ("rotated_at_utc", "ROTATED_AT_UTC", "rotation_date", "ROTATION_DATE")


def _group_present(credentials: Mapping[str, Any], aliases: tuple[str, ...]) -> bool:
    return any(bool(credentials.get(key)) for key in aliases)


def _parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def attest_live_credentials(
    broker_name: str,
    *,
    base_dir: str | Path = ".",
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    broker = str(broker_name or "").strip().lower()
    now = now_utc or datetime.now(timezone.utc)
    credentials = load_credentials(broker, mode="live", base_dir=str(base_dir)) or {}
    groups = REQUIRED_GROUPS.get(broker, ())

    group_results = [_group_present(credentials, aliases) for aliases in groups]
    required_fields_ready = bool(groups) and all(group_results)

    path_refs = []
    for key, value in credentials.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in PATH_KEY_MARKERS) and value:
            text = str(value)
            if "BEGIN " in text:
                path_refs.append(True)
            else:
                path_refs.append(os.path.exists(text))

    expiry = next((_parse_utc(credentials.get(key)) for key in EXPIRY_KEYS if credentials.get(key)), None)
    rotation = next((_parse_utc(credentials.get(key)) for key in ROTATION_KEYS if credentials.get(key)), None)
    expired = bool(expiry and expiry <= now)

    warnings: list[str] = []
    if credentials and expiry is None:
        warnings.append("EXPIRY_METADATA_UNAVAILABLE")
    if credentials and rotation is None:
        warnings.append("ROTATION_METADATA_UNAVAILABLE")
    if expired:
        warnings.append("CREDENTIAL_EXPIRED")
    if path_refs and not all(path_refs):
        warnings.append("CREDENTIAL_PATH_UNAVAILABLE")

    ready = bool(credentials) and required_fields_ready and not expired and all(path_refs or [True])
    return {
        "payload_version": "css.live_credential_attestation.v1",
        "broker": broker,
        "status": "READY" if ready else "NOT_READY",
        "credentials_present": bool(credentials),
        "required_fields_ready": required_fields_ready,
        "credential_path_checks_passed": all(path_refs or [True]),
        "expiry_metadata_present": expiry is not None,
        "rotation_metadata_present": rotation is not None,
        "expired": expired,
        "warnings": warnings,
        "secret_values_included": False,
        "local_paths_included": False,
        "execution_allowed": False,
        "read_only": True,
    }


def build_live_credential_attestation_payload(*, base_dir: str | Path = ".") -> dict[str, Any]:
    reports = [attest_live_credentials(name, base_dir=base_dir) for name in list_supported_brokers()]
    return {
        "payload_version": "css.live_credential_attestation_collection.v1",
        "reports": reports,
        "secret_values_included": False,
        "local_paths_included": False,
        "execution_allowed": False,
        "read_only": True,
    }


__all__ = [
    "REQUIRED_GROUPS",
    "attest_live_credentials",
    "build_live_credential_attestation_payload",
]
