"""
Credential loading helpers for CSS broker bootstrap.

Credentials are read from broker-specific local files declared in the broker
registry. Values are returned to the caller but never printed or logged here.
Missing or malformed files fail closed.

PCNRASS update:
- Preserve existing registry-file loading.
- Add safe .env fallback for Coinbase and OANDA.
- Add Coinbase JSON path compatibility for COINBASE_KEY_JSON_PATH,
  COINBASE_KEY_JSON, and COINBASE_KEY_FILE.
- Do not print secrets.
- Do not bypass governance gates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from dotenv import load_dotenv

from .broker_registry import get_broker_spec
from backend.runtime.broker_environment_profiles import (
    BrokerEnvironmentCredentials,
    build_broker_environment,
    profile_mode_alias,
)
from backend.runtime.environment_bootstrap import bootstrap_broker_environment


REPO_ROOT = Path(__file__).resolve().parents[3]


class CredentialLoadError(Exception):
    """Raised when broker credentials cannot be loaded safely."""

    pass


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


def _load_coinbase_json_credentials(path: str) -> Optional[Dict[str, Any]]:
    if not path:
        return None

    normalized_path = _resolve_credential_path(path)
    if not normalized_path:
        return None

    try:
        payload = _load_json_file(str(normalized_path))
    except CredentialLoadError:
        return None

    key_name = (
        payload.get("name")
        or payload.get("key_name")
        or payload.get("apiKey")
        or payload.get("key")
    )
    private_key = _normalize_coinbase_private_key_material(
        payload.get("privateKey")
        or payload.get("private_key")
        or payload.get("apiSecret")
        or payload.get("secret")
    )

    if not key_name or not private_key:
        return None

    return {
        "name": str(key_name),
        "key_name": str(key_name),
        "api_key_name": str(key_name),
        "privateKey": private_key,
        "private_key": private_key,
        "COINBASE_CDP_KEY_NAME": str(key_name),
        "COINBASE_KEY_NAME": str(key_name),
        "COINBASE_CDP_PRIVATE_KEY": private_key,
        "COINBASE_PRIVATE_KEY": private_key,
        "COINBASE_KEY_FILE": str(normalized_path),
        "COINBASE_KEY_JSON_PATH": str(normalized_path),
    }


def _resolve_credential_path(path: str) -> Optional[Path]:
    raw = str(path or "").strip().strip('"')
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    return candidate if candidate.exists() and candidate.is_file() else None


def _normalize_coinbase_private_key_material(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    path = _resolve_credential_path(raw)
    if path:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        if path.suffix.lower() == ".json" or content.lstrip().startswith("{"):
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None
            return _normalize_coinbase_private_key_material(
                payload.get("privateKey")
                or payload.get("private_key")
                or payload.get("apiSecret")
                or payload.get("secret")
            )
        return _normalize_pem_private_key(content)

    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return _normalize_coinbase_private_key_material(
            payload.get("privateKey")
            or payload.get("private_key")
            or payload.get("apiSecret")
            or payload.get("secret")
        )

    return _normalize_pem_private_key(raw)


def _normalize_pem_private_key(value: str) -> Optional[str]:
    normalized = (
        str(value or "")
        .replace("\ufeff", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\\n", "\n")
        .strip()
    )
    valid_begin = normalized.startswith("-----BEGIN EC PRIVATE KEY-----") or normalized.startswith("-----BEGIN PRIVATE KEY-----")
    valid_end = normalized.endswith("-----END EC PRIVATE KEY-----") or normalized.endswith("-----END PRIVATE KEY-----")
    if not (valid_begin and valid_end):
        return None
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    return "\n".join(lines)


def _env_present(*names: str) -> bool:
    return any(bool(os.getenv(name)) for name in names)


def _first_present(source: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = source.get(name)
        if value not in (None, ""):
            return value
    return None


def _load_coinbase_env_credentials(mode: str) -> Optional[Dict[str, Any]]:
    process_source = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("COINBASE_")
    }
    canonical = _canonical_profile_credentials("COINBASE", mode)
    source = canonical.credentials_for_broker()
    if any(
        Path(path).name in {".env.live_read_only", ".env.live_execution"}
        for path in canonical.loaded_files
    ):
        process_source = {}
    process_identity_present = bool(
        _first_present(
            process_source,
            "COINBASE_CDP_KEY_NAME",
            "COINBASE_KEY_NAME",
            "COINBASE_API_KEY",
        )
    )
    process_private_key_present = bool(
        _first_present(
            process_source,
            "COINBASE_CDP_PRIVATE_KEY",
            "COINBASE_PRIVATE_KEY",
            "COINBASE_CDP_PRIVATE_KEY_PATH",
            "COINBASE_PRIVATE_KEY_PATH",
            "COINBASE_KEY_JSON_PATH",
            "COINBASE_KEY_JSON",
            "COINBASE_KEY_FILE",
        )
    )
    if canonical.validation_status != "PASS" and not (
        canonical.key_identifier_present
        or canonical.private_key_present
        or (process_identity_present and process_private_key_present)
    ):
        return None

    process_key_files = tuple(
        process_source.get(name)
        for name in (
            "COINBASE_KEY_JSON_PATH",
            "COINBASE_KEY_JSON",
            "COINBASE_KEY_FILE",
        )
    )
    canonical_key_files = (
        source.get("COINBASE_KEY_JSON_PATH"),
        source.get("COINBASE_KEY_JSON"),
        source.get("COINBASE_KEY_FILE"),
    )
    key_file_candidates = (
        process_key_files
        if any(process_key_files)
        else (() if process_private_key_present else canonical_key_files)
    )
    for key_file in key_file_candidates:
        json_credentials = _load_coinbase_json_credentials(key_file or "")
        if json_credentials:
            json_credentials["COINBASE_ENABLE_LIVE_ORDERS"] = source.get("COINBASE_ENABLE_LIVE_ORDERS") or "false"
            json_credentials["canonical_broker_environment"] = canonical.redacted_diagnostics()
            return json_credentials

    key_name = _first_present(
        process_source,
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
    ) or _first_present(source, "COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME")
    private_key_source = _first_present(
        process_source,
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ) or _first_present(
        source,
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    )
    private_key = _normalize_coinbase_private_key_material(private_key_source)

    key_file = next((value for value in process_key_files if value), None) or _first_present(
        source,
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
    )

    if not key_name and not private_key and not key_file:
        return None

    credentials: Dict[str, Any] = {}

    if key_name:
        credentials["name"] = key_name
        credentials["key_name"] = key_name
        credentials["api_key_name"] = key_name
        credentials["COINBASE_CDP_KEY_NAME"] = key_name
        credentials["COINBASE_KEY_NAME"] = key_name

    if private_key:
        credentials["privateKey"] = private_key
        credentials["private_key"] = private_key
        credentials["COINBASE_CDP_PRIVATE_KEY"] = private_key
        credentials["COINBASE_PRIVATE_KEY"] = private_key

    resolved_key_file = _resolve_credential_path(key_file or "")
    if resolved_key_file:
        credentials["COINBASE_KEY_FILE"] = str(resolved_key_file)
        credentials["COINBASE_KEY_JSON_PATH"] = str(resolved_key_file)

    credentials["COINBASE_ENABLE_LIVE_ORDERS"] = source.get("COINBASE_ENABLE_LIVE_ORDERS") or "false"
    credentials["canonical_broker_environment"] = canonical.redacted_diagnostics()

    return credentials if credentials else None


def _load_oanda_env_credentials(mode: str) -> Optional[Dict[str, Any]]:
    canonical = _canonical_profile_credentials("OANDA", mode)
    source = canonical.credentials_for_broker()
    if canonical.validation_status != "PASS" and not (
        canonical.key_identifier_present or canonical.private_key_present
    ):
        return None

    token = (
        source.get("OANDA_API_KEY")
        or source.get("OANDA_ACCESS_TOKEN")
        or source.get("OANDA_TOKEN")
    )
    
    if mode == "live":
        account_id = source.get("OANDA_ACCOUNT_ID") or source.get("OANDA_LIVE_ACCOUNT_ID")
        env = "live"
    else:
        account_id = source.get("OANDA_PRACTICE_ACCOUNT_ID") or source.get("OANDA_ACCOUNT_ID")
        env = "practice"

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
    credentials["OANDA_ENABLE_LIVE_ORDERS"] = source.get("OANDA_ENABLE_LIVE_ORDERS") or "false"
    credentials["OANDA_BASE_URL"] = source.get("OANDA_BASE_URL") or (
        "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
    )
    credentials["OANDA_ENABLE_LIVE_TRADING"] = source.get("OANDA_ENABLE_LIVE_TRADING") or "false"
    credentials["canonical_broker_environment"] = canonical.redacted_diagnostics()

    return credentials if credentials else None


def _load_env_fallback_credentials(broker_name: str, mode: str) -> Optional[Dict[str, Any]]:
    broker = broker_name.lower()
    
    if broker == "coinbase":
        return _load_coinbase_env_credentials(mode)

    if broker == "oanda":
        return _load_oanda_env_credentials(mode)

    return None


def _canonical_profile_credentials(broker_name: str, mode: str) -> BrokerEnvironmentCredentials:
    bootstrap_broker_environment(REPO_ROOT)
    if str(mode or "").strip().lower() != "live":
        load_dotenv(REPO_ROOT / ".env.practice", override=False)
    selected_profile = profile_mode_alias(mode)
    profile_filename = {
        "PAPER": ".env.paper",
        "LIVE_READ_ONLY": ".env.live_read_only",
        "LIVE_EXECUTION": ".env.live_execution",
    }.get(selected_profile.value if selected_profile is not None else "")
    profile_file_is_authoritative = bool(
        profile_filename and (REPO_ROOT / profile_filename).is_file()
        and selected_profile is not None
        and selected_profile.value != "PAPER"
    )
    return build_broker_environment(
        REPO_ROOT,
        broker=broker_name,
        explicit_profile=selected_profile,
        env=dict(os.environ),
        allow_legacy=False,
        sanitize=profile_file_is_authoritative,
    )


def load_credentials_for_broker(
    broker_name: str,
    mode: str = "paper",
    base_dir: str = ".",
) -> Dict[str, Any]:
    normalized_mode = str(mode or "paper").strip().lower()
    # AR-033: when secret authority is enforced, live plaintext loaders fail closed.
    enforce = os.getenv("CSS_SECRET_AUTHORITY_ENFORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    } or os.getenv("CSS_ENV", "").strip().lower() in {"production", "prod"}
    if enforce and normalized_mode in {
        "live",
        "live_read_only",
        "live_execution",
        "production",
        "prod",
    }:
        allow_legacy_live = os.getenv("CSS_ALLOW_LEGACY_LIVE_CREDENTIALS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not allow_legacy_live:
            raise CredentialLoadError(
                "SECRET_AUTHORITY_REQUIRED: live credential loading via legacy "
                "plaintext paths is blocked; use enterprise secret handles "
                "(set CSS_ALLOW_LEGACY_LIVE_CREDENTIALS=1 only for governed migration)"
            )

    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)

    try:
        if spec.credential_file.endswith(".json"):
            credentials = _load_json_file(credential_path)
        else:
            credentials = _load_env_style_file(credential_path)
    except CredentialLoadError:
        env_credentials = _load_env_fallback_credentials(broker_name, mode)
        if env_credentials:
            credentials = env_credentials
        else:
            raise
    from backend.security.identity.broker_secret_adapter import (
        redirect_legacy_mapping_if_configured,
    )

    return redirect_legacy_mapping_if_configured(
        broker_name,
        credentials,
        component="backend.app.brokers.credential_loader",
        source_path=credential_path,
        environment=mode,
    )


def load_credentials(
    broker_name: str,
    mode: str = "paper",
    base_dir: str = ".",
) -> Optional[Dict[str, Any]]:
    try:
        return load_credentials_for_broker(broker_name, mode=mode, base_dir=base_dir)
    except CredentialLoadError:
        return None


def credential_file_exists(
    broker_name: str,
    base_dir: str = ".",
) -> bool:
    from backend.security.identity.broker_secret_adapter import (
        broker_secret_presence_if_configured,
    )

    authority_presence = broker_secret_presence_if_configured(broker_name)
    if authority_presence is True:
        return True
    spec = get_broker_spec(broker_name)
    credential_path = os.path.join(base_dir, spec.credential_file)

    if os.path.exists(credential_path):
       # Otherwise check env fallback
        return True
    return _load_env_fallback_credentials(broker_name, "paper") is not None
