"""Phase 189 — controlled online precheck (NO authentication)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.audit_matrix import (
    BROKER_AUDIT_MATRIX,
    get_capability_profile,
)
from backend.app.brokers.multi_broker_readiness.contracts import (
    SCHEMA_VERSION,
    AssetClass,
    BrokerType,
)

CREDENTIAL_KEYS: Mapping[str, tuple[str, ...]] = {
    "OANDA": ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN"),
    "COINBASE": ("COINBASE_API_KEY", "COINBASE_API_SECRET", "CDP_API_KEY_NAME"),
    "BINANCE": ("BINANCE_API_KEY", "BINANCE_API_SECRET"),
    "QUESTRADE": ("QUESTRADE_REFRESH_TOKEN", "QUESTRADE_ACCESS_TOKEN"),
    "IBKR": ("IBKR_ACCOUNT_ID", "IBKR_HOST"),
    "PLUGIN": ("BROKER_API_KEY",),
}

ENDPOINT_KEYS: Mapping[str, tuple[str, ...]] = {
    "OANDA": ("OANDA_BASE_URL",),
    "COINBASE": ("COINBASE_BASE_URL", "COINBASE_API_URL"),
    "BINANCE": ("BINANCE_BASE_URL",),
    "QUESTRADE": ("QUESTRADE_API_SERVER", "QUESTRADE_BASE_URL"),
    "IBKR": ("IBKR_HOST",),
    "PLUGIN": ("BROKER_BASE_URL",),
}

ACCOUNT_KEYS: Mapping[str, tuple[str, ...]] = {
    "OANDA": ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID"),
    "COINBASE": ("COINBASE_PORTFOLIO_ID", "COINBASE_ACCOUNT_ID"),
    "BINANCE": ("BINANCE_ACCOUNT_ID",),
    "QUESTRADE": ("QUESTRADE_ACCOUNT_ID",),
    "IBKR": ("IBKR_ACCOUNT_ID",),
    "PLUGIN": ("BROKER_ACCOUNT_ID",),
}


@dataclass(frozen=True)
class ControlledOnlinePrecheck:
    schema_id: str = "BROKER_CONTROLLED_ONLINE_PRECHECK"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    asset_class: str = AssetClass.NONE.value
    status: str = "BLOCKED"
    credentials_present: bool = False
    endpoint_valid: bool = False
    environment_valid: bool = False
    configuration_complete: bool = False
    provider_compatible: bool = False
    schema_compatible: bool = False
    capability_compatible: bool = False
    authentication_performed: bool = False
    blockers: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["authentication_performed"] = False
        return payload

    def __post_init__(self) -> None:
        if self.authentication_performed:
            raise ValueError("precheck must not authenticate")


def run_controlled_online_precheck(
    broker: BrokerType | str,
    env: Mapping[str, Any],
    *,
    asset_class: AssetClass | str = AssetClass.NONE,
    expected_schema_version: str = SCHEMA_VERSION,
    provider_version: str = "189.1",
) -> ControlledOnlinePrecheck:
    broker_key = broker.value if isinstance(broker, BrokerType) else str(broker).upper()
    asset_key = asset_class.value if isinstance(asset_class, AssetClass) else str(asset_class).upper()
    blockers: list[str] = []
    diagnostics: dict[str, Any] = {"redacted": True, "authentication_performed": False}

    audit = BROKER_AUDIT_MATRIX.get(broker_key)
    profile = get_capability_profile(broker_key)
    if audit is None:
        blockers.append("unknown_broker")
        provider_compatible = False
    else:
        provider_compatible = audit["classification"] in {"COMPLETE", "PARTIAL"}
        if audit["classification"] == "BLOCKED":
            blockers.append(f"broker_blocked:{broker_key}")
            provider_compatible = False
        if audit["classification"] == "NOT_STARTED":
            blockers.append(f"broker_ops_not_started:{broker_key}")

    capability_compatible = profile.supports_asset_class(asset_key)
    if not capability_compatible:
        blockers.append(f"capability_incompatible:{asset_key}")

    cred_keys = CREDENTIAL_KEYS.get(broker_key, CREDENTIAL_KEYS["PLUGIN"])
    credentials_present = _any_present(env, cred_keys)
    diagnostics["credential_keys_checked"] = list(cred_keys)
    diagnostics["credentials_present"] = credentials_present
    if not credentials_present:
        blockers.append("credentials_missing")

    endpoint_keys = ENDPOINT_KEYS.get(broker_key, ENDPOINT_KEYS["PLUGIN"])
    endpoint_value = _first_present(env, endpoint_keys)
    endpoint_valid = bool(endpoint_value) and (
        endpoint_value.lower().startswith("https://") or broker_key == "IBKR"
    )
    diagnostics["endpoint_present"] = bool(endpoint_value)
    diagnostics["endpoint_valid"] = endpoint_valid
    if not endpoint_valid:
        blockers.append("endpoint_invalid_or_missing")

    account_keys = ACCOUNT_KEYS.get(broker_key, ACCOUNT_KEYS["PLUGIN"])
    account_present = _any_present(env, account_keys) if account_keys else credentials_present
    environment_valid = credentials_present and endpoint_valid
    configuration_complete = environment_valid and account_present
    if not account_present and account_keys:
        blockers.append("account_identifier_missing")
    if not environment_valid:
        blockers.append("environment_invalid")
    if not configuration_complete:
        blockers.append("configuration_incomplete")

    schema_compatible = expected_schema_version.startswith("189.")
    if not schema_compatible:
        blockers.append("schema_incompatible")
    if not str(provider_version).startswith("189."):
        blockers.append("provider_incompatible")
        provider_compatible = False

    status = "PASS" if not blockers else "BLOCKED"
    return ControlledOnlinePrecheck(
        broker_type=broker_key,
        asset_class=asset_key,
        status=status,
        credentials_present=credentials_present,
        endpoint_valid=endpoint_valid,
        environment_valid=environment_valid,
        configuration_complete=configuration_complete,
        provider_compatible=provider_compatible,
        schema_compatible=schema_compatible,
        capability_compatible=capability_compatible,
        authentication_performed=False,
        blockers=tuple(blockers),
        diagnostics=diagnostics,
    )


def _any_present(env: Mapping[str, Any], keys: Sequence[str]) -> bool:
    return any(bool(str(env.get(k, "") or "").strip()) for k in keys)


def _first_present(env: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = str(env.get(key, "") or "").strip()
        if value:
            return value
    return ""
