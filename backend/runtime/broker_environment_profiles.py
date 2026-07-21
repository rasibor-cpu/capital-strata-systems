from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from dotenv import dotenv_values


class BrokerEnvironmentProfile(str, Enum):
    PAPER = "PAPER"
    LIVE_READ_ONLY = "LIVE_READ_ONLY"
    LIVE_EXECUTION = "LIVE_EXECUTION"


PROFILE_SELECTION_KEYS = (
    "CSS_BROKER_ENVIRONMENT_PROFILE",
    "BROKER_ENVIRONMENT_PROFILE",
    "CSS_BROKER_PROFILE",
)

ENGINE_MODE_VALUES = {"SAFE", "BALANCED", "AGGRESSIVE", "EXPANSION"}

COINBASE_PROFILE_KEYS = frozenset(
    {
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_API_KEY",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_API_SECRET",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
        "COINBASE_KEY_FILE",
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_BASE_URL",
        "COINBASE_API_URL",
        "COINBASE_REST_URL",
        "COINBASE_SANDBOX_URL",
        "COINBASE_API_PERMISSIONS",
        "COINBASE_SCOPES",
        "COINBASE_CDP_PERMISSIONS",
        "COINBASE_AUTH_TIMESTAMP",
        "COINBASE_JWT_TIMESTAMP",
        "COINBASE_ENABLE_LIVE_ORDERS",
        "COINBASE_ENABLE_LIVE_TRADING",
        "COINBASE_TEST_ORDER_USD",
        "COINBASE_MAX_LIVE_ORDER_USD",
    }
)

OANDA_PROFILE_KEYS = frozenset(
    {
        "OANDA_API_KEY",
        "OANDA_ACCESS_TOKEN",
        "OANDA_TOKEN",
        "OANDA_ACCOUNT_ID",
        "OANDA_LIVE_ACCOUNT_ID",
        "OANDA_PRACTICE_ACCOUNT_ID",
        "OANDA_BASE_URL",
        "OANDA_ENV",
        "OANDA_MODE",
        "OANDA_API_VERSION",
        "OANDA_ENABLE_LIVE_ORDERS",
        "OANDA_ENABLE_LIVE_TRADING",
    }
)

BINANCE_PROFILE_KEYS = frozenset(
    {
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_BASE_URL",
        "BINANCE_API_URL",
        "BINANCE_REST_URL",
        "BINANCE_TESTNET_URL",
        "BINANCE_API_VERSION",
        "BINANCE_ENABLE_LIVE_ORDERS",
        "BINANCE_ENABLE_LIVE_TRADING",
    }
)

QUESTRADE_PROFILE_KEYS = frozenset(
    {
        "QUESTRADE_REFRESH_TOKEN",
        "QUESTRADE_ACCESS_TOKEN",
        "QUESTRADE_TOKEN_STORE_ID",
        "QUESTRADE_SECRET_STORE_PROVIDER",
        "QUESTRADE_ACCOUNT_HASH",
        "QUESTRADE_ACCOUNT_ID",
        "QUESTRADE_API_SERVER",
        "QUESTRADE_API_KEY",
        "QUESTRADE_BASE_URL",
        "QUESTRADE_API_URL",
        "QUESTRADE_AUTH_URL",
        "QUESTRADE_API_VERSION",
        "QUESTRADE_ENABLE_LIVE_ORDERS",
        "QT_REFRESH_TOKEN",
        "QT_ACCESS_TOKEN",
    }
)

PROFILE_SPECIFIC_KEYS = (
    COINBASE_PROFILE_KEYS | OANDA_PROFILE_KEYS | BINANCE_PROFILE_KEYS | QUESTRADE_PROFILE_KEYS
)

TEST_PRACTICE_SANDBOX_KEYS = frozenset(
    key
    for key in PROFILE_SPECIFIC_KEYS
    if "TEST" in key or "PRACTICE" in key or "SANDBOX" in key
)

LIVE_AUTHORITY_KEYS = frozenset(
    {
        "COINBASE_ENABLE_LIVE_ORDERS",
        "COINBASE_ENABLE_LIVE_TRADING",
        "OANDA_ENABLE_LIVE_ORDERS",
        "OANDA_ENABLE_LIVE_TRADING",
        "BINANCE_ENABLE_LIVE_ORDERS",
        "BINANCE_ENABLE_LIVE_TRADING",
        "QUESTRADE_ENABLE_LIVE_ORDERS",
    }
)

LIVE_CREDENTIAL_KEYS = frozenset(
    {
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "OANDA_LIVE_ACCOUNT_ID",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "QUESTRADE_REFRESH_TOKEN",
        "QUESTRADE_ACCESS_TOKEN",
    }
)

COINBASE_KEY_FIELDS = ("COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY")
COINBASE_PRIVATE_KEY_FIELDS = (
    "COINBASE_CDP_PRIVATE_KEY",
    "COINBASE_PRIVATE_KEY",
    "COINBASE_API_SECRET",
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
    "COINBASE_KEY_FILE",
    "COINBASE_KEY_JSON_PATH",
    "COINBASE_KEY_JSON",
)

OANDA_TOKEN_FIELDS = ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN")
OANDA_ACCOUNT_FIELDS = ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID")
QUESTRADE_TOKEN_FIELDS = (
    "QUESTRADE_TOKEN_STORE_ID",
)
QUESTRADE_ACCOUNT_FIELDS = (
    "QUESTRADE_ACCOUNT_HASH",
)
SECURE_CONFIGURATION_REFERENCE_KEYS = frozenset(
    {"QUESTRADE_TOKEN_STORE_ID", "QUESTRADE_ACCOUNT_HASH", "QUESTRADE_SECRET_STORE_PROVIDER"}
)


@dataclass(frozen=True)
class BrokerEnvironmentCredentials:
    profile: BrokerEnvironmentProfile | None
    broker: str
    environment: str
    credential_source: str
    key_identifier_present: bool
    private_key_present: bool
    account_identifier_present: bool
    permissions_classification: str
    base_url: str
    read_only_allowed: bool
    execution_requested: bool
    execution_authorized: bool
    profile_fingerprint: str
    validation_status: str
    failure_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    loaded_files: tuple[str, ...] = ()
    skipped_files: tuple[str, ...] = ()
    removed_inherited_variables: tuple[str, ...] = ()
    contamination_keys: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    advisory_only: bool = True
    secrets_redacted: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "broker", str(self.broker or "NONE").upper())
        object.__setattr__(self, "environment", str(self.environment or "unknown").lower())
        object.__setattr__(self, "credential_source", str(self.credential_source or "UNKNOWN"))
        object.__setattr__(self, "permissions_classification", str(self.permissions_classification or "UNKNOWN").upper())
        object.__setattr__(self, "validation_status", str(self.validation_status or "FAIL").upper())
        object.__setattr__(self, "failure_reasons", tuple(dict.fromkeys(str(item) for item in self.failure_reasons if str(item))))
        object.__setattr__(self, "warnings", tuple(dict.fromkeys(str(item) for item in self.warnings if str(item))))
        object.__setattr__(self, "loaded_files", tuple(dict.fromkeys(str(item) for item in self.loaded_files if str(item))))
        object.__setattr__(self, "skipped_files", tuple(dict.fromkeys(str(item) for item in self.skipped_files if str(item))))
        object.__setattr__(self, "removed_inherited_variables", tuple(dict.fromkeys(str(item) for item in self.removed_inherited_variables if str(item))))
        object.__setattr__(self, "contamination_keys", tuple(dict.fromkeys(str(item) for item in self.contamination_keys if str(item))))
        object.__setattr__(self, "execution_requested", bool(self.execution_requested))
        object.__setattr__(self, "execution_authorized", False)
        object.__setattr__(self, "execution_allowed", False)
        object.__setattr__(self, "live_trading_blocked", True)
        object.__setattr__(self, "broker_execution_armed", False)
        object.__setattr__(self, "advisory_only", True)
        object.__setattr__(self, "secrets_redacted", True)

    def redacted_diagnostics(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("env", None)
        payload["profile"] = self.profile.value if self.profile else "UNSELECTED"
        payload["credential_values_redacted"] = True
        payload["private_key_redacted"] = True
        payload["account_ids_redacted"] = True
        return _json_safe(payload)

    def credentials_for_broker(self) -> dict[str, str]:
        return dict(self.env)


@dataclass(frozen=True)
class ProfileLoadTrace:
    selected_profile: str
    loaded_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    removed_inherited_variables: tuple[str, ...]
    validation_status: str
    failure_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    contamination_keys: tuple[str, ...]
    profile_fingerprint: str
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    advisory_only: bool = True
    secrets_redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def select_broker_environment_profile(
    *,
    explicit_profile: str | BrokerEnvironmentProfile | None = None,
    cli_profile: str | BrokerEnvironmentProfile | None = None,
    env: Mapping[str, Any] | None = None,
) -> BrokerEnvironmentProfile | None:
    source = env if isinstance(env, Mapping) else os.environ
    candidates: list[str | BrokerEnvironmentProfile] = []
    for value in (explicit_profile, cli_profile):
        if value is not None and str(value).strip():
            candidates.append(value if isinstance(value, BrokerEnvironmentProfile) else str(value).strip())
    env_values = [str(source.get(key, "") or "").strip() for key in PROFILE_SELECTION_KEYS if str(source.get(key, "") or "").strip()]
    candidates.extend(env_values)
    normalized = [_normalize_profile(value) for value in candidates]
    selected = [profile for profile in normalized if profile is not None]
    if len({profile.value for profile in selected}) == 1:
        return selected[0]
    return None


def build_broker_environment(
    project_root: str | Path,
    *,
    broker: str = "COINBASE",
    explicit_profile: str | BrokerEnvironmentProfile | None = None,
    cli_profile: str | BrokerEnvironmentProfile | None = None,
    env: MutableMapping[str, str] | None = None,
    allow_legacy: bool = True,
    sanitize: bool = True,
) -> BrokerEnvironmentCredentials:
    target_env = env if env is not None else os.environ
    root = Path(project_root)
    selected = select_broker_environment_profile(
        explicit_profile=explicit_profile,
        cli_profile=cli_profile,
        env=target_env,
    )
    selection_failures = _profile_selection_failures(
        explicit_profile=explicit_profile,
        cli_profile=cli_profile,
        env=target_env,
        selected=selected,
    )
    removed = sanitize_broker_profile_environment(target_env) if sanitize else []
    # When an explicit environment mapping is provided, profile file loading remains
    # deterministic and isolated from process-level pytest flags.
    allow_legacy_files = allow_legacy or env is not None
    loaded, skipped = _load_profile_files(root, selected, target_env, allow_legacy=allow_legacy_files)
    contamination = _contamination_keys(target_env, selected, broker=broker)
    removed.extend(_remove_incompatible_profile_variables(target_env, selected, broker=broker))
    failures = list(selection_failures)
    warnings: list[str] = []
    if contamination:
        failures.append("mixed_profile_variables")
    if selected is None:
        failures.append("no_explicit_broker_environment_profile")
    if selected == BrokerEnvironmentProfile.PAPER:
        live_keys = sorted(key for key in contamination if key in LIVE_CREDENTIAL_KEYS)
        if live_keys:
            failures.append("live_credential_in_paper_profile")
    if selected in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION}:
        authority = _truthy_any(target_env, LIVE_AUTHORITY_KEYS)
        if authority:
            failures.append("unsafe_execution_flags")
            contamination.extend(sorted(key for key in LIVE_AUTHORITY_KEYS if _truthy(target_env.get(key))))
    if selected == BrokerEnvironmentProfile.LIVE_READ_ONLY and _truthy_any(target_env, LIVE_AUTHORITY_KEYS):
        failures.append("execution_authorization_in_read_only_profile")
    if selected == BrokerEnvironmentProfile.LIVE_EXECUTION:
        warnings.append("live_execution_profile_modeled_but_execution_blocked")

    broker_name = str(broker or "COINBASE").upper()
    profile_env = _environment_name(selected)
    credential_fields = {
        "COINBASE": COINBASE_KEY_FIELDS,
        "OANDA": OANDA_TOKEN_FIELDS,
        "QUESTRADE": QUESTRADE_TOKEN_FIELDS,
    }.get(broker_name, ())
    private_key_fields = {
        "COINBASE": COINBASE_PRIVATE_KEY_FIELDS,
        "OANDA": OANDA_ACCOUNT_FIELDS,
    }.get(broker_name, ())
    account_fields = {
        "OANDA": OANDA_ACCOUNT_FIELDS,
        "QUESTRADE": QUESTRADE_ACCOUNT_FIELDS,
    }.get(broker_name, ())
    key_present = _any_present(target_env, credential_fields)
    private_key_present = _any_present(target_env, private_key_fields)
    account_identifier_present = _any_present(target_env, account_fields)
    credential_source = _credential_source(target_env, broker_name, loaded)
    if credential_source == "UNKNOWN" and selected is not None:
        failures.append("unknown_credential_source")
    base_url = _base_url(target_env, broker_name, selected)
    if _invalid_base_url(base_url, selected):
        failures.append("invalid_base_url")
    permissions = _permissions_classification(target_env, selected, broker_name)
    fingerprint = _profile_fingerprint(
        selected=selected,
        broker=broker_name,
        environment=profile_env,
        env=target_env,
        loaded_files=loaded,
    )
    status = "PASS" if not failures else "FAIL"
    profile_env_snapshot = {
        key: str(value)
        for key, value in target_env.items()
        if key in PROFILE_SPECIFIC_KEYS or key in PROFILE_SELECTION_KEYS
    }
    return BrokerEnvironmentCredentials(
        profile=selected,
        broker=broker_name,
        environment=profile_env,
        credential_source=credential_source,
        key_identifier_present=key_present,
        private_key_present=private_key_present,
        account_identifier_present=account_identifier_present,
        permissions_classification=permissions,
        base_url=base_url,
        read_only_allowed=selected in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION},
        execution_requested=selected == BrokerEnvironmentProfile.LIVE_EXECUTION,
        execution_authorized=False,
        profile_fingerprint=fingerprint,
        validation_status=status,
        failure_reasons=tuple(dict.fromkeys(failures)),
        warnings=tuple(warnings),
        loaded_files=tuple(loaded),
        skipped_files=tuple(skipped),
        removed_inherited_variables=tuple(removed),
        contamination_keys=tuple(dict.fromkeys(contamination)),
        env=profile_env_snapshot,
    )


def sanitize_broker_profile_environment(env: MutableMapping[str, str] | None = None) -> list[str]:
    target_env = env if env is not None else os.environ
    removed: list[str] = []
    for key in sorted(PROFILE_SPECIFIC_KEYS - SECURE_CONFIGURATION_REFERENCE_KEYS):
        if target_env.get(key) not in (None, ""):
            target_env.pop(key, None)
            removed.append(key)
    return removed


def profile_mode_alias(value: str | None) -> BrokerEnvironmentProfile | None:
    text = str(value or "").strip().lower()
    if text in {"paper", "practice", "demo", "sim", "simulation"}:
        return BrokerEnvironmentProfile.PAPER
    if text in {"live", "production", "prod", "read_only", "readonly", "live_read_only"}:
        return BrokerEnvironmentProfile.LIVE_READ_ONLY
    if text in {"live_execution", "execution"}:
        return BrokerEnvironmentProfile.LIVE_EXECUTION
    return None


def profile_trace(credentials: BrokerEnvironmentCredentials) -> dict[str, Any]:
    return ProfileLoadTrace(
        selected_profile=credentials.profile.value if credentials.profile else "UNSELECTED",
        loaded_files=credentials.loaded_files,
        skipped_files=credentials.skipped_files,
        removed_inherited_variables=credentials.removed_inherited_variables,
        validation_status=credentials.validation_status,
        failure_reasons=credentials.failure_reasons,
        warnings=credentials.warnings,
        contamination_keys=credentials.contamination_keys,
        profile_fingerprint=credentials.profile_fingerprint,
    ).as_dict()


def legacy_variable_migration_register() -> list[dict[str, Any]]:
    return [
        {
            "variable": "COINBASE_TEST_ORDER_USD",
            "profile": "PAPER",
            "purpose": "paper/practice test notional",
            "consumer": "paper broker and legacy dashboard preview",
            "deprecated_status": "profile_scoped_legacy",
            "migration_target": ".env.paper",
            "safe_to_remove_from_live": True,
        },
        {
            "variable": "COINBASE_ENABLE_LIVE_ORDERS",
            "profile": "LIVE_EXECUTION",
            "purpose": "legacy live order authority flag",
            "consumer": "execution firewall compatibility",
            "deprecated_status": "unsafe_legacy_authority",
            "migration_target": "future governed execution profile approval",
            "safe_to_remove_from_live_read_only": True,
        },
        {
            "variable": "COINBASE_KEY_NAME",
            "profile": "LIVE_READ_ONLY or LIVE_EXECUTION",
            "purpose": "Coinbase key-name compatibility alias",
            "consumer": "canonical broker environment profile",
            "deprecated_status": "compatibility_alias",
            "migration_target": "COINBASE_CDP_KEY_NAME in selected profile file",
            "safe_to_remove_from_live": False,
        },
        {
            "variable": ".env.practice",
            "profile": "PAPER",
            "purpose": "legacy practice environment file",
            "consumer": "compatibility migration only",
            "deprecated_status": "legacy_file",
            "migration_target": ".env.paper",
            "safe_to_remove_from_live": True,
        },
    ]


def _load_profile_files(
    root: Path,
    selected: BrokerEnvironmentProfile | None,
    env: MutableMapping[str, str],
    *,
    allow_legacy: bool,
) -> tuple[list[str], list[str]]:
    loaded: list[str] = []
    skipped: list[str] = []
    ordered = [root / ".env.shared"]
    if selected == BrokerEnvironmentProfile.PAPER:
        ordered.append(root / ".env.paper")
    elif selected == BrokerEnvironmentProfile.LIVE_READ_ONLY:
        ordered.append(root / ".env.live_read_only")
    elif selected == BrokerEnvironmentProfile.LIVE_EXECUTION:
        ordered.append(root / ".env.live_execution")
    else:
        skipped.extend(str(root / name) for name in (".env.shared", ".env.paper", ".env.live_read_only", ".env.live_execution", ".env", ".env.practice"))
        return loaded, skipped

    if allow_legacy:
        ordered.append(root / ".env")
        if selected == BrokerEnvironmentProfile.PAPER:
            ordered.append(root / ".env.practice")
        else:
            skipped.append(str(root / ".env.practice"))
    for path in ordered:
        if _load_env_file(path, env, override=False):
            loaded.append(str(path))
        elif str(path) not in skipped:
            skipped.append(str(path))
    return loaded, skipped


def _load_env_file(path: Path, env: MutableMapping[str, str], *, override: bool) -> bool:
    if not path.exists():
        return False
    changed = False
    for key, value in dotenv_values(path).items():
        if value is None:
            continue
        if override or key not in env:
            env[str(key)] = str(value)
            changed = True
    return changed


def _profile_selection_failures(
    *,
    explicit_profile: str | BrokerEnvironmentProfile | None,
    cli_profile: str | BrokerEnvironmentProfile | None,
    env: Mapping[str, Any],
    selected: BrokerEnvironmentProfile | None,
) -> list[str]:
    raw: list[str | BrokerEnvironmentProfile] = []
    for value in (explicit_profile, cli_profile):
        if value is not None and str(value).strip():
            raw.append(value if isinstance(value, BrokerEnvironmentProfile) else str(value).strip())
    raw.extend(str(env.get(key, "") or "").strip() for key in PROFILE_SELECTION_KEYS if str(env.get(key, "") or "").strip())
    raw = [item for item in raw if item]
    normalized = [_normalize_profile(item) for item in raw]
    failures: list[str] = []
    raw_text = {item.value if isinstance(item, BrokerEnvironmentProfile) else str(item) for item in raw}
    if len(raw_text) > 1 and len({profile.value for profile in normalized if profile}) > 1:
        failures.append("multiple_broker_environment_profiles_selected")
    if any(str(item.value if isinstance(item, BrokerEnvironmentProfile) else item).strip().upper() in ENGINE_MODE_VALUES for item in raw):
        failures.append("engine_mode_is_not_broker_profile")
    if raw and selected is None:
        failures.append("unknown_broker_environment_profile")
    return failures


def _normalize_profile(value: Any) -> BrokerEnvironmentProfile | None:
    if isinstance(value, BrokerEnvironmentProfile):
        return value
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "PAPER": BrokerEnvironmentProfile.PAPER,
        "PRACTICE": BrokerEnvironmentProfile.PAPER,
        "LIVE_READ_ONLY": BrokerEnvironmentProfile.LIVE_READ_ONLY,
        "LIVE_READONLY": BrokerEnvironmentProfile.LIVE_READ_ONLY,
        "READ_ONLY": BrokerEnvironmentProfile.LIVE_READ_ONLY,
        "READONLY": BrokerEnvironmentProfile.LIVE_READ_ONLY,
        "LIVE": BrokerEnvironmentProfile.LIVE_READ_ONLY,
        "LIVE_EXECUTION": BrokerEnvironmentProfile.LIVE_EXECUTION,
        "EXECUTION": BrokerEnvironmentProfile.LIVE_EXECUTION,
    }
    return aliases.get(text)


def _environment_name(profile: BrokerEnvironmentProfile | None) -> str:
    if profile == BrokerEnvironmentProfile.PAPER:
        return "paper"
    if profile == BrokerEnvironmentProfile.LIVE_READ_ONLY:
        return "live_read_only"
    if profile == BrokerEnvironmentProfile.LIVE_EXECUTION:
        return "live_execution"
    return "unselected"


def _contamination_keys(env: Mapping[str, Any], selected: BrokerEnvironmentProfile | None, broker: str = "COINBASE") -> list[str]:
    broker_u = str(broker).upper()
    if broker_u == "COINBASE":
        broker_keys = COINBASE_PROFILE_KEYS
    elif broker_u == "OANDA":
        broker_keys = OANDA_PROFILE_KEYS
    elif broker_u == "BINANCE":
        broker_keys = BINANCE_PROFILE_KEYS
    elif broker_u == "QUESTRADE":
        broker_keys = QUESTRADE_PROFILE_KEYS
    else:
        broker_keys = COINBASE_PROFILE_KEYS
    keys: list[str] = []
    if selected in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION}:
        keys.extend(sorted(key for key in TEST_PRACTICE_SANDBOX_KEYS if key in broker_keys and env.get(key) not in (None, "")))
        for key, value in env.items():
            value_text = str(value or "").strip().lower()
            if key in broker_keys and any(token in value_text for token in ("sandbox", "practice", "demo", "testnet")):
                keys.append(str(key))
        # Phase 177C — detect foreign broker host tokens under this broker's endpoint keys
        try:
            from backend.app.brokers.contamination_isolation import analyze_environment_contamination

            report = analyze_environment_contamination(env, selected_broker=broker_u)
            for finding in report.findings:
                if finding.owner_broker == broker_u:
                    keys.append(finding.field)
        except Exception:
            pass
    if selected == BrokerEnvironmentProfile.PAPER:
        keys.extend(sorted(key for key in LIVE_CREDENTIAL_KEYS if key in broker_keys and env.get(key) not in (None, "")))
    return list(dict.fromkeys(keys))


def _remove_incompatible_profile_variables(env: MutableMapping[str, str], selected: BrokerEnvironmentProfile | None, broker: str = "COINBASE") -> list[str]:
    broker_u = str(broker).upper()
    if broker_u == "COINBASE":
        broker_keys = COINBASE_PROFILE_KEYS
    elif broker_u == "OANDA":
        broker_keys = OANDA_PROFILE_KEYS
    elif broker_u == "BINANCE":
        broker_keys = BINANCE_PROFILE_KEYS
    elif broker_u == "QUESTRADE":
        broker_keys = QUESTRADE_PROFILE_KEYS
    else:
        broker_keys = COINBASE_PROFILE_KEYS
    if selected in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION}:
        keys = TEST_PRACTICE_SANDBOX_KEYS & broker_keys
    elif selected == BrokerEnvironmentProfile.PAPER:
        keys = (LIVE_CREDENTIAL_KEYS | LIVE_AUTHORITY_KEYS) & broker_keys
    else:
        keys = frozenset()
    removed: list[str] = []
    for key in sorted(keys):
        if env.get(key) not in (None, ""):
            env.pop(key, None)
            removed.append(key)
    # Also scrub foreign broker endpoint values that contaminate selected broker keys
    try:
        from backend.app.brokers.contamination_isolation import analyze_environment_contamination

        report = analyze_environment_contamination(env, selected_broker=broker_u)
        for finding in report.findings:
            if finding.code.startswith("CROSS_BROKER") and finding.field in env and finding.owner_broker == broker_u:
                env.pop(finding.field, None)
                removed.append(finding.field)
    except Exception:
        pass
    return list(dict.fromkeys(removed))


def _credential_source(env: Mapping[str, Any], broker: str, loaded_files: list[str]) -> str:
    if broker == "COINBASE":
        if any(env.get(key) not in (None, "") for key in ("COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON", "COINBASE_KEY_FILE")):
            return "PROFILE_KEY_FILE"
        if _any_present(env, COINBASE_KEY_FIELDS) or _any_present(env, COINBASE_PRIVATE_KEY_FIELDS):
            return "PROFILE_ENV"
    if broker == "OANDA":
        if _any_present(env, OANDA_TOKEN_FIELDS) or _any_present(env, OANDA_ACCOUNT_FIELDS):
            return "PROFILE_ENV"
    if broker == "QUESTRADE":
        if _any_present(env, QUESTRADE_TOKEN_FIELDS) or _any_present(env, QUESTRADE_ACCOUNT_FIELDS):
            return "SECURE_REFERENCE_ENV"
    if loaded_files:
        return "PROFILE_FILE_NO_CREDENTIALS"
    return "UNKNOWN"


def _base_url(env: Mapping[str, Any], broker: str, selected: BrokerEnvironmentProfile | None) -> str:
    if broker == "COINBASE":
        value = str(env.get("COINBASE_BASE_URL") or env.get("COINBASE_API_URL") or env.get("COINBASE_REST_URL") or "").strip()
        return value or "https://api.coinbase.com"
    if broker == "OANDA":
        value = str(env.get("OANDA_BASE_URL") or "").strip()
        if value:
            return value
        return "https://api-fxpractice.oanda.com" if selected == BrokerEnvironmentProfile.PAPER else "https://api-fxtrade.oanda.com"
    if broker == "QUESTRADE":
        value = str(
            env.get("QUESTRADE_API_SERVER")
            or env.get("QUESTRADE_BASE_URL")
            or env.get("QUESTRADE_API_URL")
            or ""
        ).strip()
        return value or "https://login.questrade.com/oauth2/token"
    return ""


def _invalid_base_url(base_url: str, selected: BrokerEnvironmentProfile | None) -> bool:
    text = str(base_url or "").strip().lower()
    if not text.startswith("https://"):
        return True
    if selected in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION} and any(token in text for token in ("sandbox", "practice", "demo")):
        return True
    return False


def _permissions_classification(
    env: Mapping[str, Any],
    selected: BrokerEnvironmentProfile | None,
    broker: str,
) -> str:
    if broker == "QUESTRADE":
        return "PAPER_NOT_REQUIRED" if selected == BrokerEnvironmentProfile.PAPER else "READ_ONLY"
    raw = " ".join(str(env.get(key, "") or "").lower() for key in ("COINBASE_API_PERMISSIONS", "COINBASE_SCOPES", "COINBASE_CDP_PERMISSIONS"))
    if selected == BrokerEnvironmentProfile.PAPER:
        return "PAPER_NOT_REQUIRED"
    if any(token in raw for token in ("trade", "order", "transfer", "write")):
        return "ORDER_CAPABLE"
    if any(token in raw for token in ("view", "read", "account", "portfolio", "product", "market")):
        return "READ_ONLY"
    return "UNKNOWN"


def _profile_fingerprint(
    *,
    selected: BrokerEnvironmentProfile | None,
    broker: str,
    environment: str,
    env: Mapping[str, Any],
    loaded_files: list[str],
) -> str:
    present = sorted(
        key
        for key in env
        if key in PROFILE_SPECIFIC_KEYS and env.get(key) not in (None, "")
    )
    payload = {
        "profile": selected.value if selected else "UNSELECTED",
        "broker": broker,
        "environment": environment,
        "present_keys": present,
        "loaded_file_names": [Path(item).name for item in loaded_files],
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _any_present(env: Mapping[str, Any], keys: tuple[str, ...] | frozenset[str]) -> bool:
    return any(env.get(key) not in (None, "") for key in keys)


def _truthy_any(env: Mapping[str, Any], keys: frozenset[str]) -> bool:
    return any(_truthy(env.get(key)) for key in keys)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "armed"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


__all__ = [
    "BrokerEnvironmentCredentials",
    "BrokerEnvironmentProfile",
    "BINANCE_PROFILE_KEYS",
    "COINBASE_PROFILE_KEYS",
    "LIVE_AUTHORITY_KEYS",
    "OANDA_PROFILE_KEYS",
    "PROFILE_SELECTION_KEYS",
    "PROFILE_SPECIFIC_KEYS",
    "QUESTRADE_PROFILE_KEYS",
    "build_broker_environment",
    "legacy_variable_migration_register",
    "profile_mode_alias",
    "profile_trace",
    "sanitize_broker_profile_environment",
    "select_broker_environment_profile",
]
