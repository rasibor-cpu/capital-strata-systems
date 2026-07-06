from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from backend.runtime.broker_startup_selection import BrokerStartupSelection, build_startup_broker_selection
from backend.runtime.broker_readiness_framework import broker_readiness_payload, build_broker_readiness_snapshot
from backend.runtime.broker_credential_diagnostics import (
    authority_reason_from_diagnostics,
    diagnose_broker_credentials,
)
from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter
from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.live_readiness_state_machine import evaluate_live_readiness_state


TOKEN_ENV_VARS = ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN")
ACCOUNT_ENV_VARS = ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID")
URL_ENV_VARS = ("OANDA_BASE_URL",)


@dataclass(frozen=True)
class OandaCredentialDiagnostics:
    token_present: bool
    account_present: bool
    url_present: bool
    missing_credentials: list[str] = field(default_factory=list)
    canonical: dict[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.token_present and self.account_present and self.url_present

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "oanda_token_present": self.token_present,
            "oanda_account_present": self.account_present,
            "oanda_base_url_present": self.url_present,
            "missing_credentials": list(self.missing_credentials),
            "credential_status": "PRESENT" if self.ready else "MISSING",
            "redacted": True,
        }
        if self.canonical:
            payload.update(dict(self.canonical))
            payload["broker_credential_diagnostics"] = dict(self.canonical)
            payload["oanda_token_present"] = self.token_present
            payload["oanda_account_present"] = self.account_present
            payload["oanda_base_url_present"] = self.url_present
        return payload


def oanda_credential_diagnostics(env: Mapping[str, Any] | None = None) -> OandaCredentialDiagnostics:
    source = env if isinstance(env, Mapping) else os.environ
    canonical = diagnose_broker_credentials("oanda", env=source).as_dict()
    token_present = _any_present(source, TOKEN_ENV_VARS)
    account_present = _any_present(source, ACCOUNT_ENV_VARS)
    url_present = _any_present(source, URL_ENV_VARS)
    missing: list[str] = []
    if not token_present:
        missing.append("OANDA_API_KEY|OANDA_ACCESS_TOKEN|OANDA_TOKEN")
    if not account_present:
        missing.append("OANDA_ACCOUNT_ID|OANDA_LIVE_ACCOUNT_ID|OANDA_PRACTICE_ACCOUNT_ID")
    if not url_present:
        missing.append("OANDA_BASE_URL")
    return OandaCredentialDiagnostics(
        token_present=token_present,
        account_present=account_present,
        url_present=url_present,
        missing_credentials=missing,
        canonical=canonical,
    )


def confirm_oanda_live_read_only(value: Any) -> dict[str, Any]:
    accepted = str(value or "").strip().upper() == "LIVE"
    return {
        "accepted": accepted,
        "broker_mode": "live" if accepted else "paper",
        "reason": "oanda_live_read_only_confirmed" if accepted else "oanda_live_confirmation_missing_or_invalid",
        "required_confirmation": "LIVE",
    }


def oanda_live_limit_reconciliation(*, legacy_limit_usd: Any = 1.0) -> dict[str, Any]:
    try:
        legacy = max(0.0, float(legacy_limit_usd))
    except (TypeError, ValueError):
        legacy = 1.0
    return {
        "canonical_authority": "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR",
        "canonical_live_pilot_limit_cad": "20.00",
        "legacy_secondary_limit_label": "LEGACY_SECONDARY_LIMIT",
        "legacy_oanda_max_live_order_usd": round(legacy, 2),
        "effective_order_limit_note": "Phase 152A CAD 20 governor is authoritative; legacy OANDA USD limit is an additional stricter broker-side guard only if live execution is separately armed.",
        "execution_allowed": False,
        "advisory_only": True,
    }


def evaluate_oanda_live_read_only(
    selection: BrokerStartupSelection,
    *,
    env: Mapping[str, Any] | None = None,
    adapter_factory: Callable[[], Any] | None = None,
    legacy_limit_usd: Any = 1.0,
) -> dict[str, Any]:
    diagnostics = oanda_credential_diagnostics(env)
    canonical_diagnostics = diagnostics.as_dict().get("broker_credential_diagnostics", diagnostics.as_dict())
    authority_reason = authority_reason_from_diagnostics(canonical_diagnostics)
    result: dict[str, Any] = {
        "selected_broker": selection.selected_broker,
        "broker_type": _broker_type(selection.selected_broker),
        "broker_mode": selection.broker_mode,
        "execution_scope": "LIVE READ-ONLY VALIDATION" if selection.selected_broker != "NONE" and selection.broker_mode == "live" else "PAPER_OR_NOT_SELECTED",
        "broker_execution_status": "DISABLED",
        "can_live_execute": False,
        "broker_connected": False,
        "broker_authenticated": False,
        "broker_health": "UNKNOWN" if selection.selected_broker == "OANDA" else "DISABLED",
        "infrastructure_health": "UNKNOWN" if selection.selected_broker != "NONE" else "DISABLED",
        "credentials_health": "UNKNOWN",
        "authentication_health": "NOT_TESTED",
        "connection_health": "NOT_CONNECTED",
        "market_data_health": "NOT_TESTED",
        "account_data_health": "UNAVAILABLE",
        "auth_reason": "not_oanda_live_read_only",
        "read_checks": {
            "account": "NOT_ATTEMPTED",
            "balances": "NOT_ATTEMPTED",
            "positions": "NOT_ATTEMPTED",
            "products_or_prices": "NOT_ATTEMPTED",
        },
        "credential_diagnostics": diagnostics.as_dict(),
        "broker_credential_diagnostics": dict(canonical_diagnostics),
        "limit_reconciliation": oanda_live_limit_reconciliation(legacy_limit_usd=legacy_limit_usd),
        "advisory_only": True,
        "execution_allowed": False,
        "live_order_permission": False,
        "connection_error": "",
        "last_successful_sync": "",
        "last_broker_sync": "DATA UNAVAILABLE",
        "account_equity": None,
        "cash": None,
        "buying_power": None,
        "available_balance": None,
        "products_loaded": 0,
        "market_data_status": "NOT_TESTED",
        "drawdown_status": "UNKNOWN",
        "drawdown_reason": "Broker balance unavailable",
        "broker_guard": "REJECT_BEFORE_BROKER",
        "live_micro_pilot_state": "DISARMED",
        "operator_requested_live": bool(selection.operator_requested_live),
        "execution_authority": False,
        "authority_reason": authority_reason if selection.operator_requested_live else "Operator Intent Missing",
        "live_authority_state": "BLOCKED",
    }
    result["broker_readiness"] = broker_readiness_payload(
        build_broker_readiness_snapshot(
            {
                **result,
                "broker_name": result["selected_broker"],
                "mode": result["broker_mode"],
                "execution_supported": result["selected_broker"] in {"COINBASE", "OANDA"},
                "execution_enabled": False,
            }
        )
    )

    if selection.selected_broker != "OANDA" or selection.broker_mode != "live":
        return _apply_readiness_state(result)

    if not diagnostics.ready:
        result["auth_reason"] = "missing credentials"
        result["broker_health"] = "UNKNOWN"
        result["connection_status"] = "UNKNOWN"
        result["connection_error"] = "missing credentials"
        result["credential_status"] = "MISSING"
        result["authority_block_reason"] = authority_reason
        return _apply_readiness_state(result)

    try:
        read_client = adapter_factory() if adapter_factory is not None else None
        adapter = OandaLiveReadOnlyAdapter(env=env, read_client=read_client)
        adapter_status = adapter.sync()
        result.update(adapter_status)
        authenticated = bool(adapter_status.get("broker_authenticated"))
        canonical_diagnostics = diagnose_broker_credentials(
            "oanda",
            env=env,
            authentication_attempted=True,
            authenticated=authenticated,
            failure_reason=None if authenticated else str(adapter_status.get("connection_error") or "AUTH_FAILED"),
        ).as_dict()
        result["credential_diagnostics"] = {**diagnostics.as_dict(), **canonical_diagnostics, "broker_credential_diagnostics": canonical_diagnostics}
        result["broker_credential_diagnostics"] = canonical_diagnostics
        result["auth_reason"] = (
            "oanda_read_only_authentication_verified"
            if adapter_status.get("broker_authenticated")
            else str(adapter_status.get("connection_error") or "oanda_read_only_authentication_pending")
        )
        result["read_checks"] = {
            "account": "OK" if adapter_status.get("account_loaded") else "FAILED",
            "balances": "OK" if adapter_status.get("account_loaded") else "FAILED",
            "positions": "OK" if adapter_status.get("positions_loaded") else "FAILED",
            "products_or_prices": "OK" if adapter_status.get("products_loaded", 0) > 0 else "FAILED",
        }
        result["account_read_status"] = result["read_checks"]["account"]
        result["auth_status"] = "AUTHENTICATED" if result["broker_authenticated"] else "NOT_AUTHENTICATED"
        result["balance_position_status"] = result["read_checks"]["balances"]
        result["product_price_status"] = result["market_data_status"]
    except Exception as exc:
        canonical_diagnostics = diagnose_broker_credentials(
            "oanda",
            env=env,
            authentication_attempted=True,
            authenticated=False,
            exception=exc,
        ).as_dict()
        result["credential_diagnostics"] = {**diagnostics.as_dict(), **canonical_diagnostics, "broker_credential_diagnostics": canonical_diagnostics}
        result["broker_credential_diagnostics"] = canonical_diagnostics
        result["broker_health"] = "UNKNOWN"
        result["connection_status"] = "UNKNOWN"
        result["connection_error"] = str(exc)[:160]
        result["auth_reason"] = f"oanda_read_only_auth_failed:{str(exc)[:120]}"
    return _apply_readiness_state(result)


def selection_with_oanda_readiness(
    selection: BrokerStartupSelection,
    readiness: Mapping[str, Any],
) -> BrokerStartupSelection:
    return build_startup_broker_selection(
        selected_broker=selection.selected_broker,
        broker_mode=selection.broker_mode,
        broker_execution_armed=False,
        operator_requested_live=selection.operator_requested_live,
        execution_authority=False,
        authority_reason=str(readiness.get("authority_reason", "Operator Intent Missing")),
        live_authority_state=str(readiness.get("live_authority_state", "BLOCKED")),
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
            "broker_credential_diagnostics": dict(readiness.get("broker_credential_diagnostics", {}))
            if isinstance(readiness.get("broker_credential_diagnostics"), Mapping)
            else dict(_mapping(readiness.get("credential_diagnostics")).get("broker_credential_diagnostics", {})),
            "limit_reconciliation": dict(readiness.get("limit_reconciliation", {})),
            "execution_scope": str(readiness.get("execution_scope", state.get("broker_connection_mode", ""))),
            "auth_reason": str(readiness.get("auth_reason", state.get("readiness_reason", ""))),
            "can_live_execute": False,
            "operator_requested_live": bool(readiness.get("operator_requested_live", state.get("operator_requested_live", False))),
            "execution_authority": False,
            "authority_reason": str(readiness.get("authority_reason", state.get("authority_reason", "Operator Intent Missing"))),
            "live_authority_state": str(readiness.get("live_authority_state", state.get("live_authority_state", "BLOCKED"))),
            "broker_execution_enabled": False,
            "live_order_permission": False,
            "execution_allowed": False,
            "credential_status": str(readiness.get("credential_status", "")),
            "broker_type": str(readiness.get("broker_type", _mapping(readiness.get("broker_readiness")).get("broker_type", _broker_type(state.get("selected_broker"))))),
            "infrastructure_health": str(readiness.get("infrastructure_health", _mapping(readiness.get("broker_readiness")).get("infrastructure_health", "UNKNOWN"))),
            "credentials_health": str(readiness.get("credentials_health", _mapping(readiness.get("broker_readiness")).get("credentials_health", "UNKNOWN"))),
            "authentication_health": str(readiness.get("authentication_health", _mapping(readiness.get("broker_readiness")).get("authentication_health", "UNKNOWN"))),
            "connection_health": str(readiness.get("connection_health", _mapping(readiness.get("broker_readiness")).get("connection_health", "UNKNOWN"))),
            "market_data_health": str(readiness.get("market_data_health", _mapping(readiness.get("broker_readiness")).get("market_data_health", "UNKNOWN"))),
            "account_data_health": str(readiness.get("account_data_health", _mapping(readiness.get("broker_readiness")).get("account_data_health", "UNKNOWN"))),
            "auth_status": str(readiness.get("auth_status", "")),
            "connection_status": str(readiness.get("connection_status", "")),
            "product_price_status": str(readiness.get("product_price_status", "")),
            "balance_position_status": str(readiness.get("balance_position_status", "")),
            "order_submission_status": str(readiness.get("order_submission_status", "DISABLED")),
            "orders_sent_count": int(readiness.get("orders_sent_count", 0) or 0),
            "orders_blocked_count": int(readiness.get("orders_blocked_count", 0) or 0),
            "connection_error": str(readiness.get("connection_error", "")),
            "last_successful_sync": str(readiness.get("last_successful_sync", "")),
            "last_broker_sync": str(readiness.get("last_broker_sync", "DATA UNAVAILABLE")),
            "account_equity": readiness.get("account_equity"),
            "cash": readiness.get("cash"),
            "buying_power": readiness.get("buying_power"),
            "available_balance": readiness.get("available_balance"),
            "products_loaded": int(readiness.get("products_loaded", 0) or 0),
            "market_data_status": str(readiness.get("market_data_status", readiness.get("product_price_status", "NOT_TESTED"))),
            "drawdown_status": str(readiness.get("drawdown_status", "UNKNOWN")),
            "drawdown_reason": str(readiness.get("drawdown_reason", "Broker balance unavailable")),
            "live_micro_pilot_state": str(readiness.get("live_micro_pilot_state", "DISARMED")),
            "broker_guard": str(readiness.get("broker_guard", "REJECT_BEFORE_BROKER")),
            "oanda_live_validation": dict(readiness.get("oanda_live_validation", {}))
            if isinstance(readiness.get("oanda_live_validation"), Mapping)
            else {},
            "broker_readiness": dict(readiness.get("broker_readiness", {}))
            if isinstance(readiness.get("broker_readiness"), Mapping)
            else broker_readiness_payload(build_broker_readiness_snapshot(readiness)),
            "readiness_score": readiness.get("readiness_score", _mapping(readiness.get("broker_readiness")).get("readiness_score", 0.0)),
            "readiness_state": str(readiness.get("readiness_state", "UNCONFIGURED")),
            "go_no_go": str(readiness.get("go_no_go", "NO GO")),
            "readiness_checklist": list(readiness.get("readiness_checklist", []))
            if isinstance(readiness.get("readiness_checklist"), list)
            else [],
            "startup_diagnostics": dict(readiness.get("startup_diagnostics", {}))
            if isinstance(readiness.get("startup_diagnostics"), Mapping)
            else {},
        }
    )
    authority = evaluate_live_execution_authority(state).as_dict()
    state.update(
        {
            "operator_requested_live": bool(authority.get("operator_requested_live", state.get("operator_requested_live", False))),
            "execution_authority": False,
            "authority_reason": str(authority.get("authority_reason", state.get("authority_reason", "Operator Intent Missing"))),
            "live_authority_state": str(authority.get("live_authority_state", state.get("live_authority_state", "BLOCKED"))),
            "live_execution_authority": authority,
            "broker_execution_enabled": False,
            "broker_execution_status": "DISABLED",
            "can_live_execute": False,
        }
    )
    return state


def _apply_readiness_state(result: dict[str, Any]) -> dict[str, Any]:
    authority = evaluate_live_execution_authority(result).as_dict()
    result["operator_requested_live"] = bool(authority.get("operator_requested_live", result.get("operator_requested_live", False)))
    result["execution_authority"] = False
    result["authority_reason"] = str(authority.get("authority_reason", result.get("authority_reason", "Operator Intent Missing")))
    result["live_authority_state"] = str(authority.get("live_authority_state", "BLOCKED"))
    result["live_execution_authority"] = authority
    result["broker_execution_enabled"] = False
    result["broker_execution_status"] = "DISABLED"
    result["can_live_execute"] = False
    readiness = evaluate_live_readiness_state(result).as_dict()
    result["readiness_state"] = readiness["readiness_state"]
    result["go_no_go"] = readiness["go_no_go"]
    result["readiness_checklist"] = readiness["readiness_checklist"]
    result["startup_diagnostics"] = readiness["startup_diagnostics"]
    return result


def _any_present(env: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return any(bool(str(env.get(name, "")).strip()) for name in names)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _broker_type(broker: Any) -> str:
    text = str(broker or "NONE").strip().upper()
    if text == "COINBASE":
        return "CRYPTO"
    if text == "OANDA":
        return "FX"
    if text == "IBKR":
        return "MULTI_ASSET"
    return "NONE"


__all__ = [
    "oanda_credential_diagnostics",
    "oanda_live_limit_reconciliation",
    "confirm_oanda_live_read_only",
    "evaluate_oanda_live_read_only",
    "merge_readiness_into_broker_state",
    "selection_with_oanda_readiness",
]
