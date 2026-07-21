from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Mapping


CANONICAL_FAILURE_REASONS = (
    "MISSING_CREDENTIALS",
    "KEY_MISSING",
    "SECRET_MISSING",
    "PRIVATE_KEY_INVALID",
    "PEM_INVALID",
    "JWT_GENERATION_FAILED",
    "JWT_SIGNATURE_INVALID",
    "TOKEN_INVALID",
    "ACCOUNT_ID_MISSING",
    "AUTH_FAILED",
    "UNAUTHORIZED",
    "FORBIDDEN",
    "NETWORK_ERROR",
    "DNS_ERROR",
    "TLS_ERROR",
    "TIMEOUT",
    "RATE_LIMIT",
    "BROKER_UNAVAILABLE",
    "CLOCK_SKEW",
    "UNKNOWN_ERROR",
    "NONE",
)

COINBASE_KEY_ENV_VARS = ("COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY")
COINBASE_SECRET_ENV_VARS = ("COINBASE_API_SECRET",)
COINBASE_PRIVATE_KEY_ENV_VARS = (
    "COINBASE_CDP_PRIVATE_KEY",
    "COINBASE_PRIVATE_KEY",
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
)
COINBASE_KEY_FILE_ENV_VARS = ("COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON", "COINBASE_KEY_FILE")

OANDA_TOKEN_ENV_VARS = ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN")
OANDA_ACCOUNT_ENV_VARS = ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID")
OANDA_BASE_URL_ENV_VARS = ("OANDA_BASE_URL",)
QUESTRADE_TOKEN_REFERENCE_ENV_VARS = (
    "QUESTRADE_TOKEN_STORE_ID",
)
QUESTRADE_ACCOUNT_REFERENCE_ENV_VARS = ("QUESTRADE_ACCOUNT_HASH",)
QUESTRADE_API_SERVER_ENV_VARS = ("QUESTRADE_API_SERVER", "QUESTRADE_BASE_URL", "QUESTRADE_API_URL")


@dataclass(frozen=True)
class BrokerCredentialDiagnostics:
    broker: str
    credentials_present: bool
    key_present: bool = False
    key_identifier_present: bool = False
    secret_present: bool = False
    private_key_present: bool = False
    token_present: bool = False
    account_present: bool = False
    account_identifier_present: bool = False
    base_url_present: bool = False
    pem_valid: bool = False
    jwt_generated: bool = False
    authentication_attempted: bool = False
    authenticated: bool = False
    failure_reason: str = "MISSING_CREDENTIALS"
    canonical_failure_reason: str = "MISSING_CREDENTIALS"
    readiness_status: str = "BLOCKED"
    recommended_action: str = "Configure broker credentials"
    remediation_hint: str = "Configure broker credentials"
    severity: str = "ERROR"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    missing_credentials: tuple[str, ...] = field(default_factory=tuple)
    missing_credential_fields: tuple[str, ...] = field(default_factory=tuple)
    redacted: bool = True
    advisory_only: bool = True
    live_trading_blocked: bool = True
    execution_allowed: bool = False
    broker_name: str = "NONE"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["missing_credentials"] = list(self.missing_credentials)
        payload["missing_credential_fields"] = list(self.missing_credential_fields)
        payload["broker_name"] = self.broker_name or str(self.broker or "NONE").upper()
        payload["canonical_failure_reason"] = self.canonical_failure_reason or self.failure_reason
        payload["remediation_hint"] = self.remediation_hint or self.recommended_action
        return payload


def diagnose_broker_credentials(
    broker: str | None,
    *,
    env: Mapping[str, Any] | None = None,
    authentication_attempted: bool = False,
    authenticated: bool = False,
    failure_reason: str | None = None,
    exception: BaseException | None = None,
    jwt_generated: bool = False,
    now: Any | None = None,
) -> BrokerCredentialDiagnostics:
    broker_name = str(broker or "NONE").strip().lower()
    source = env if isinstance(env, Mapping) else _diagnostic_source_from_canonical_loader(broker_name)
    timestamp = _timestamp(now)
    if broker_name == "coinbase":
        return _coinbase_diagnostics(
            source,
            authentication_attempted=authentication_attempted,
            authenticated=authenticated,
            failure_reason=failure_reason,
            exception=exception,
            jwt_generated=jwt_generated,
            timestamp=timestamp,
        )
    if broker_name == "oanda":
        return _oanda_diagnostics(
            source,
            authentication_attempted=authentication_attempted,
            authenticated=authenticated,
            failure_reason=failure_reason,
            exception=exception,
            timestamp=timestamp,
        )
    if broker_name == "questrade":
        return _questrade_diagnostics(
            source,
            authentication_attempted=authentication_attempted,
            authenticated=authenticated,
            failure_reason=failure_reason,
            exception=exception,
            timestamp=timestamp,
        )
    return _diagnostic(
        broker=broker_name or "none",
        credentials_present=False,
        failure_reason="MISSING_CREDENTIALS",
        recommended_action="Select a supported broker and configure read-only credentials",
        remediation_hint="Select a supported broker and configure read-only credentials",
        readiness_status="FAILED" if broker_name not in {"coinbase", "oanda"} else "BLOCKED",
        timestamp=timestamp,
    )


def diagnostics_payload(value: BrokerCredentialDiagnostics | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, BrokerCredentialDiagnostics):
        return value.as_dict()
    if isinstance(value, Mapping):
        payload = _diagnostic_from_mapping(value).as_dict()
        payload.update(_safe_legacy_fields(value))
        return payload
    return diagnose_broker_credentials("NONE").as_dict()


def authority_reason_from_diagnostics(value: BrokerCredentialDiagnostics | Mapping[str, Any] | None) -> str:
    payload = diagnostics_payload(value)
    reason = str(payload.get("failure_reason", "MISSING_CREDENTIALS")).upper()
    return {
        "MISSING_CREDENTIALS": "Credentials Missing",
        "KEY_MISSING": "Credentials Invalid",
        "SECRET_MISSING": "Credentials Invalid",
        "PRIVATE_KEY_INVALID": "Credentials Invalid",
        "PEM_INVALID": "Credentials Invalid",
        "JWT_GENERATION_FAILED": "JWT Generation Failed",
        "JWT_SIGNATURE_INVALID": "JWT Signature Invalid",
        "TOKEN_INVALID": "Token Invalid",
        "ACCOUNT_ID_MISSING": "Account ID Missing",
        "AUTH_FAILED": "Authentication Failed",
        "UNAUTHORIZED": "Unauthorized",
        "FORBIDDEN": "Forbidden",
        "NETWORK_ERROR": "Network Error",
        "DNS_ERROR": "DNS Error",
        "TLS_ERROR": "TLS Error",
        "TIMEOUT": "Timeout",
        "RATE_LIMIT": "Rate Limit",
        "BROKER_UNAVAILABLE": "Broker Unavailable",
        "CLOCK_SKEW": "Clock Skew",
        "UNKNOWN_ERROR": "Unknown Credential Error",
        "NONE": "Broker Execution Disabled",
    }.get(reason, "Credentials Invalid")


def classify_auth_failure(exc_or_reason: Any) -> str:
    text = f"{exc_or_reason.__class__.__name__} {exc_or_reason}".lower()
    if "jwt" in text and "signature" in text:
        return "JWT_SIGNATURE_INVALID"
    if "jwt" in text:
        return "JWT_GENERATION_FAILED"
    if "pem" in text or "private key" in text:
        return "PEM_INVALID"
    if "token" in text:
        return "TOKEN_INVALID"
    if "unauthorized" in text or "401" in text:
        return "UNAUTHORIZED"
    if "forbidden" in text or "403" in text:
        return "FORBIDDEN"
    if "dns" in text or "name resolution" in text:
        return "DNS_ERROR"
    if "tls" in text or "ssl" in text or "certificate" in text:
        return "TLS_ERROR"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    if "rate" in text and "limit" in text:
        return "RATE_LIMIT"
    if "network" in text or "connection" in text:
        return "NETWORK_ERROR"
    if "unavailable" in text or "503" in text:
        return "BROKER_UNAVAILABLE"
    if "clock" in text or "skew" in text:
        return "CLOCK_SKEW"
    if "auth" in text:
        return "AUTH_FAILED"
    return "UNKNOWN_ERROR"


def _coinbase_diagnostics(
    env: Mapping[str, Any],
    *,
    authentication_attempted: bool,
    authenticated: bool,
    failure_reason: str | None,
    exception: BaseException | None,
    jwt_generated: bool,
    timestamp: str,
) -> BrokerCredentialDiagnostics:
    key_present = _any_present(env, COINBASE_KEY_ENV_VARS)
    secret_present = _any_present(env, COINBASE_SECRET_ENV_VARS)
    private_key_present = _any_present(env, COINBASE_PRIVATE_KEY_ENV_VARS)
    key_file_present = _any_present(env, COINBASE_KEY_FILE_ENV_VARS)
    pem_valid = _coinbase_pem_valid(env, private_key_present=private_key_present, key_file_present=key_file_present)
    missing: list[str] = []
    if not key_present:
        missing.append("|".join(COINBASE_KEY_ENV_VARS))
    if not (secret_present or private_key_present or key_file_present):
        missing.append("COINBASE_CDP_PRIVATE_KEY|COINBASE_PRIVATE_KEY|COINBASE_API_SECRET|COINBASE_KEY_FILE")
    credentials_present = key_present and (secret_present or private_key_present or key_file_present) and pem_valid
    reason = _explicit_reason(failure_reason, exception)
    if not reason:
        if not key_present:
            reason = "KEY_MISSING"
        elif not (secret_present or private_key_present or key_file_present):
            reason = "SECRET_MISSING"
        elif not pem_valid:
            reason = "PEM_INVALID"
        elif authentication_attempted and not authenticated:
            reason = "AUTH_FAILED"
        else:
            reason = "NONE"
    return _diagnostic(
        broker="coinbase",
        broker_name="COINBASE",
        credentials_present=credentials_present,
        key_present=key_present,
        secret_present=secret_present,
        private_key_present=private_key_present or key_file_present,
        pem_valid=pem_valid,
        jwt_generated=jwt_generated,
        authentication_attempted=authentication_attempted,
        authenticated=authenticated,
        failure_reason=reason,
        canonical_failure_reason=reason,
        readiness_status=_readiness_status(credentials_present, authenticated=authenticated),
        recommended_action=_recommended_action(reason, "coinbase"),
        remediation_hint=_recommended_action(reason, "coinbase"),
        severity=_severity(reason, authenticated),
        timestamp=timestamp,
        missing_credentials=tuple(missing),
        missing_credential_fields=tuple(missing),
    )


def _oanda_diagnostics(
    env: Mapping[str, Any],
    *,
    authentication_attempted: bool,
    authenticated: bool,
    failure_reason: str | None,
    exception: BaseException | None,
    timestamp: str,
) -> BrokerCredentialDiagnostics:
    token_present = _any_present(env, OANDA_TOKEN_ENV_VARS)
    account_present = _any_present(env, OANDA_ACCOUNT_ENV_VARS)
    base_url_present = _any_present(env, OANDA_BASE_URL_ENV_VARS)
    missing: list[str] = []
    if not token_present:
        missing.append("|".join(OANDA_TOKEN_ENV_VARS))
    if not account_present:
        missing.append("|".join(OANDA_ACCOUNT_ENV_VARS))
    if not base_url_present:
        missing.append("OANDA_BASE_URL")
    credentials_present = token_present and account_present and base_url_present
    reason = _explicit_reason(failure_reason, exception)
    if not reason:
        if not token_present and not account_present:
            reason = "MISSING_CREDENTIALS"
        elif not token_present:
            reason = "TOKEN_INVALID"
        elif not account_present:
            reason = "ACCOUNT_ID_MISSING"
        elif not base_url_present:
            reason = "BROKER_UNAVAILABLE"
        elif authentication_attempted and not authenticated:
            reason = "AUTH_FAILED"
        else:
            reason = "NONE"
    return _diagnostic(
        broker="oanda",
        broker_name="OANDA",
        credentials_present=credentials_present,
        token_present=token_present,
        account_present=account_present,
        base_url_present=base_url_present,
        pem_valid=True,
        authentication_attempted=authentication_attempted,
        authenticated=authenticated,
        failure_reason=reason,
        canonical_failure_reason=reason,
        readiness_status=_readiness_status(credentials_present, authenticated=authenticated),
        recommended_action=_recommended_action(reason, "oanda"),
        remediation_hint=_recommended_action(reason, "oanda"),
        severity=_severity(reason, authenticated),
        timestamp=timestamp,
        missing_credentials=tuple(missing),
        missing_credential_fields=tuple(missing),
    )


def _questrade_diagnostics(
    env: Mapping[str, Any],
    *,
    authentication_attempted: bool,
    authenticated: bool,
    failure_reason: str | None,
    exception: BaseException | None,
    timestamp: str,
) -> BrokerCredentialDiagnostics:
    token_present = _any_present(env, QUESTRADE_TOKEN_REFERENCE_ENV_VARS)
    account_present = _any_present(env, QUESTRADE_ACCOUNT_REFERENCE_ENV_VARS)
    base_url_present = _any_present(env, QUESTRADE_API_SERVER_ENV_VARS)
    missing = () if token_present else ("QUESTRADE_REFRESH_TOKEN|QUESTRADE_TOKEN_STORE_ID",)
    reason = _explicit_reason(failure_reason, exception)
    if not reason:
        if not token_present:
            reason = "MISSING_CREDENTIALS"
        elif authentication_attempted and not authenticated:
            reason = "AUTH_FAILED"
        else:
            reason = "NONE"
    return _diagnostic(
        broker="questrade",
        broker_name="QUESTRADE",
        credentials_present=token_present,
        key_present=token_present,
        key_identifier_present=token_present,
        token_present=token_present,
        account_present=account_present,
        account_identifier_present=account_present,
        base_url_present=base_url_present,
        pem_valid=True,
        authentication_attempted=authentication_attempted,
        authenticated=authenticated,
        failure_reason=reason,
        canonical_failure_reason=reason,
        readiness_status=_readiness_status(token_present, authenticated=authenticated),
        recommended_action=_recommended_action(reason, "questrade"),
        remediation_hint=_recommended_action(reason, "questrade"),
        severity=_severity(reason, authenticated),
        timestamp=timestamp,
        missing_credentials=missing,
        missing_credential_fields=missing,
    )


def _diagnostic(**kwargs: Any) -> BrokerCredentialDiagnostics:
    payload = {
        "broker": "none",
        "credentials_present": False,
        "failure_reason": "MISSING_CREDENTIALS",
        "recommended_action": "Configure broker credentials",
        "severity": "ERROR",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(kwargs)
    reason = str(payload.get("failure_reason", "UNKNOWN_ERROR")).upper()
    if reason not in CANONICAL_FAILURE_REASONS:
        reason = "UNKNOWN_ERROR"
    payload["failure_reason"] = reason
    payload["canonical_failure_reason"] = str(payload.get("canonical_failure_reason", reason)).upper()
    payload["readiness_status"] = str(payload.get("readiness_status", "BLOCKED") or "BLOCKED").upper()
    payload["remediation_hint"] = str(payload.get("remediation_hint", payload.get("recommended_action", "Configure broker credentials")) or "Configure broker credentials")
    payload["broker_name"] = str(payload.get("broker_name", str(payload.get("broker", "NONE")).upper()) or "NONE").upper()
    payload.setdefault("key_identifier_present", bool(payload.get("key_present")))
    payload.setdefault("account_identifier_present", bool(payload.get("account_present")))
    payload["missing_credential_fields"] = tuple(payload.get("missing_credential_fields", payload.get("missing_credentials", ())))
    payload["live_trading_blocked"] = True if payload.get("live_trading_blocked", True) else False
    return BrokerCredentialDiagnostics(**payload)


def _diagnostic_from_mapping(value: Mapping[str, Any]) -> BrokerCredentialDiagnostics:
    broker = str(value.get("broker", value.get("selected_broker", "none")) or "none").lower()
    credentials_present = _truthy(value.get("credentials_present")) or str(
        value.get("credential_status", value.get("credentials", ""))
    ).upper() in {"PRESENT", "READY", "PASS"}
    reason = str(value.get("failure_reason", value.get("credential_failure_reason", "")) or "")
    if not reason:
        reason = "NONE" if credentials_present else "MISSING_CREDENTIALS"
    return _diagnostic(
        broker=broker,
        broker_name=str(value.get("broker_name", str(broker or "NONE")).upper()),
        credentials_present=credentials_present,
        key_present=_truthy(value.get("key_present", value.get("coinbase_key_present"))),
        secret_present=_truthy(value.get("secret_present")),
        private_key_present=_truthy(
            value.get("private_key_present", value.get("coinbase_private_key_present", value.get("coinbase_key_file_present")))
        ),
        token_present=_truthy(value.get("token_present", value.get("oanda_token_present"))),
        account_present=_truthy(value.get("account_present", value.get("oanda_account_present"))),
        base_url_present=_truthy(value.get("base_url_present", value.get("oanda_base_url_present"))),
        pem_valid=_truthy(value.get("pem_valid", True)),
        jwt_generated=_truthy(value.get("jwt_generated")),
        authentication_attempted=_truthy(value.get("authentication_attempted")),
        authenticated=_truthy(value.get("authenticated")),
        failure_reason=reason,
        canonical_failure_reason=str(value.get("canonical_failure_reason", reason)).upper(),
        readiness_status=str(value.get("readiness_status", "READY" if credentials_present else "BLOCKED") or "BLOCKED").upper(),
        recommended_action=str(value.get("recommended_action", _recommended_action(reason, broker))),
        remediation_hint=str(value.get("remediation_hint", value.get("recommended_action", _recommended_action(reason, broker)))) ,
        severity=str(value.get("severity", _severity(reason, _truthy(value.get("authenticated"))))),
        timestamp=str(value.get("timestamp", datetime.now(timezone.utc).isoformat())),
        missing_credentials=tuple(str(item) for item in value.get("missing_credentials", []) if str(item)),
        missing_credential_fields=tuple(str(item) for item in value.get("missing_credential_fields", value.get("missing_credentials", [])) if str(item)),
        live_trading_blocked=_truthy(value.get("live_trading_blocked", True)),
    )


def _safe_legacy_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key.endswith("_present") or key in {"credential_status", "missing_credentials", "redacted"}
    }


def _coinbase_pem_valid(env: Mapping[str, Any], *, private_key_present: bool, key_file_present: bool) -> bool:
    if not private_key_present and not key_file_present:
        return False
    for name in COINBASE_PRIVATE_KEY_ENV_VARS:
        raw = str(env.get(name, "") or "").strip()
        if not raw:
            continue
        if name.endswith("_PATH"):
            return Path(raw).exists()
        return _looks_like_private_key(raw)
    for name in COINBASE_KEY_FILE_ENV_VARS:
        raw = str(env.get(name, "") or "").strip()
        if raw and (Path(raw).exists() or raw.startswith("{")):
            return True
    return True


def _looks_like_private_key(value: str) -> bool:
    normalized = value.replace("\\n", "\n")
    if "BEGIN" not in normalized:
        return bool(normalized.strip())
    return "PRIVATE KEY" in normalized and "END" in normalized


def _explicit_reason(reason: str | None, exception: BaseException | None) -> str:
    if reason:
        normalized = str(reason).strip().upper()
        return normalized if normalized in CANONICAL_FAILURE_REASONS else classify_auth_failure(normalized)
    if exception is not None:
        return classify_auth_failure(exception)
    return ""


def _recommended_action(reason: str, broker: str) -> str:
    reason = str(reason or "UNKNOWN_ERROR").upper()
    return {
        "MISSING_CREDENTIALS": f"Configure {broker.upper()} read-only credentials",
        "KEY_MISSING": "Configure the Coinbase CDP key name",
        "SECRET_MISSING": "Configure the Coinbase CDP private key or API secret",
        "PRIVATE_KEY_INVALID": "Verify the Coinbase private key file or value",
        "PEM_INVALID": "Generate a new Coinbase CDP key",
        "JWT_GENERATION_FAILED": "Regenerate the Coinbase JWT signing key",
        "JWT_SIGNATURE_INVALID": "Generate a new Coinbase CDP key",
        "TOKEN_INVALID": "Configure a valid OANDA API token",
        "ACCOUNT_ID_MISSING": "Configure OANDA Account ID",
        "AUTH_FAILED": "Verify broker credentials and read-only permissions",
        "UNAUTHORIZED": "Verify broker credentials and API permissions",
        "FORBIDDEN": "Enable the required read-only broker permissions",
        "NETWORK_ERROR": "Check network connectivity to the broker API",
        "DNS_ERROR": "Check DNS resolution for the broker API endpoint",
        "TLS_ERROR": "Check TLS/certificate trust for the broker API endpoint",
        "TIMEOUT": "Retry after confirming broker API latency",
        "RATE_LIMIT": "Wait for the broker API rate limit window to reset",
        "BROKER_UNAVAILABLE": "Confirm the broker API endpoint is available",
        "CLOCK_SKEW": "Synchronize system time before authentication",
        "NONE": "No credential remediation required",
    }.get(reason, "Inspect broker credential diagnostics")


def _readiness_status(credentials_present: bool, *, authenticated: bool) -> str:
    if authenticated:
        return "READY"
    return "READY" if credentials_present else "BLOCKED"


def _severity(reason: str, authenticated: bool) -> str:
    if authenticated or str(reason).upper() == "NONE":
        return "INFO"
    if str(reason).upper() in {"RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "BROKER_UNAVAILABLE"}:
        return "WARNING"
    return "ERROR"


def _timestamp(now: Any | None) -> str:
    if now is None:
        return datetime.now(timezone.utc).isoformat()
    value = now() if callable(now) else now
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _any_present(env: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return any(bool(str(env.get(name, "") or "").strip()) for name in names)


def _diagnostic_source_from_canonical_loader(broker_name: str) -> Mapping[str, Any]:
    signature = _credential_env_signature(broker_name)
    return dict(_cached_diagnostic_source_from_canonical_loader(broker_name, signature))


@lru_cache(maxsize=16)
def _cached_diagnostic_source_from_canonical_loader(
    broker_name: str,
    _signature: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, Any], ...]:
    source: dict[str, Any] = dict(os.environ)
    if broker_name not in {"coinbase", "oanda"}:
        return tuple(source.items())
    try:
        from backend.app.brokers.credential_loader import load_credentials

        credentials = load_credentials(broker_name, mode="paper") or {}
    except Exception:
        return tuple(source.items())
    for key, value in credentials.items():
        if value is not None and not source.get(str(key)):
            source[str(key)] = value
    return tuple(source.items())


def _credential_env_signature(broker_name: str) -> tuple[tuple[str, str], ...]:
    if broker_name == "coinbase":
        names = COINBASE_KEY_ENV_VARS + COINBASE_SECRET_ENV_VARS + COINBASE_PRIVATE_KEY_ENV_VARS + COINBASE_KEY_FILE_ENV_VARS
    elif broker_name == "oanda":
        names = OANDA_TOKEN_ENV_VARS + OANDA_ACCOUNT_ENV_VARS + OANDA_BASE_URL_ENV_VARS
    else:
        names = ()
    return tuple((name, str(os.environ.get(name, "") or "")) for name in names)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "present", "ready", "pass", "ok"}


__all__ = [
    "CANONICAL_FAILURE_REASONS",
    "BrokerCredentialDiagnostics",
    "authority_reason_from_diagnostics",
    "classify_auth_failure",
    "diagnose_broker_credentials",
    "diagnostics_payload",
]
