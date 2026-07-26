from __future__ import annotations

import math
from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState


class AccountStateBuilder:
    """
    Build account/PnL fields for DashboardState.

    PURPOSE
    -------
    Normalize accounting and PnL outputs into dashboard-safe state.

    RULES
    -----
    - builder must not calculate official accounting truth
    - builder must not override broker/accounting authority
    - builder must not execute trades
    """

    def build(
        self,
        *,
        account_payload: Dict[str, Any],
        state: DashboardState,
    ) -> DashboardState:
        numeric_fields = {
            "cash_balance": _safe_number(account_payload.get("cash_balance")),
            "total_equity": _safe_number(account_payload.get("total_equity")),
            "realized_pnl": _safe_number(account_payload.get("realized_pnl")),
            "unrealized_pnl": _safe_number(account_payload.get("unrealized_pnl")),
        }

        state.cash_balance = _calculation_value(numeric_fields["cash_balance"])
        state.total_equity = _calculation_value(numeric_fields["total_equity"])
        state.realized_pnl = _calculation_value(numeric_fields["realized_pnl"])
        state.unrealized_pnl = _calculation_value(numeric_fields["unrealized_pnl"])

        state.total_open_positions = _safe_int(account_payload.get("total_open_positions"))

        state.open_positions_by_asset = dict(
            account_payload.get("open_positions_by_asset", {})
        )
        state.last_scan_results["_account_field_values"] = numeric_fields
        state.last_scan_results["_account_field_availability"] = {
            field: "AVAILABLE" if value is not None else _availability_state(account_payload, field)
            for field, value in numeric_fields.items()
        }

        return state


def _safe_number(value: Any) -> float | None:
    if value in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE", "NOT_TESTED", "N/A"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _calculation_value(value: float | None) -> float:
    return value if value is not None else 0.0


def _safe_int(value: Any) -> int:
    number = _safe_number(value)
    return int(number) if number is not None else 0


def _availability_state(payload: Dict[str, Any], field: str) -> str:
    explicit = payload.get(f"{field}_availability") or payload.get("account_availability")
    if explicit:
        return str(explicit).strip().upper()
    if field in payload:
        return "UNAVAILABLE"
    return "MISSING"
