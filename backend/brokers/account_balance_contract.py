"""Canonical provider-neutral broker account balance contract."""

from __future__ import annotations

import os
from typing import Any, Mapping

BALANCE_FIELDS = (
    "total_account_value",
    "total_equity",
    "cash",
    "available_to_trade",
    "buying_power",
    "market_value",
    "margin_used",
    "margin_available",
    "held_reserved",
    "pending",
    "unrealized_pnl",
    "realized_pnl",
    "total_pnl",
)


def build_broker_balance_summary(
    payload: Mapping[str, Any] | None,
    *,
    broker: str | None = None,
    mode: str | None = None,
    base_currency: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    source = dict(payload or {})
    broker_name = str(broker or source.get("broker") or "NONE").strip().upper()
    account_mode = str(mode or source.get("account_mode") or source.get("environment") or "ADVISORY").strip().upper()
    currency = str(base_currency or source.get("base_currency") or source.get("currency") or "UNAVAILABLE").upper()
    timestamp = str(
        as_of
        or source.get("as_of")
        or source.get("timestamp")
        or source.get("generated_at")
        or "UNAVAILABLE"
    )
    paper = broker_name in {"NONE", "PAPER", "CSS_PAPER", "SIMULATED"} or account_mode == "PAPER"
    values = _provider_values(source, broker_name)
    configuration_source = None
    simulation_ceiling = _number(source.get("simulation_collateral_ceiling"))
    if paper:
        capital = _first_number(
            source.get("paper_capital"),
            values.get("total_account_value"),
            values.get("total_equity"),
            values.get("cash"),
        )
        ratio, configuration_source = _paper_collateral_policy(source)
        values["total_account_value"] = capital
        values["total_equity"] = _first_number(values.get("total_equity"), capital)
        values["cash"] = _first_number(values.get("cash"), capital)
        values["available_to_trade"] = _first_number(values.get("available_to_trade"), capital)
        values["buying_power"] = _first_number(values.get("buying_power"), capital)
        values["margin_available"] = (
            round(capital * ratio, 8)
            if capital is not None and ratio is not None
            else None
        )
    total_pnl = _sum_if_available(values.get("realized_pnl"), values.get("unrealized_pnl"))
    values["total_pnl"] = _first_number(values.get("total_pnl"), total_pnl)
    source_name = "CSS_PAPER_CAPITAL" if paper else (broker_name or "UNAVAILABLE")
    provenance = "SIMULATED_PAPER_ACCOUNT" if paper else "BROKER_REPORTED"
    fields = {
        name: _value_contract(
            values.get(name),
            currency=currency,
            source=source_name,
            provenance=provenance,
            freshness=source.get("freshness"),
            as_of=timestamp,
        )
        for name in BALANCE_FIELDS
    }
    return {
        "schema_version": "css.broker_balance_summary.v1",
        "account_summary": fields,
        "asset_breakdown": _asset_rows(source, broker_name, currency, timestamp),
        "position_value": _position_values(source, currency, timestamp),
        "collateral_margin": {
            "required_collateral": _value_contract(_first_number(source.get("required_collateral"), source.get("margin_requirement")), currency=currency, source=source_name, provenance=provenance, freshness=source.get("freshness"), as_of=timestamp),
            "available_collateral": fields["margin_available"],
            "used_margin": fields["margin_used"],
            "free_margin": fields["margin_available"],
            "utilization_pct": _value_contract(_utilization(values.get("margin_used"), values.get("margin_available")), currency="PERCENT", source=source_name, provenance=provenance, freshness=source.get("freshness"), as_of=timestamp),
            "closeout_percentage": _value_contract(_first_number(source.get("closeout_percentage"), source.get("marginCloseoutPercent")), currency="PERCENT", source=source_name, provenance=provenance, freshness=source.get("freshness"), as_of=timestamp),
            "margin_state": str(source.get("margin_state") or ("SIMULATED" if paper else "UNAVAILABLE")),
            "source": source_name,
            "provenance": provenance,
            "simulation_collateral_ceiling": _value_contract(simulation_ceiling, currency=currency, source=str(source.get("simulation_collateral_ceiling_source") or "UNAVAILABLE"), provenance="SEPARATE_SIMULATION_LIMIT" if simulation_ceiling is not None else "UNAVAILABLE", freshness=source.get("freshness"), as_of=timestamp),
        },
        "account_context": {
            "broker": broker_name,
            "account_alias": source.get("account_alias") or source.get("alias") or "UNAVAILABLE",
            "account_type": source.get("account_type") or source.get("type") or "UNAVAILABLE",
            "base_currency": currency,
            "environment": account_mode,
            "data_timestamp": timestamp,
            "data_source": source_name,
            "authority_label": "SIMULATED" if paper else "LIVE_READ_ONLY",
            "execution_status": "BLOCKED",
            "configuration_source": configuration_source,
        },
        "paper_account": paper,
        "advisory_only": True,
        "execution_allowed": False,
    }


def _provider_values(source: Mapping[str, Any], broker: str) -> dict[str, float | None]:
    aliases = {
        "total_account_value": ("total_account_value", "account_value", "portfolio_balance", "nav", "total_equity", "equity"),
        "total_equity": ("total_equity", "equity", "nav"),
        "cash": ("cash", "cash_balance", "balance"),
        "available_to_trade": ("available_to_trade", "available", "available_balance", "maintenance_excess"),
        "buying_power": ("buying_power",),
        "market_value": ("market_value", "total_market_value", "invested_value"),
        "margin_used": ("margin_used", "used_margin", "margin_requirement"),
        "margin_available": ("margin_available", "available_margin", "free_margin", "maintenance_excess"),
        "held_reserved": ("held_reserved", "held", "locked", "reserved"),
        "pending": ("pending", "pending_balance"),
        "unrealized_pnl": ("unrealized_pnl", "unrealizedPL"),
        "realized_pnl": ("realized_pnl", "realizedPL"),
        "total_pnl": ("total_pnl",),
    }
    values = {
        field: _first_number(*(source.get(alias) for alias in names))
        for field, names in aliases.items()
    }
    if broker == "OANDA":
        values["total_account_value"] = _first_number(source.get("NAV"), source.get("nav"), values["total_account_value"])
        values["cash"] = _first_number(source.get("balance"), values["cash"])
        values["margin_available"] = _first_number(source.get("marginAvailable"), values["margin_available"])
        values["margin_used"] = _first_number(source.get("marginUsed"), values["margin_used"])
    return values


def _asset_rows(source: Mapping[str, Any], broker: str, currency: str, as_of: str) -> list[dict[str, Any]]:
    candidates = source.get("assets") or source.get("balances") or source.get("currencies") or []
    if not isinstance(candidates, list):
        return []
    rows = []
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        asset = str(raw.get("asset") or raw.get("currency") or raw.get("symbol") or "UNAVAILABLE").upper()
        rows.append(
            {
                "asset_currency": asset,
                "total": _first_number(raw.get("total"), raw.get("balance"), raw.get("quantity")),
                "available": _first_number(raw.get("available"), raw.get("cash")),
                "held_reserved": _first_number(raw.get("held"), raw.get("locked"), raw.get("reserved")),
                "pending": _number(raw.get("pending")),
                "market_value": _first_number(raw.get("market_value"), raw.get("fiat_equivalent")),
                "base_currency_equivalent": _first_number(raw.get("base_currency_equivalent"), raw.get("fiat_equivalent")),
                "currency": str(raw.get("base_currency") or currency).upper(),
                "source": broker,
                "freshness": raw.get("freshness") or source.get("freshness") or "UNAVAILABLE",
                "as_of": raw.get("as_of") or raw.get("timestamp") or as_of,
            }
        )
    return rows


def _position_values(source: Mapping[str, Any], currency: str, as_of: str) -> dict[str, Any]:
    by_class = source.get("position_value") if isinstance(source.get("position_value"), Mapping) else {}
    return {
        asset_class: _value_contract(_first_number(by_class.get(asset_class.lower()), source.get(f"{asset_class.lower()}_market_value")), currency=currency, source="ACCOUNT_POSITIONS", provenance="POSITION_AGGREGATION", freshness=source.get("freshness"), as_of=as_of)
        for asset_class in ("EQUITIES", "CRYPTO", "FX", "OPTIONS", "FUTURES", "TOTAL_INVESTED_VALUE")
    }


def _paper_collateral_policy(source: Mapping[str, Any]) -> tuple[float | None, str]:
    supplied = _number(source.get("paper_collateral_ratio"))
    if supplied is not None:
        return max(0.0, supplied), "account_payload.paper_collateral_ratio"
    raw = os.getenv("CSS_PAPER_COLLATERAL_RATIO", "1.0").strip()
    try:
        return max(0.0, float(raw)), "CSS_PAPER_COLLATERAL_RATIO(default=1.0)"
    except ValueError:
        return None, "CSS_PAPER_COLLATERAL_RATIO(invalid)"


def _value_contract(value: float | None, *, currency: str, source: str, provenance: str, freshness: Any, as_of: str) -> dict[str, Any]:
    return {
        "value": value,
        "currency": currency,
        "source": source,
        "provenance": provenance,
        "freshness": freshness or "UNAVAILABLE",
        "as_of": as_of,
        "availability_state": "AVAILABLE" if value is not None else "UNAVAILABLE",
    }


def _number(value: Any) -> float | None:
    if value in (None, "", "UNAVAILABLE", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number(value)
        if number is not None:
            return number
    return None


def _sum_if_available(left: Any, right: Any) -> float | None:
    a, b = _number(left), _number(right)
    return None if a is None and b is None else (a or 0.0) + (b or 0.0)


def _utilization(used: Any, available: Any) -> float | None:
    used_n, available_n = _number(used), _number(available)
    if used_n is None or available_n is None or used_n + available_n <= 0:
        return None
    return round(100.0 * used_n / (used_n + available_n), 4)


__all__ = ["BALANCE_FIELDS", "build_broker_balance_summary"]
