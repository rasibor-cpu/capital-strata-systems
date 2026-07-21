from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


# Phase 177C Revision B — startup selection. IBKR removed from roadmap.
# BINANCE / QUESTRADE are Tier-1 registered but not yet live-startup enabled.
SUPPORTED_STARTUP_BROKERS = {
    "1": "NONE",
    "2": "COINBASE",
    "3": "OANDA",
    "4": "BINANCE",
    "5": "QUESTRADE",
}

TIER1_STARTUP_BROKERS = frozenset({"NONE", "COINBASE", "OANDA", "BINANCE", "QUESTRADE"})
STARTUP_LIVE_ENABLED_BROKERS = frozenset({"COINBASE", "OANDA"})  # read-only validation path today

CANONICAL_STARTUP_SEQUENCE = (
    "authenticate_startup_user",
    "select_global_broker_mode",
    "select_startup_broker_selection",
    "select_broker_execution_config",
    "select_engine_mode",
    "select_cycle_mode",
)


@dataclass(frozen=True)
class BrokerStartupSelection:
    selected_broker: str = "NONE"
    broker_mode: str = "paper"
    broker_execution_armed: bool = False
    operator_requested_live: bool = False
    execution_authority: bool = False
    authority_reason: str = "Operator Intent Missing"
    live_authority_state: str = "BLOCKED"
    broker_connected: bool = False
    broker_authenticated: bool = False
    broker_health: str = "DISABLED"
    broker_readiness_status: str = "BROKER_DISABLED"
    broker_execution_status: str = "DISABLED"
    broker_connection_mode: str = "PAPER_ONLY"
    readiness_reason: str = "no_live_broker_selected"
    timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = payload["timestamp"] or _utc_now()
        payload["advisory_only"] = True
        payload["execution_allowed"] = False
        payload["live_order_permission"] = False
        payload["operator_requested_live"] = bool(payload.get("operator_requested_live", False))
        payload["execution_authority"] = bool(payload.get("execution_authority", False))
        payload["authority_reason"] = payload.get("authority_reason") or "Operator Intent Missing"
        payload["live_authority_state"] = payload.get("live_authority_state") or "BLOCKED"
        payload["broker_execution_enabled"] = bool(payload.get("execution_authority", False))
        payload["broker_execution_status"] = "ENABLED" if payload["execution_authority"] else "DISABLED"
        payload["can_live_execute"] = False
        payload["execution_scope"] = (
            "LIVE READ-ONLY VALIDATION"
            if payload["selected_broker"] != "NONE" and payload["broker_mode"] == "live"
            else payload["broker_connection_mode"]
        )
        payload["live_micro_pilot_state"] = "DISARMED"
        payload["broker_guard"] = "REJECT_BEFORE_BROKER"
        payload.setdefault("last_broker_sync", "DATA UNAVAILABLE")
        payload.setdefault("products_loaded", 0)
        payload.setdefault("market_data_status", "NOT_TESTED")
        payload.setdefault("drawdown_status", "NOT_COMPUTABLE")
        payload.setdefault("drawdown_reason", "Broker balance unavailable")
        payload.setdefault("readiness_state", "UNCONFIGURED")
        payload.setdefault("go_no_go", "NO GO")
        payload.setdefault("readiness_checklist", [])
        payload.setdefault("startup_diagnostics", {})
        payload.setdefault("broker_readiness", {})
        payload.setdefault("broker_type", _broker_type(payload.get("selected_broker")))
        payload.setdefault("infrastructure_health", "UNKNOWN")
        payload.setdefault("credentials_health", "UNKNOWN")
        payload.setdefault("authentication_health", "UNKNOWN")
        payload.setdefault("connection_health", "UNKNOWN")
        payload.setdefault("market_data_health", "UNKNOWN")
        payload.setdefault("account_data_health", "UNKNOWN")
        payload.setdefault("readiness_score", 0.0)
        if payload["selected_broker"] in {"COINBASE", "BINANCE", "OANDA", "QUESTRADE"}:
            from backend.app.brokers.operational_adapter import get_operational_adapter

            operational = get_operational_adapter(payload["selected_broker"]).operational_snapshot()
            payload["canonical_operational_state"] = operational["operational_state"]
            payload["canonical_operation_result"] = operational["operation_result"]
            payload["capability_states"] = operational["capability_states"]
            payload["recommended_action"] = operational["recommended_action"]
            payload["expected_condition"] = operational["expected_condition"]
            payload["retryable"] = operational["retryable"]
        else:
            payload["canonical_operational_state"] = "DISABLED"
            payload["canonical_operation_result"] = {}
            payload["capability_states"] = {}
            payload["recommended_action"] = "Select a Tier-1 broker for read-only validation"
            payload["expected_condition"] = True
            payload["retryable"] = False
        payload["execution_state"] = "EXECUTION_BLOCKED"
        return payload


def normalize_broker(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {
        "": "NONE",
        "NO": "NONE",
        "PAPER": "NONE",
        "PAPER_ONLY": "NONE",
        "NONE / PAPER ONLY": "NONE",
        "COINBASE_ADVANCED": "COINBASE",
        "CB": "COINBASE",
        "OANDA_V20": "OANDA",
        "BN": "BINANCE",
        "BINANCE_SPOT": "BINANCE",
        "QT": "QUESTRADE",
        # IBKR explicitly excluded from active roadmap (Revision B)
        "IBKR": "NONE",
        "INTERACTIVE_BROKERS": "NONE",
        "INTERACTIVE BROKERS": "NONE",
    }
    broker = aliases.get(text, text)
    return broker if broker in TIER1_STARTUP_BROKERS else "NONE"


def _broker_type(broker: Any) -> str:
    normalized = normalize_broker(broker)
    if normalized in {"COINBASE", "BINANCE"}:
        return "CRYPTO"
    if normalized == "OANDA":
        return "FX"
    if normalized == "QUESTRADE":
        return "EQUITIES_CA"
    return "NONE"


def normalize_broker_mode(value: Any, *, selected_broker: str = "NONE") -> str:
    mode = str(value or "").strip().lower()
    if selected_broker == "NONE":
        return "paper"
    return "live" if mode in {"live", "real", "production", "prod"} else "paper"


def startup_broker_from_choice(choice: Any, *, ibkr_supported: bool = False) -> str:
    """Map numeric startup choice → broker.

    ``ibkr_supported`` is retained for call-site compatibility but ignored —
    IBKR is not on the Phase 177C roadmap.
    """
    _ = ibkr_supported
    normalized = str(choice or "1").strip()
    broker = SUPPORTED_STARTUP_BROKERS.get(normalized, "NONE")
    # Choices 4/5 (Binance/Questrade) are selectable for future LIVE_READ_ONLY
    # onboarding but do not enable execution.
    return broker


def startup_broker_mode_from_choice(choice: Any, *, selected_broker: str, global_mode: str = "paper") -> str:
    broker = normalize_broker(selected_broker)
    if broker == "NONE":
        return "paper"
    default_choice = "2" if str(global_mode or "").strip().lower() == "live" else "1"
    normalized = str(choice or default_choice).strip()
    return "live" if normalized == "2" else "paper"


def cancelled_startup_selection(reason: str = "operator_cancelled") -> BrokerStartupSelection:
    return build_startup_broker_selection(
        selected_broker="NONE",
        broker_mode="paper",
        broker_execution_armed=False,
        readiness_reason=reason,
    )


def build_startup_broker_selection(
    *,
    selected_broker: Any = "NONE",
    broker_mode: Any = "paper",
    broker_execution_armed: Any = False,
    operator_requested_live: Any = False,
    execution_authority: Any = False,
    authority_reason: Any = "",
    live_authority_state: Any = "",
    broker_connected: Any = False,
    broker_authenticated: Any = False,
    broker_health: Any = "",
    broker_readiness_status: Any = "",
    readiness_reason: Any = "",
) -> BrokerStartupSelection:
    broker = normalize_broker(selected_broker)
    mode = normalize_broker_mode(broker_mode, selected_broker=broker)
    armed = _truthy(broker_execution_armed)
    requested_live = _truthy(operator_requested_live)
    authority = _truthy(execution_authority)
    connected = _truthy(broker_connected)
    authenticated = _truthy(broker_authenticated)
    health = str(broker_health or "").strip().upper()

    if broker == "NONE":
        health = "DISABLED"
        connected = False
        authenticated = False
        armed = False
        readiness = "BROKER_DISABLED"
        connection_mode = "PAPER_ONLY"
        reason = str(readiness_reason or "no_live_broker_selected")
    elif connected and authenticated and health in {"", "UNKNOWN", "DISABLED"}:
        health = "GREEN"
        readiness = "READ_ONLY_CONNECTED"
        connection_mode = "READ_ONLY_LIVE" if mode == "live" else "READ_ONLY_PAPER"
        reason = str(readiness_reason or "broker_read_only_connection_verified")
    else:
        health = health or ("GREEN" if connected and authenticated else "UNKNOWN")
        readiness = str(broker_readiness_status or ("READ_ONLY_CONNECTED" if connected and authenticated else "READ_ONLY_PENDING"))
        connection_mode = "READ_ONLY_LIVE" if mode == "live" else "READ_ONLY_PAPER"
        reason = str(readiness_reason or ("broker_read_only_connection_pending" if not connected else "broker_read_only_connection_observed"))

    return BrokerStartupSelection(
        selected_broker=broker,
        broker_mode=mode,
        broker_execution_armed=armed,
        operator_requested_live=requested_live,
        execution_authority=authority,
        authority_reason=str(authority_reason or ("Authority Granted" if authority else "Operator Intent Missing")),
        live_authority_state=str(live_authority_state or ("AUTHORIZED" if authority else "BLOCKED")),
        broker_connected=connected,
        broker_authenticated=authenticated,
        broker_health=health,
        broker_readiness_status=readiness,
        broker_execution_status="ENABLED" if authority else "DISABLED",
        broker_connection_mode=connection_mode,
        readiness_reason=reason,
        timestamp=_utc_now(),
    )


def broker_summary_from_artifacts(
    account_state: Mapping[str, Any] | None,
    session_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    account = account_state if isinstance(account_state, Mapping) else {}
    session_root = session_state if isinstance(session_state, Mapping) else {}
    session = session_root.get("session", session_root) if isinstance(session_root, Mapping) else {}
    session = session if isinstance(session, Mapping) else {}
    broker_state = _mapping(account.get("broker_state")) or _mapping(session.get("broker_state")) or _mapping(session_root.get("broker_state"))

    selected = broker_state.get("selected_broker") or session.get("selected_broker") or session.get("broker") or account.get("selected_broker") or "NONE"
    mode = broker_state.get("broker_mode") or session.get("broker_mode") or account.get("broker_mode") or "paper"
    selection = build_startup_broker_selection(
        selected_broker=selected,
        broker_mode=mode,
        broker_execution_armed=broker_state.get("broker_execution_armed", session.get("broker_execution_armed", session.get("broker_execution_enabled", False))),
        operator_requested_live=broker_state.get("operator_requested_live", session.get("operator_requested_live", False)),
        execution_authority=broker_state.get("execution_authority", session.get("execution_authority", False)),
        authority_reason=broker_state.get("authority_reason", ""),
        live_authority_state=broker_state.get("live_authority_state", ""),
        broker_connected=broker_state.get("broker_connected", broker_state.get("connected", False)),
        broker_authenticated=broker_state.get("broker_authenticated", broker_state.get("authenticated", False)),
        broker_health=broker_state.get("broker_health", broker_state.get("api_health", "")),
        broker_readiness_status=broker_state.get("broker_readiness_status", broker_state.get("readiness_status", "")),
        readiness_reason=broker_state.get("readiness_reason", ""),
    )
    summary = selection.as_dict()
    override_keys = {
        "readiness_state",
        "go_no_go",
        "readiness_checklist",
        "startup_diagnostics",
        "operator_requested_live",
        "execution_authority",
        "authority_reason",
        "live_authority_state",
        "live_execution_authority",
        "broker_execution_enabled",
        "broker_readiness",
        "broker_type",
        "infrastructure_health",
        "credentials_health",
        "authentication_health",
        "connection_health",
        "market_data_health",
        "account_data_health",
        "readiness_score",
        "last_broker_sync",
        "products_loaded",
        "market_data_status",
        "drawdown_status",
        "drawdown_reason",
    }
    for key, value in broker_state.items():
        if key not in summary or key in override_keys:
            summary[key] = value
    return summary


def persist_broker_selection(
    *,
    account_state_path: str | Path,
    session_state_path: str | Path,
    selection: BrokerStartupSelection,
    broker_state_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    account_path = Path(account_state_path)
    session_path = Path(session_state_path)
    broker_state = dict(broker_state_override) if isinstance(broker_state_override, Mapping) else selection.as_dict()
    account = _read_json(account_path)
    session_state = _read_json(session_path)
    session = session_state.get("session")
    if not isinstance(session, dict):
        session = {}
        session_state["session"] = session

    account.update(
        {
            "selected_broker": selection.selected_broker,
            "broker_mode": selection.broker_mode,
            "broker_connected": selection.broker_connected,
            "broker_health": selection.broker_health,
            "broker_execution_armed": selection.broker_execution_armed,
            "operator_requested_live": broker_state.get("operator_requested_live", selection.operator_requested_live),
            "execution_authority": broker_state.get("execution_authority", selection.execution_authority),
            "authority_reason": broker_state.get("authority_reason", selection.authority_reason),
            "live_authority_state": broker_state.get("live_authority_state", selection.live_authority_state),
            "broker_execution_enabled": False,
            "broker_state": broker_state,
            "advisory_only": True,
            "execution_allowed": False,
        }
    )
    session.update(
        {
            "selected_broker": selection.selected_broker,
            "broker": selection.selected_broker,
            "broker_mode": selection.broker_mode,
            "broker_connected": selection.broker_connected,
            "broker_health": selection.broker_health,
            "broker_execution_armed": selection.broker_execution_armed,
            "operator_requested_live": broker_state.get("operator_requested_live", selection.operator_requested_live),
            "execution_authority": broker_state.get("execution_authority", selection.execution_authority),
            "authority_reason": broker_state.get("authority_reason", selection.authority_reason),
            "live_authority_state": broker_state.get("live_authority_state", selection.live_authority_state),
            "broker_execution_enabled": False,
            "broker_execution_status": selection.broker_execution_status,
            "broker_state": broker_state,
            "advisory_only": True,
            "execution_allowed": False,
        }
    )
    session_state["broker_state"] = broker_state
    _write_json(account_path, account)
    _write_json(session_path, session_state)
    return {"account_state": str(account_path), "session_state": str(session_path), "broker_state": broker_state}


def live_readiness_broker_evidence(broker_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    broker = broker_summary if isinstance(broker_summary, Mapping) else {}
    selected = normalize_broker(broker.get("selected_broker"))
    mode = normalize_broker_mode(broker.get("broker_mode"), selected_broker=selected)
    connected = _truthy(broker.get("broker_connected", broker.get("connected", False)))
    authenticated = _truthy(broker.get("broker_authenticated", broker.get("authenticated", connected)))
    health = str(broker.get("broker_health", broker.get("api_health", "")) or "").strip().upper()

    checks: dict[str, dict[str, Any]] = {}
    if selected == "COINBASE" and mode == "live" and connected and authenticated:
        checks["broker_authentication_state"] = {
            "status": "PASS",
            "reason": "coinbase_read_only_authentication_verified",
            "evidence": {"selected_broker": selected, "broker_mode": mode, "read_only": True},
        }
        checks["broker_health"] = {
            "status": "PASS" if health in {"GREEN", "OK", "HEALTHY", "PASS"} else "WARNING",
            "reason": "coinbase_read_only_health_verified" if health in {"GREEN", "OK", "HEALTHY", "PASS"} else "coinbase_read_only_health_warning",
            "evidence": {"selected_broker": selected, "broker_mode": mode, "broker_health": health or "UNKNOWN", "read_only": True},
        }
    return {"checks": checks, "broker_summary": dict(broker), "execution_allowed": False, "advisory_only": True}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "BrokerStartupSelection",
    "CANONICAL_STARTUP_SEQUENCE",
    "SUPPORTED_STARTUP_BROKERS",
    "broker_summary_from_artifacts",
    "build_startup_broker_selection",
    "cancelled_startup_selection",
    "live_readiness_broker_evidence",
    "normalize_broker",
    "normalize_broker_mode",
    "persist_broker_selection",
    "startup_broker_from_choice",
    "startup_broker_mode_from_choice",
]
