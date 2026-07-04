from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from backend.runtime.broker_startup_selection import BrokerStartupSelection, build_startup_broker_selection


KEY_NAME_ENV_VARS = ("COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY")
PRIVATE_KEY_ENV_VARS = (
    "COINBASE_CDP_PRIVATE_KEY",
    "COINBASE_PRIVATE_KEY",
    "COINBASE_API_SECRET",
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
)
KEY_FILE_ENV_VARS = ("COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON", "COINBASE_KEY_FILE")


@dataclass(frozen=True)
class CoinbaseCredentialDiagnostics:
    key_present: bool
    private_key_present: bool
    key_file_present: bool
    missing_credentials: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.key_present and (self.private_key_present or self.key_file_present)

    def as_dict(self) -> dict[str, Any]:
        return {
            "coinbase_key_present": self.key_present,
            "coinbase_private_key_present": self.private_key_present,
            "coinbase_key_file_present": self.key_file_present,
            "missing_credentials": list(self.missing_credentials),
            "credential_status": "PRESENT" if self.ready else "MISSING",
            "redacted": True,
        }


def coinbase_credential_diagnostics(env: Mapping[str, Any] | None = None) -> CoinbaseCredentialDiagnostics:
    source = env if isinstance(env, Mapping) else os.environ
    key_present = _any_present(source, KEY_NAME_ENV_VARS)
    private_key_present = _any_present(source, PRIVATE_KEY_ENV_VARS)
    key_file_present = _any_present(source, KEY_FILE_ENV_VARS)
    missing: list[str] = []
    if not key_present:
        missing.append("COINBASE_CDP_KEY_NAME|COINBASE_KEY_NAME|COINBASE_API_KEY")
    if not private_key_present and not key_file_present:
        missing.append("COINBASE_CDP_PRIVATE_KEY|COINBASE_PRIVATE_KEY|COINBASE_API_SECRET|COINBASE_KEY_FILE")
    return CoinbaseCredentialDiagnostics(
        key_present=key_present,
        private_key_present=private_key_present,
        key_file_present=key_file_present,
        missing_credentials=missing,
    )


def confirm_coinbase_live_read_only(value: Any) -> dict[str, Any]:
    accepted = str(value or "") == "LIVE"
    return {
        "accepted": accepted,
        "broker_mode": "live" if accepted else "paper",
        "reason": "coinbase_live_read_only_confirmed" if accepted else "coinbase_live_confirmation_missing_or_invalid",
        "required_confirmation": "LIVE",
    }


def coinbase_live_limit_reconciliation(*, legacy_limit_usd: Any = 1.0) -> dict[str, Any]:
    try:
        legacy = max(0.0, float(legacy_limit_usd))
    except (TypeError, ValueError):
        legacy = 1.0
    return {
        "canonical_authority": "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR",
        "canonical_live_pilot_limit_cad": "20.00",
        "legacy_secondary_limit_label": "LEGACY_SECONDARY_LIMIT",
        "legacy_coinbase_max_live_order_usd": round(legacy, 2),
        "effective_order_limit_note": "Phase 152A CAD 20 governor is authoritative; legacy Coinbase USD limit is an additional stricter broker-side guard only if live execution is separately armed.",
        "execution_allowed": False,
        "advisory_only": True,
    }


def evaluate_coinbase_live_read_only(
    selection: BrokerStartupSelection,
    *,
    env: Mapping[str, Any] | None = None,
    adapter_factory: Callable[[], Any] | None = None,
    legacy_limit_usd: Any = 1.0,
) -> dict[str, Any]:
    diagnostics = coinbase_credential_diagnostics(env)
    result: dict[str, Any] = {
        "selected_broker": selection.selected_broker,
        "broker_mode": selection.broker_mode,
        "execution_scope": "LIVE READ-ONLY VALIDATION" if selection.selected_broker == "COINBASE" and selection.broker_mode == "live" else "PAPER_OR_NOT_SELECTED",
        "broker_execution_status": "DISABLED",
        "can_live_execute": False,
        "broker_connected": False,
        "broker_authenticated": False,
        "broker_health": "UNKNOWN" if selection.selected_broker == "COINBASE" else "DISABLED",
        "auth_reason": "not_coinbase_live_read_only",
        "read_checks": {
            "account": "NOT_ATTEMPTED",
            "balances": "NOT_ATTEMPTED",
            "positions": "NOT_ATTEMPTED",
            "products_or_prices": "NOT_ATTEMPTED",
        },
        "credential_diagnostics": diagnostics.as_dict(),
        "limit_reconciliation": coinbase_live_limit_reconciliation(legacy_limit_usd=legacy_limit_usd),
        "advisory_only": True,
        "execution_allowed": False,
        "live_order_permission": False,
    }

    if selection.selected_broker != "COINBASE" or selection.broker_mode != "live":
        return result

    if not diagnostics.ready:
        result["auth_reason"] = "missing credentials"
        result["broker_health"] = "MISSING_CREDENTIALS"
        return result

    if adapter_factory is None:
        from backend.app.brokers.broker_bootstrap import initialize_broker

        adapter_factory = lambda: initialize_broker("coinbase", "live")

    try:
        adapter = adapter_factory()
        result["broker_authenticated"] = True
        account_payload = _try_read(adapter, ("get_account", "get_account_balance", "get_account_summary"))
        accounts_payload = _try_read(adapter, ("get_accounts",))
        positions_payload = _try_read(adapter, ("get_positions", "list_positions"))
        products_payload = _try_read(adapter, ("get_products", "list_products", "get_product", "get_price"))
        result["read_checks"] = {
            "account": _status(account_payload),
            "balances": _status(account_payload if account_payload is not None else accounts_payload),
            "positions": _status(positions_payload, unavailable_ok=True),
            "products_or_prices": _status(products_payload, unavailable_ok=True),
        }
        result["broker_connected"] = True
        result["broker_health"] = "GREEN"
        result["auth_reason"] = "coinbase_read_only_authentication_verified"
        result["account_read_status"] = result["read_checks"]["account"]
    except Exception as exc:
        result["broker_health"] = "AUTH_FAILED"
        result["auth_reason"] = f"coinbase_read_only_auth_failed:{str(exc)[:120]}"
    return result


def selection_with_coinbase_readiness(
    selection: BrokerStartupSelection,
    readiness: Mapping[str, Any],
) -> BrokerStartupSelection:
    return build_startup_broker_selection(
        selected_broker=selection.selected_broker,
        broker_mode=selection.broker_mode,
        broker_execution_armed=False,
        broker_connected=bool(readiness.get("broker_connected", False)),
        broker_authenticated=bool(readiness.get("broker_authenticated", False)),
        broker_health=str(readiness.get("broker_health", "UNKNOWN")),
        broker_readiness_status="READ_ONLY_CONNECTED" if readiness.get("broker_connected") else "READ_ONLY_PENDING",
        readiness_reason=str(readiness.get("auth_reason", "broker_read_only_connection_pending")),
    )


def merge_readiness_into_broker_state(selection: BrokerStartupSelection, readiness: Mapping[str, Any]) -> dict[str, Any]:
    state = selection.as_dict()
    state.update(
        {
            "credential_diagnostics": dict(readiness.get("credential_diagnostics", {})),
            "limit_reconciliation": dict(readiness.get("limit_reconciliation", {})),
            "execution_scope": str(readiness.get("execution_scope", state.get("broker_connection_mode", ""))),
            "auth_reason": str(readiness.get("auth_reason", state.get("readiness_reason", ""))),
            "can_live_execute": False,
            "live_order_permission": False,
            "execution_allowed": False,
        }
    )
    return state


def _any_present(env: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return any(bool(str(env.get(name, "")).strip()) for name in names)


def _try_read(adapter: Any, method_names: tuple[str, ...]) -> Any:
    for name in method_names:
        method = getattr(adapter, name, None)
        if callable(method):
            return method()
    return None


def _status(payload: Any, *, unavailable_ok: bool = False) -> str:
    if payload is None:
        return "UNAVAILABLE" if unavailable_ok else "FAILED"
    return "OK"


__all__ = [
    "CoinbaseCredentialDiagnostics",
    "coinbase_credential_diagnostics",
    "coinbase_live_limit_reconciliation",
    "confirm_coinbase_live_read_only",
    "evaluate_coinbase_live_read_only",
    "merge_readiness_into_broker_state",
    "selection_with_coinbase_readiness",
]
