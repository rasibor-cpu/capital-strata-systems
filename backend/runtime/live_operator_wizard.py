from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from backend.runtime.broker_startup_selection import (
    normalize_broker,
    normalize_broker_mode,
    startup_broker_from_choice,
    startup_broker_mode_from_choice,
)


LIVE_OPERATOR_WIZARD_SEQUENCE = (
    "authentication",
    "global_mode_selection",
    "global_live_confirmation",
    "broker_selection",
    "broker_specific_mode_selection",
    "broker_live_read_only_confirmation",
    "broker_execution_arming",
    "engine_mode_selection",
    "cycle_mode_selection",
    "startup_summary_confirmation",
    "start_runtime_cycle",
)

INVALID_CONFIRMATION_TEMPLATE = (
    "INVALID CONFIRMATION\n"
    "Expected: {expected}\n"
    "Received: {received}\n"
    "Please try again."
)


@dataclass(frozen=True)
class StartupWizardState:
    step: str = "authentication"
    authenticated: bool = False
    global_mode: str = "paper"
    selected_broker: str = ""
    broker_mode: str = ""
    broker_execution_armed: bool = False
    engine_mode: str = ""
    cycle_mode: str = ""
    cycle_interval_seconds: int = 0
    execution_scope: str = "PAPER_OR_NOT_SELECTED"
    can_live_execute: bool = False
    restart_requested: bool = False
    exit_requested: bool = False
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["broker_execution_status"] = "ARMED" if self.broker_execution_armed else "DISABLED"
        payload["execution_allowed"] = False
        payload["live_order_permission"] = False
        payload["advisory_only"] = True
        return payload


@dataclass(frozen=True)
class WizardStepResult:
    state: StartupWizardState
    advanced: bool
    message: str = ""
    error: str = ""


def mark_authenticated(state: StartupWizardState) -> WizardStepResult:
    return WizardStepResult(
        replace(state, authenticated=True, step="global_mode_selection", last_error=""),
        True,
        "AUTHENTICATION ACCEPTED",
    )


def choose_global_mode(state: StartupWizardState, choice: Any, confirmation: Any = "") -> WizardStepResult:
    normalized = str(choice or "").strip()
    if normalized not in {"1", "2"}:
        return _invalid_choice(state, "1 or 2", normalized)
    if normalized == "1":
        return WizardStepResult(replace(state, global_mode="paper", step="broker_selection", last_error=""), True)
    confirmation_result = require_exact_confirmation("LIVE", confirmation)
    if not confirmation_result["accepted"]:
        return WizardStepResult(replace(state, step="global_live_confirmation", last_error=confirmation_result["message"]), False, error=confirmation_result["message"])
    return WizardStepResult(replace(state, global_mode="live", step="broker_selection", last_error=""), True)


def choose_broker(state: StartupWizardState, choice: Any, *, ibkr_supported: bool = False) -> WizardStepResult:
    normalized = str(choice or "").strip()
    if normalized not in {"1", "2", "3", "4"}:
        return _invalid_choice(state, "1, 2, 3, or 4", normalized)
    if normalized == "4" and not ibkr_supported:
        return WizardStepResult(
            replace(state, step="broker_selection", last_error="IBKR is not enabled in this runtime."),
            False,
            error="IBKR is not enabled in this runtime.",
        )
    broker = startup_broker_from_choice(normalized, ibkr_supported=ibkr_supported)
    next_step = "broker_execution_arming" if broker == "NONE" else "broker_specific_mode_selection"
    mode = "paper" if broker == "NONE" else ""
    return WizardStepResult(replace(state, selected_broker=broker, broker_mode=mode, step=next_step, last_error=""), True)


def choose_broker_mode(
    state: StartupWizardState,
    choice: Any,
    *,
    confirmation: Any = "",
    env: Mapping[str, Any] | None = None,
) -> WizardStepResult:
    broker = normalize_broker(state.selected_broker)
    if broker == "NONE":
        return WizardStepResult(replace(state, broker_mode="paper", step="broker_execution_arming", last_error=""), True)
    normalized = str(choice or "").strip()
    if normalized not in {"1", "2"}:
        return _invalid_choice(state, "1 or 2", normalized)
    mode = startup_broker_mode_from_choice(normalized, selected_broker=broker, global_mode=state.global_mode)
    conflict = paper_live_environment_conflict(broker, mode, env=env)
    if conflict["blocking"]:
        return WizardStepResult(replace(state, step="broker_specific_mode_selection", last_error=conflict["message"]), False, error=conflict["message"])
    if mode == "live":
        confirmation_result = require_exact_confirmation("LIVE", confirmation)
        if not confirmation_result["accepted"]:
            return WizardStepResult(replace(state, step="broker_live_read_only_confirmation", last_error=confirmation_result["message"]), False, error=confirmation_result["message"])
    scope = "LIVE READ-ONLY VALIDATION" if mode == "live" else "READ_ONLY_PAPER"
    return WizardStepResult(replace(state, broker_mode=mode, execution_scope=scope, step="broker_execution_arming", last_error=""), True)


def choose_broker_execution_arming(
    state: StartupWizardState,
    choice: Any,
    *,
    arm_confirmation: Any = "",
    role_profile: Mapping[str, Any] | None = None,
) -> WizardStepResult:
    normalized = str(choice or "").strip()
    if normalized not in {"1", "2"}:
        return _invalid_choice(state, "1 or 2", normalized)
    broker = normalize_broker(state.selected_broker)
    mode = normalize_broker_mode(state.broker_mode, selected_broker=broker)
    if normalized == "1":
        return WizardStepResult(replace(state, broker_execution_armed=False, can_live_execute=False, step="engine_mode_selection", last_error=""), True)
    if broker == "NONE":
        message = "Broker execution cannot be armed because no broker is selected."
        return WizardStepResult(replace(state, broker_execution_armed=False, can_live_execute=False, step="broker_selection", last_error=message), False, error=message)
    profile = role_profile if isinstance(role_profile, Mapping) else {}
    if not bool(profile.get("can_arm_broker", False)):
        message = "Broker execution arming denied by RBAC."
        return WizardStepResult(replace(state, broker_execution_armed=False, can_live_execute=False, step="engine_mode_selection", last_error=message), True, error=message)
    if mode == "live":
        confirmation_result = require_exact_confirmation("ARM LIVE", arm_confirmation)
        if not confirmation_result["accepted"]:
            return WizardStepResult(
                replace(state, broker_execution_armed=False, can_live_execute=False, step="engine_mode_selection", last_error=confirmation_result["message"]),
                True,
                error=confirmation_result["message"],
            )
    return WizardStepResult(replace(state, broker_execution_armed=True, can_live_execute=mode == "live", step="engine_mode_selection", last_error=""), True)


def set_engine_mode(state: StartupWizardState, mode: Any) -> WizardStepResult:
    engine = str(mode or "").strip().upper()
    if not engine:
        return _invalid_choice(state, "engine mode", mode)
    return WizardStepResult(replace(state, engine_mode=engine, step="cycle_mode_selection", last_error=""), True)


def set_cycle_mode(state: StartupWizardState, mode: Any, interval_seconds: Any = 0) -> WizardStepResult:
    cycle = str(mode or "").strip().lower()
    if cycle not in {"manual", "continuous"}:
        return _invalid_choice(state, "manual or continuous", mode)
    interval = 0
    if cycle == "continuous":
        try:
            interval = max(5, int(interval_seconds or 60))
        except (TypeError, ValueError):
            interval = 60
    return WizardStepResult(replace(state, cycle_mode=cycle, cycle_interval_seconds=interval, step="startup_summary_confirmation", last_error=""), True)


def startup_summary_confirmation(state: StartupWizardState, value: Any) -> WizardStepResult:
    normalized = str(value or "").strip().upper()
    if normalized == "Y":
        return WizardStepResult(replace(state, step="start_runtime_cycle", restart_requested=False, exit_requested=False, last_error=""), True)
    if normalized == "N":
        return WizardStepResult(replace(state, step="broker_selection", restart_requested=True, broker_execution_armed=False, can_live_execute=False, last_error="startup_restart_requested"), False, message="STARTUP RESTART REQUESTED")
    return _invalid_choice(state, "Y or N", value)


def require_exact_confirmation(expected: str, received: Any) -> dict[str, Any]:
    text = str(received or "").strip()
    accepted = text == expected
    return {
        "accepted": accepted,
        "expected": expected,
        "received": text,
        "message": "" if accepted else INVALID_CONFIRMATION_TEMPLATE.format(expected=expected, received=text),
    }


def paper_live_environment_conflict(
    selected_broker: Any,
    broker_mode: Any,
    *,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    broker = normalize_broker(selected_broker)
    mode = normalize_broker_mode(broker_mode, selected_broker=broker)
    source = env if isinstance(env, Mapping) else {}
    live_keys: list[str] = []
    if mode != "paper":
        return {"blocking": False, "message": "", "live_environment_keys": []}
    if broker == "OANDA":
        if str(source.get("OANDA_ENV", "")).strip().lower() == "live":
            live_keys.append("OANDA_ENV")
        for key in ("OANDA_LIVE_TOKEN", "OANDA_LIVE_ACCOUNT_ID"):
            if str(source.get(key, "")).strip():
                live_keys.append(key)
    if broker == "COINBASE":
        if str(source.get("COINBASE_ENABLE_LIVE_ORDERS", "")).strip().lower() in {"1", "true", "yes", "on", "enabled"}:
            live_keys.append("COINBASE_ENABLE_LIVE_ORDERS")
    message = (
        "Paper mode cannot use LIVE broker credentials/environment.\n"
        "Choose:\n"
        "1. Return to broker setup\n"
        "2. Exit"
        if live_keys
        else ""
    )
    return {"blocking": bool(live_keys), "message": message, "live_environment_keys": live_keys}


def broker_validation_display(
    *,
    selected_broker: Any,
    broker_mode: Any,
    readiness: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    broker = normalize_broker(selected_broker)
    mode = normalize_broker_mode(broker_mode, selected_broker=broker)
    data = readiness if isinstance(readiness, Mapping) else {}
    diagnostics = data.get("credential_diagnostics") if isinstance(data.get("credential_diagnostics"), Mapping) else {}
    credential_status = str(diagnostics.get("credential_status", "") or "").upper()
    if not credential_status and broker == "OANDA":
        credential_status = "PASS" if _oanda_credentials_present(env) else "MISSING"
    elif credential_status == "PRESENT":
        credential_status = "PASS"
    elif not credential_status:
        credential_status = "NOT_TESTED" if broker == "NONE" else "MISSING"
    auth_status = _pass_fail_not_tested(data.get("broker_authenticated"), data.get("auth_reason"))
    connection_status = _pass_fail_not_tested(data.get("broker_connected"), data.get("auth_reason"))
    checks = data.get("read_checks") if isinstance(data.get("read_checks"), Mapping) else {}
    product_price_status = _read_check_status(checks.get("products_or_prices"))
    balance_position_status = _combined_read_check_status(checks.get("balances"), checks.get("positions"))
    order_status = "DISABLED" if not _truthy(data.get("broker_execution_armed", False)) else "BLOCKED"
    return {
        "credential_status": credential_status,
        "auth_status": auth_status,
        "connection_status": connection_status,
        "product_price_status": product_price_status,
        "balance_position_status": balance_position_status,
        "order_submission_status": order_status,
        "orders_sent_count": int(data.get("orders_sent_count", 0) or 0),
        "orders_blocked_count": int(data.get("orders_blocked_count", 0) or 0),
        "selected_broker": broker,
        "broker_mode": mode,
        "advisory_only": True,
        "execution_allowed": False,
    }


def build_startup_summary(
    state: StartupWizardState | Mapping[str, Any],
    *,
    broker_status: Mapping[str, Any] | None = None,
    pilot_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = state.as_dict() if isinstance(state, StartupWizardState) else dict(state)
    broker = broker_status if isinstance(broker_status, Mapping) else {}
    pilot = pilot_status if isinstance(pilot_status, Mapping) else {}
    return {
        "global_mode": str(source.get("global_mode", "paper")),
        "selected_broker": str(source.get("selected_broker", "NONE") or "NONE"),
        "broker_mode": str(source.get("broker_mode", "paper") or "paper"),
        "broker_connection_status": str(broker.get("connection_status", broker.get("broker_health", "NOT_TESTED"))),
        "broker_auth_status": str(broker.get("auth_status", "NOT_TESTED")),
        "broker_execution_status": "ARMED" if bool(source.get("broker_execution_armed", False)) else "DISABLED",
        "live_micro_pilot_state": str(pilot.get("pilot_state", "DISARMED")),
        "canonical_live_capital_authority": "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR",
        "canonical_pilot_cap": f"{pilot.get('currency', 'CAD')} {pilot.get('canonical_live_pilot_limit_cad', pilot.get('max_live_test_capital', '20.00'))}",
        "engine_mode": str(source.get("engine_mode", "")),
        "cycle_mode": str(source.get("cycle_mode", "")),
        "can_live_execute": bool(source.get("can_live_execute", False)),
        "execution_scope": str(source.get("execution_scope", "PAPER_OR_NOT_SELECTED")),
        "execution_allowed": False,
        "advisory_only": True,
    }


def _invalid_choice(state: StartupWizardState, expected: Any, received: Any) -> WizardStepResult:
    message = f"INVALID INPUT\nExpected: {expected}\nReceived: {received}\nPlease try again."
    return WizardStepResult(replace(state, last_error=message), False, error=message)


def _oanda_credentials_present(env: Mapping[str, Any] | None) -> bool:
    source = env if isinstance(env, Mapping) else {}
    token = str(source.get("OANDA_API_KEY") or source.get("OANDA_ACCESS_TOKEN") or source.get("OANDA_TOKEN") or "").strip()
    account = str(source.get("OANDA_ACCOUNT_ID") or source.get("OANDA_PRACTICE_ACCOUNT_ID") or "").strip()
    return bool(token and account)


def _pass_fail_not_tested(value: Any, reason: Any = "") -> str:
    if _truthy(value):
        return "PASS"
    reason_text = str(reason or "").lower()
    if "failed" in reason_text or "auth_failed" in reason_text:
        return "FAIL"
    return "NOT_TESTED"


def _read_check_status(value: Any) -> str:
    text = str(value or "NOT_TESTED").strip().upper()
    if text == "OK":
        return "PASS"
    if text in {"FAILED", "ERROR"}:
        return "FAIL"
    return "NOT_TESTED"


def _combined_read_check_status(first: Any, second: Any) -> str:
    statuses = {_read_check_status(first), _read_check_status(second)}
    if "PASS" in statuses:
        return "PASS"
    if "FAIL" in statuses:
        return "FAIL"
    return "NOT_TESTED"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green"}


__all__ = [
    "INVALID_CONFIRMATION_TEMPLATE",
    "LIVE_OPERATOR_WIZARD_SEQUENCE",
    "StartupWizardState",
    "WizardStepResult",
    "broker_validation_display",
    "build_startup_summary",
    "choose_broker",
    "choose_broker_execution_arming",
    "choose_broker_mode",
    "choose_global_mode",
    "mark_authenticated",
    "paper_live_environment_conflict",
    "require_exact_confirmation",
    "set_cycle_mode",
    "set_engine_mode",
    "startup_summary_confirmation",
]
