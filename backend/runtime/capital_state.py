from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class CapitalState(str, Enum):
    CAPITAL_READY = "CAPITAL_READY"
    SIMULATED_CAPITAL_READY = "SIMULATED_CAPITAL_READY"
    REAL_DRAWDOWN_ACTIVE = "REAL_DRAWDOWN_ACTIVE"

    CAPITAL_UNAVAILABLE = "CAPITAL_UNAVAILABLE"
    BROKER_BALANCE_UNAVAILABLE = "BROKER_BALANCE_UNAVAILABLE"
    BROKER_CREDENTIALS_MISSING = "BROKER_CREDENTIALS_MISSING"
    BROKER_CREDENTIALS_INVALID = "BROKER_CREDENTIALS_INVALID"
    ACCOUNT_DATA_NOT_READY = "ACCOUNT_DATA_NOT_READY"
    ZERO_FUNDED_ACCOUNT = "ZERO_FUNDED_ACCOUNT"
    UNKNOWN = "UNKNOWN"


CANONICAL_CAPITAL_STATES = tuple(state.value for state in CapitalState)

TRADEABLE_CAPITAL_STATES = {
    CapitalState.CAPITAL_READY.value,
    CapitalState.SIMULATED_CAPITAL_READY.value,
}

NON_TRADEABLE_CAPITAL_STATES = {
    CapitalState.CAPITAL_UNAVAILABLE.value,
    CapitalState.BROKER_BALANCE_UNAVAILABLE.value,
    CapitalState.BROKER_CREDENTIALS_MISSING.value,
    CapitalState.BROKER_CREDENTIALS_INVALID.value,
    CapitalState.ACCOUNT_DATA_NOT_READY.value,
    CapitalState.ZERO_FUNDED_ACCOUNT.value,
    CapitalState.REAL_DRAWDOWN_ACTIVE.value,
    CapitalState.UNKNOWN.value,
}

MISSING_CREDENTIAL_FAILURE_REASONS = {
    "MISSING_CREDENTIALS",
    "KEY_MISSING",
    "SECRET_MISSING",
    "ACCOUNT_ID_MISSING",
}

INVALID_CREDENTIAL_FAILURE_REASONS = {
    "PRIVATE_KEY_INVALID",
    "PEM_INVALID",
    "JWT_GENERATION_FAILED",
    "JWT_SIGNATURE_INVALID",
    "TOKEN_INVALID",
    "AUTH_FAILED",
    "UNAUTHORIZED",
    "FORBIDDEN",
}


def normalize_capital_state(value: Any) -> str:
    if value is None:
        return CapitalState.UNKNOWN.value
    normalized = str(value).strip().upper()
    if not normalized:
        return CapitalState.UNKNOWN.value
    return normalized


def is_tradeable_capital_state(value: Any) -> bool:
    return normalize_capital_state(value) in TRADEABLE_CAPITAL_STATES


def is_non_tradeable_capital_state(value: Any) -> bool:
    return not is_tradeable_capital_state(value)


def drawdown_is_computable(value: Any) -> bool:
    return normalize_capital_state(value) in {
        CapitalState.CAPITAL_READY.value,
        CapitalState.SIMULATED_CAPITAL_READY.value,
        CapitalState.REAL_DRAWDOWN_ACTIVE.value,
    }


def drawdown_status_for_capital_state(value: Any) -> str:
    return "COMPUTED" if drawdown_is_computable(value) else "NOT_COMPUTABLE"


def trade_gate_reason_for_capital_state(value: Any) -> str:
    if is_tradeable_capital_state(value):
        return "CAPITAL_READY"
    return "CAPITAL_STATE_UNAVAILABLE"


def capital_state_from_credential_diagnostics(value: Mapping[str, Any] | None) -> str:
    diagnostics = value if isinstance(value, Mapping) else {}
    failure_reason = str(
        diagnostics.get("canonical_failure_reason", diagnostics.get("failure_reason", "MISSING_CREDENTIALS"))
    ).upper()
    credentials_present = bool(diagnostics.get("credentials_present", False))

    if not credentials_present or failure_reason in MISSING_CREDENTIAL_FAILURE_REASONS:
        return CapitalState.BROKER_CREDENTIALS_MISSING.value
    if failure_reason in INVALID_CREDENTIAL_FAILURE_REASONS:
        return CapitalState.BROKER_CREDENTIALS_INVALID.value
    if failure_reason == "NONE" and credentials_present:
        return CapitalState.CAPITAL_READY.value
    return CapitalState.CAPITAL_UNAVAILABLE.value


def classify_capital_state(
    *,
    selected_broker: Any = None,
    broker_mode: Any = None,
    balance: Any = None,
    equity: Any = None,
    balance_status: Any = "NOT_AVAILABLE",
    drawdown_reason: Any = "",
    credential_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    broker = str(selected_broker or "NONE").upper()
    mode = str(broker_mode or "paper").lower()
    status = str(balance_status or "NOT_AVAILABLE").upper()
    reason = str(drawdown_reason or "").strip()

    if broker == "NONE" or mode != "live":
        return _capital_payload(CapitalState.SIMULATED_CAPITAL_READY.value, "ALLOW", "CAPITAL_READY", "")

    numeric_balance = _float_or_none(balance)
    numeric_equity = _float_or_none(equity)

    if status == "AVAILABLE" and numeric_balance is not None and numeric_equity is not None:
        if numeric_balance <= 0.0 and numeric_equity <= 0.0:
            return _capital_payload(
                CapitalState.ZERO_FUNDED_ACCOUNT.value,
                "BLOCK",
                "CAPITAL_STATE_UNAVAILABLE",
                "Zero funded account",
            )
        return _capital_payload(CapitalState.CAPITAL_READY.value, "ALLOW", "CAPITAL_READY", "")

    diagnostics_state = capital_state_from_credential_diagnostics(credential_diagnostics)
    if diagnostics_state == CapitalState.BROKER_CREDENTIALS_MISSING.value:
        return _capital_payload(
            diagnostics_state,
            "BLOCK",
            "CAPITAL_STATE_UNAVAILABLE",
            "Broker credentials missing",
        )
    if diagnostics_state == CapitalState.BROKER_CREDENTIALS_INVALID.value:
        return _capital_payload(
            diagnostics_state,
            "BLOCK",
            "CAPITAL_STATE_UNAVAILABLE",
            "Broker credentials invalid",
        )

    if status != "AVAILABLE" or numeric_balance is None or numeric_equity is None:
        return _capital_payload(
            CapitalState.BROKER_BALANCE_UNAVAILABLE.value,
            "BLOCK",
            "CAPITAL_STATE_UNAVAILABLE",
            reason or "Broker balance unavailable",
        )

    return _capital_payload(
        CapitalState.CAPITAL_UNAVAILABLE.value,
        "BLOCK",
        "CAPITAL_STATE_UNAVAILABLE",
        reason or "Capital state unavailable",
    )


def evaluate_drawdown_state(
    *,
    current_equity: float | None,
    peak_equity: float | None,
    max_drawdown_pct: float,
    capital_state: Any = CapitalState.CAPITAL_READY.value,
    drawdown_reason: str = "",
) -> dict[str, Any]:
    state = normalize_capital_state(capital_state)
    timestamp = datetime.now(timezone.utc).isoformat()

    if state not in CANONICAL_CAPITAL_STATES:
        state = CapitalState.CAPITAL_UNAVAILABLE.value
        drawdown_reason = drawdown_reason or "Unknown capital state"

    if not drawdown_is_computable(state):
        return {
            "decision": "BLOCK",
            "reason": "Capital state unavailable (fail-closed).",
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": None,
            "max_drawdown_pct": float(max_drawdown_pct),
            "allowed": False,
            "blocked": True,
            "timestamp_utc": timestamp,
            "capital_state": state,
            "drawdown_status": "NOT_COMPUTABLE",
            "drawdown_reason": drawdown_reason or _default_unavailable_reason(state),
            "trade_gate_decision": "BLOCK",
            "trade_gate_reason": "CAPITAL_STATE_UNAVAILABLE",
            "live_execution_authority": "NO",
        }

    current = _float_or_none(current_equity)
    peak = _float_or_none(peak_equity)

    if current is None or peak is None:
        return {
            "decision": "BLOCK",
            "reason": "Account data not ready (fail-closed).",
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": None,
            "max_drawdown_pct": float(max_drawdown_pct),
            "allowed": False,
            "blocked": True,
            "timestamp_utc": timestamp,
            "capital_state": CapitalState.ACCOUNT_DATA_NOT_READY.value,
            "drawdown_status": "NOT_COMPUTABLE",
            "drawdown_reason": drawdown_reason or "Account data not ready",
            "trade_gate_decision": "BLOCK",
            "trade_gate_reason": "CAPITAL_STATE_UNAVAILABLE",
            "live_execution_authority": "NO",
        }

    if peak <= 0:
        return {
            "decision": "BLOCK",
            "reason": "Invalid peak equity value.",
            "current_equity": current,
            "peak_equity": peak,
            "drawdown_pct": None,
            "max_drawdown_pct": float(max_drawdown_pct),
            "allowed": False,
            "blocked": True,
            "timestamp_utc": timestamp,
            "capital_state": CapitalState.ACCOUNT_DATA_NOT_READY.value,
            "drawdown_status": "NOT_COMPUTABLE",
            "drawdown_reason": drawdown_reason or "Peak equity unavailable",
            "trade_gate_decision": "BLOCK",
            "trade_gate_reason": "CAPITAL_STATE_UNAVAILABLE",
            "live_execution_authority": "NO",
        }

    drawdown_pct = max(0.0, ((peak - current) / peak) * 100.0)
    blocked = drawdown_pct >= float(max_drawdown_pct)

    return {
        "decision": "BLOCK" if blocked else "ALLOW",
        "reason": "Max equity drawdown exceeded." if blocked else "Drawdown within limits.",
        "current_equity": current,
        "peak_equity": peak,
        "drawdown_pct": round(drawdown_pct, 2),
        "max_drawdown_pct": float(max_drawdown_pct),
        "allowed": not blocked,
        "blocked": blocked,
        "timestamp_utc": timestamp,
        "capital_state": CapitalState.REAL_DRAWDOWN_ACTIVE.value if blocked else state,
        "drawdown_status": "COMPUTED",
        "drawdown_reason": drawdown_reason or ("Drawdown limit reached" if blocked else ""),
        "trade_gate_decision": "BLOCK" if blocked else "ALLOW",
        "trade_gate_reason": "DRAWDOWN_LIMIT_REACHED" if blocked else "CAPITAL_READY",
        "live_execution_authority": "NO" if blocked else "NOT_EVALUATED",
    }


def canonical_drawdown_display(
    *,
    current_equity: float | None,
    peak_equity: float | None,
    max_drawdown_pct: float,
    capital_state: Any,
    drawdown_reason: str = "",
) -> dict[str, Any]:
    evaluation = evaluate_drawdown_state(
        current_equity=current_equity,
        peak_equity=peak_equity,
        max_drawdown_pct=max_drawdown_pct,
        capital_state=capital_state,
        drawdown_reason=drawdown_reason,
    )
    drawdown_status = str(evaluation.get("drawdown_status", "NOT_COMPUTABLE")).upper()
    drawdown_pct = evaluation.get("drawdown_pct")
    if drawdown_status == "NOT_COMPUTABLE":
        drawdown_display = "NOT COMPUTABLE"
    else:
        drawdown_display = f"{float(drawdown_pct or 0.0):.4f}%"

    return {
        "drawdown_display": drawdown_display,
        "drawdown_status": drawdown_status,
        "drawdown_reason": str(evaluation.get("drawdown_reason", "") or ""),
        "capital_state": str(evaluation.get("capital_state", normalize_capital_state(capital_state))),
        "evaluation": evaluation,
    }


def _capital_payload(capital_state: str, trade_gate_decision: str, trade_gate_reason: str, drawdown_reason: str) -> dict[str, Any]:
    return {
        "capital_state": capital_state,
        "drawdown_status": "NOT_COMPUTABLE" if trade_gate_decision == "BLOCK" else "COMPUTED",
        "drawdown_reason": drawdown_reason,
        "trade_gate_decision": trade_gate_decision,
        "trade_gate_reason": trade_gate_reason,
        "live_execution_authority": "NO" if trade_gate_decision == "BLOCK" else "NOT_EVALUATED",
    }


def _default_unavailable_reason(state: str) -> str:
    return {
        CapitalState.BROKER_BALANCE_UNAVAILABLE.value: "Broker balance unavailable",
        CapitalState.BROKER_CREDENTIALS_MISSING.value: "Broker credentials missing",
        CapitalState.BROKER_CREDENTIALS_INVALID.value: "Broker credentials invalid",
        CapitalState.ACCOUNT_DATA_NOT_READY.value: "Account data not ready",
        CapitalState.ZERO_FUNDED_ACCOUNT.value: "Zero funded account",
        CapitalState.CAPITAL_UNAVAILABLE.value: "Capital state unavailable",
    }.get(state, "Capital state unavailable")


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "CANONICAL_CAPITAL_STATES",
    "CapitalState",
    "TRADEABLE_CAPITAL_STATES",
    "NON_TRADEABLE_CAPITAL_STATES",
    "normalize_capital_state",
    "is_tradeable_capital_state",
    "is_non_tradeable_capital_state",
    "drawdown_is_computable",
    "drawdown_status_for_capital_state",
    "trade_gate_reason_for_capital_state",
    "capital_state_from_credential_diagnostics",
    "classify_capital_state",
    "evaluate_drawdown_state",
    "canonical_drawdown_display",
]
