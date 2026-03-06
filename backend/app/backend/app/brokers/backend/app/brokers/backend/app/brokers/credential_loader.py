"""
Broker Credential Loader
Capital Strata Systems (CSS)

Purpose:
- Load broker credentials from controlled local files.
- Support broker-specific credential formats.
- Never print or expose secrets.

Rules:
- Fail closed if credential file is missing or invalid.
- Never log full credential contents.
- Only support registry-approved credential file patterns.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

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
                raise CredentialLoadError(
                    f"Invalid credential line in {path}: '{raw_line.rstrip()}'"
                )
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
    """
    Load credentials for the selected broker using the registry metadata.

    Args:
        broker_name: Normalized broker name (e.g. coinbase, oanda, alpaca)
        base_dir: Directory where credential files are expected

    Returns:
        Dict[str, Any]: Loaded credential payload

    Raises:
        CredentialLoadError: If credentials cannot be loaded safely
    """
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)

    if spec.credential_file.endswith(".json"):
        return _load_json_file(credential_path)

    return _load_env_style_file(credential_path)


def credential_file_exists(
    broker_name: str,
    base_dir: str = ".",
) -> bool:
    """
    Return True if the expected credential file exists for the broker.
    """
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)
    return os.path.exists(credential_path)
