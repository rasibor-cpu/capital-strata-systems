"""
Credential loading helpers for CSS broker bootstrap.

Credentials are read from broker-specific local files declared in the broker
registry. Values are returned to the caller but never printed or logged here.
Missing or malformed files fail closed.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .broker_registry import get_broker_spec


class CredentialLoadError(Exception):
    """Raised when broker credentials cannot be loaded safely."""


def _load_json_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise CredentialLoadError(f"Credential file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CredentialLoadError(f"Invalid JSON credential file: {path}") from exc

    if not isinstance(data, dict):
        raise CredentialLoadError(f"Credential JSON must be an object: {path}")

    return data


def _load_env_style_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise CredentialLoadError(f"Credential file not found: {path}")

    credentials: Dict[str, Any] = {}

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise CredentialLoadError(f"Invalid credential line in {path}")

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise CredentialLoadError(f"Empty credential key in {path}")
            credentials[key] = value

    if not credentials:
        raise CredentialLoadError(f"No credentials found in file: {path}")

    return credentials


def load_credentials_for_broker(
    broker_name: str,
    base_dir: str = ".",
) -> Dict[str, Any]:
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)

    if spec.credential_file.endswith(".json"):
        return _load_json_file(credential_path)

    return _load_env_style_file(credential_path)


def load_credentials(
    broker_name: str,
    base_dir: str = ".",
) -> Optional[Dict[str, Any]]:
    try:
        return load_credentials_for_broker(broker_name, base_dir=base_dir)
    except CredentialLoadError:
        return None


def credential_file_exists(
    broker_name: str,
    base_dir: str = ".",
) -> bool:
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)
    return os.path.exists(credential_path)
