
"""
Credential loading helpers for CSS broker bootstrap.

Credentials are read from broker-specific local files declared in the broker
registry. Values are returned to the caller but never printed or logged here.
Missing or malformed files fail closed.

PCNRASS update:
- Preserve existing registry-file loading.
- Add safe .env fallback for Coinbase and OANDA.
- Do not print secrets.
- Do not bypass governance gates.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

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


def _env_present(*names: str) -> bool:
    return any(bool(os.getenv(name)) for name in names)


def _load_coinbase_env_credentials() -> Optional[Dict[str, Any]]:
    load_dotenv()

    key_name = os.getenv("COINBASE_CDP_KEY_NAME") or os.getenv("COINBASE_KEY_NAME")
    private_key_path = (
        os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH")
        or os.getenv("COINBASE_PRIVATE_KEY_PATH")
        or os.getenv("COINBASE_PRIVATE_KEY")
    )
    key_file = os.getenv("COINBASE_KEY_FILE")

    if not key_name and not private_key_path and not key_file:
        return None

    credentials: Dict[str, Any] = {}

    if key_name:
        credentials["COINBASE_CDP_KEY_NAME"] = key_name
        credentials["COINBASE_KEY_NAME"] = key_name

    if private_key_path:
        credentials["COINBASE_CDP_PRIVATE_KEY_PATH"] = private_key_path
        credentials["COINBASE_PRIVATE_KEY_PATH"] = private_key_path
        credentials["COINBASE_PRIVATE_KEY"] = private_key_path

    if key_file:
        credentials["COINBASE_KEY_FILE"] = key_file

    credentials["COINBASE_ENABLE_LIVE_ORDERS"] = os.getenv(
        "COINBASE_ENABLE_LIVE_ORDERS", "false"
    )

    return credentials if credentials else None


def _load_oanda_env_credentials() -> Optional[Dict[str, Any]]:
    load_dotenv()

    token = (
        os.getenv("OANDA_API_KEY")
        or os.getenv("OANDA_ACCESS_TOKEN")
        or os.getenv("OANDA_TOKEN")
    )
    account_id = os.getenv("OANDA_ACCOUNT_ID") or os.getenv("OANDA_PRACTICE_ACCOUNT_ID")
    env = os.getenv("OANDA_ENV", "practice")

    if not token and not account_id:
        return None

    credentials: Dict[str, Any] = {}

    if token:
        credentials["OANDA_API_KEY"] = token
        credentials["OANDA_ACCESS_TOKEN"] = token
        credentials["OANDA_TOKEN"] = token

    if account_id:
        credentials["OANDA_ACCOUNT_ID"] = account_id
        credentials["OANDA_PRACTICE_ACCOUNT_ID"] = account_id

    credentials["OANDA_ENV"] = env
    credentials["OANDA_ENABLE_LIVE_ORDERS"] = os.getenv(
        "OANDA_ENABLE_LIVE_ORDERS", "false"
    )

    return credentials if credentials else None


def _load_env_fallback_credentials(broker_name: str) -> Optional[Dict[str, Any]]:
    broker = broker_name.strip().lower()

    if broker == "coinbase":
        return _load_coinbase_env_credentials()

    if broker == "oanda":
        return _load_oanda_env_credentials()

    return None


def load_credentials_for_broker(
    broker_name: str,
    base_dir: str = ".",
) -> Dict[str, Any]:
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)

    try:
        if spec.credential_file.endswith(".json"):
            return _load_json_file(credential_path)
        return _load_env_style_file(credential_path)
    except CredentialLoadError:
        env_credentials = _load_env_fallback_credentials(broker_name)
        if env_credentials:
            return env_credentials
        raise


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

    if os.path.exists(credential_path):
        return True

    return _load_env_fallback_credentials(broker_name) is not None
