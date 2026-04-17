"""
Broker Credential Loader
Capital Strata Systems (CSS)

Purpose:
- Load broker credentials from controlled local files.
- Support broker-specific credential formats.
- Never print or expose secrets.
- Provide both:
    - load_credentials_for_broker(...)
    - load_credentials(...)

Rules:
- Fail closed if credential file is missing or invalid for live mode.
- Never log full credential contents.
- Only support registry-approved credential file patterns.
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


def _load_from_environment(broker_name: str) -> Dict[str, Any]:
    """
    Load credentials from environment variables as a safe fallback.

    This supports the existing CSS practice of keeping credentials in .env
    loaded by python-dotenv or the shell environment.
    """
    key = (broker_name or "").strip().lower()

    if key == "coinbase":
        return {
            "COINBASE_CDP_KEY_NAME": (os.getenv("COINBASE_CDP_KEY_NAME") or "").strip(),
            "COINBASE_CDP_PRIVATE_KEY_PATH": (os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH") or "").strip(),
            "COINBASE_KEY_NAME": (os.getenv("COINBASE_KEY_NAME") or "").strip(),
            "COINBASE_PRIVATE_KEY": (os.getenv("COINBASE_PRIVATE_KEY") or "").strip(),
            "COINBASE_PAPER_MODE": (os.getenv("COINBASE_PAPER_MODE") or "").strip(),
        }

    if key == "oanda":
        return {
            "OANDA_API_KEY": (os.getenv("OANDA_API_KEY") or "").strip(),
            "OANDA_ACCOUNT_ID": (os.getenv("OANDA_ACCOUNT_ID") or "").strip(),
            "OANDA_BASE_URL": (os.getenv("OANDA_BASE_URL") or "").strip(),
            "OANDA_ENV": (os.getenv("OANDA_ENV") or "").strip(),
        }

    if key == "alpaca":
        return {
            "ALPACA_API_KEY": (os.getenv("ALPACA_API_KEY") or "").strip(),
            "ALPACA_SECRET_KEY": (os.getenv("ALPACA_SECRET_KEY") or "").strip(),
            "ALPACA_BASE_URL": (os.getenv("ALPACA_BASE_URL") or "").strip(),
            "ALPACA_PAPER": (os.getenv("ALPACA_PAPER") or "").strip(),
        }

    if key in {"futures_sim", "futures"}:
        return {"mode": "paper"}

    return {}


def _has_any_value(payload: Dict[str, Any]) -> bool:
    return any(str(v or "").strip() for v in payload.values())


def load_credentials_for_broker(
    broker_name: str,
    base_dir: str = ".",
    allow_env_fallback: bool = True,
    fail_if_missing: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Load credentials for the selected broker using registry metadata.

    Args:
        broker_name: Normalized broker name, e.g. coinbase, oanda, alpaca.
        base_dir: Directory where credential files are expected.
        allow_env_fallback: Use environment variables if file is missing.
        fail_if_missing: Raise CredentialLoadError if no credentials found.

    Returns:
        Dict[str, Any] or None.
    """
    spec = get_broker_spec(broker_name)

    if not spec.credential_file:
        return {"mode": "paper"}

    credential_path = os.path.join(base_dir, spec.credential_file)

    try:
        if spec.credential_file.endswith(".json"):
            return _load_json_file(credential_path)
        return _load_env_style_file(credential_path)
    except CredentialLoadError:
        if not allow_env_fallback:
            if fail_if_missing:
                raise
            return None

    env_payload = _load_from_environment(spec.name)
    if _has_any_value(env_payload):
        return env_payload

    if fail_if_missing:
        raise CredentialLoadError(
            f"No credentials found for broker '{broker_name}' via file or environment."
        )

    return None


def load_credentials(
    broker_name: str,
    mode: str = "paper",
    base_dir: str = ".",
) -> Optional[Dict[str, Any]]:
    """
    Compatibility wrapper used by broker_bootstrap.py.

    In paper mode:
    - Missing credentials are allowed.

    In live mode:
    - Missing credentials fail closed.
    """
    mode_key = (mode or "paper").strip().lower()
    fail = mode_key == "live"

    return load_credentials_for_broker(
        broker_name=broker_name,
        base_dir=base_dir,
        allow_env_fallback=True,
        fail_if_missing=fail,
    )


def credential_file_exists(
    broker_name: str,
    base_dir: str = ".",
) -> bool:
    """
    Return True if the expected credential file exists for the broker.
    """
    spec = get_broker_spec(broker_name)
    if not spec.credential_file:
        return True
    credential_path = os.path.join(base_dir, spec.credential_file)
    return os.path.exists(credential_path)