"""Canonical read-only broker portfolio contract for Mission Control.

Distinguishes ACCOUNT_ASSET_BALANCE, POSITION, and HOLDING. Never fabricates
unsupported P&L, margin, maturity, or market value. Observability only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    evaluate_canonical_broker_snapshot_freshness,
)
from backend.runtime.coinbase_spot_asset_balances import (
    SECTION_LABEL as COINBASE_BALANCE_LABEL,
    build_spot_asset_balances,
)


EXPOSURE_ACCOUNT_ASSET_BALANCE = "ACCOUNT_ASSET_BALANCE"
EXPOSURE_POSITION = "POSITION"
EXPOSURE_HOLDING = "HOLDING"
PROVENANCE_BROKER_REPORTED = "BROKER_REPORTED"
PROVENANCE_DERIVED = "DERIVED"
PROVENANCE_UNAVAILABLE = "UNAVAILABLE"
_AVAILABLE = "AVAILABLE"
_UNAVAILABLE = "UNAVAILABLE"
SOURCE_BINANCE_LIVE_READ_ONLY = "BINANCE_LIVE_READ_ONLY"
SOURCE_OANDA_LIVE_READ_ONLY = "OANDA_LIVE_READ_ONLY"
SOURCE_QUESTRADE_READ_ONLY = "QUESTRADE_READ_ONLY"
LIVE_READ_ONLY_MODES = frozenset({"LIVE_READ_ONLY", "LIVE READ-ONLY", "LIVE READ ONLY"})
QUESTRADE_UNAVAILABLE_STATUSES = frozenset(
    {
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_DISABLED",
        "QUESTRADE_PROVIDER_DISABLED",
        "CONFIGURATION_REQUIRED",
        "AUTHENTICATION_REQUIRED",
        "ACCOUNT_UNAVAILABLE",
        "DATA_DEPENDENCY_BLOCKED",
        "SECRET_LEASE_UNAVAILABLE",
        "OPTION_CHAIN_PROVIDER_REQUIRED",
    }
)
SAFETY = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}


def unavailable_metric(*, reason: str = "UNAVAILABLE") -> dict[str, Any]:
    return {
        "value": None,
        "availability": _UNAVAILABLE,
        "provenance": PROVENANCE_UNAVAILABLE,
        "origin": _UNAVAILABLE,
        "reason": reason,
    }


def reported_metric(value: Any, *, origin: str, reason: str = "ok") -> dict[str, Any]:
    return {
        "value": value,
        "availability": _AVAILABLE,
        "provenance": PROVENANCE_BROKER_REPORTED,
        "origin": origin,
        "reason": reason,
    }


def derived_metric(value: Any, *, origin: str, reason: str) -> dict[str, Any]:
    return {
        "value": value,
        "availability": _AVAILABLE,
        "provenance": PROVENANCE_DERIVED,
        "origin": origin,
        "reason": reason,
    }


def empty_canonical_portfolio(*, broker: str = _UNAVAILABLE, reason: str = "unavailable") -> dict[str, Any]:
    return {
        "schema": "css.canonical_broker_portfolio.v1",
        "status": _UNAVAILABLE,
        "broker": str(broker or _UNAVAILABLE).upper() if broker not in (None, "") else _UNAVAILABLE,
        "source": _UNAVAILABLE,
        "timestamp": _UNAVAILABLE,
        "freshness": {},
        "reason": reason,
        "metrics": {
            "cash": unavailable_metric(reason=reason),
            "equity": unavailable_metric(reason=reason),
            "portfolio_value": unavailable_metric(reason=reason),
            "buying_power": unavailable_metric(reason=reason),
            "available_balance": unavailable_metric(reason=reason),
            "margin_available": unavailable_metric(reason=reason),
            "margin_used": unavailable_metric(reason=reason),
            "session_pnl": unavailable_metric(reason=reason),
            "realized_pnl": unavailable_metric(reason=reason),
            "unrealized_pnl": unavailable_metric(reason=reason),
            "open_positions": unavailable_metric(reason=reason),
            "next_maturity": unavailable_metric(reason=reason),
        },
        "exposures": [],
        "session_pnl_by_instrument": {"status": _UNAVAILABLE, "rows": [], "reason": reason},
        "maturity": {
            "status": _UNAVAILABLE,
            "profile": _UNAVAILABLE,
            "next_maturity": _UNAVAILABLE,
            "rows": [],
            "source": _UNAVAILABLE,
            "reason": reason,
        },
        **SAFETY,
    }


def apply_canonical_broker_portfolio_bridge(
    dashboard_payload: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Any = None,
) -> dict[str, Any]:
    payload = dict(dashboard_payload) if isinstance(dashboard_payload, Mapping) else {}
    existing = payload.get("canonical_broker_portfolio")
    if not (
        isinstance(existing, Mapping)
        and existing.get("schema") == "css.canonical_broker_portfolio.v1"
    ):
        payload["canonical_broker_portfolio"] = build_canonical_broker_portfolio(
            payload,
            now=now,
            policy=policy,
            policy_path=policy_path,
        )
    _maybe_project_binance_spot_section(payload)
    return payload


def build_canonical_broker_portfolio(
    payload: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_path: Any = None,
) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    broker = _resolve_broker(source)
    clock = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if broker == "COINBASE":
        return _from_coinbase(source, now=clock, policy=policy, policy_path=policy_path)
    if broker == "BINANCE":
        return _from_binance(source, now=clock, policy=policy, policy_path=policy_path)
    if broker == "OANDA":
        return _from_oanda(source, now=clock, policy=policy, policy_path=policy_path)
    if broker == "QUESTRADE":
        return _from_questrade(source, now=clock, policy=policy, policy_path=policy_path)
    return empty_canonical_portfolio(broker=broker or _UNAVAILABLE, reason="unsupported_or_unselected_broker")


def _from_coinbase(
    payload: Mapping[str, Any],
    *,
    now: datetime,
    policy: Mapping[str, Any] | None,
    policy_path: Any,
) -> dict[str, Any]:
    existing = payload.get("spot_asset_balances") if isinstance(payload.get("spot_asset_balances"), Mapping) else {}
    validation = _coinbase_validation(payload)
    if existing.get("status") == _AVAILABLE and existing.get("rows"):
        balances = dict(existing)
        freshness = dict(existing.get("freshness") or {})
        timestamp = str(existing.get("timestamp") or _UNAVAILABLE)
        source = str(existing.get("source") or SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY)
    else:
        balances = build_spot_asset_balances(
            selected_broker="COINBASE",
            canonical_mode=_resolve_mode(payload),
            coinbase_validation=validation,
            now=now,
            policy=policy,
            policy_path=policy_path,
        )
        freshness = dict(balances.get("freshness") or {})
        timestamp = str(balances.get("timestamp") or _UNAVAILABLE)
        source = str(balances.get("source") or _UNAVAILABLE)
    if balances.get("status") != _AVAILABLE:
        return empty_canonical_portfolio(
            broker="COINBASE",
            reason=str(balances.get("reason") or "coinbase_balances_unavailable"),
        )
    account = _mapping(payload.get("account_summary"))
    metrics = {key: unavailable_metric(reason="unsupported_for_coinbase_spot") for key in empty_canonical_portfolio()["metrics"]}
    if str(account.get("source") or "") == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY:
        if str(account.get("cash_balance_availability") or "") == _AVAILABLE and _is_number(account.get("cash_balance")):
            metrics["cash"] = reported_metric(float(account.get("cash_balance")), origin=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY)
        if str(account.get("total_equity_availability") or "") == _AVAILABLE and _is_number(account.get("total_equity")):
            equity = reported_metric(float(account.get("total_equity")), origin=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY)
            metrics["equity"] = equity
            metrics["portfolio_value"] = dict(equity)
        if str(account.get("buying_power_availability") or "") == _AVAILABLE and _is_number(account.get("buying_power")):
            metrics["buying_power"] = reported_metric(
                float(account.get("buying_power")),
                origin=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
            )
        if str(account.get("available_margin_availability") or "") == _AVAILABLE and _is_number(account.get("available_balance", account.get("available_margin"))):
            metrics["available_balance"] = reported_metric(
                float(account.get("available_balance", account.get("available_margin"))),
                origin=SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
            )
    exposures = []
    for row in balances.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        exposures.append(
            {
                "exposure_kind": EXPOSURE_ACCOUNT_ASSET_BALANCE,
                "section_label": str(balances.get("section_label") or COINBASE_BALANCE_LABEL),
                "broker": "COINBASE",
                "asset": row.get("asset"),
                "available_quantity": row.get("available_quantity"),
                "available_quantity_availability": row.get("available_quantity_availability"),
                "held_quantity": row.get("held_quantity"),
                "held_quantity_availability": row.get("held_quantity_availability"),
                "total_quantity": row.get("total_quantity"),
                "total_quantity_availability": row.get("total_quantity_availability"),
                "total_quantity_provenance": row.get("total_quantity_provenance") or _UNAVAILABLE,
                "market_value": None,
                "market_value_availability": _UNAVAILABLE,
                "unrealized_pnl": None,
                "unrealized_pnl_availability": _UNAVAILABLE,
                "realized_pnl": None,
                "realized_pnl_availability": _UNAVAILABLE,
                "maturity": None,
                "maturity_availability": _UNAVAILABLE,
                "availability": _AVAILABLE,
                "provenance": PROVENANCE_BROKER_REPORTED,
                "source": source,
                "not_a_position": True,
            }
        )
    return {
        **empty_canonical_portfolio(broker="COINBASE", reason="ok"),
        "status": _AVAILABLE,
        "source": source,
        "timestamp": timestamp,
        "freshness": freshness,
        "reason": "ok",
        "metrics": metrics,
        "exposures": exposures,
    }


def _from_binance(
    payload: Mapping[str, Any],
    *,
    now: datetime,
    policy: Mapping[str, Any] | None,
    policy_path: Any,
) -> dict[str, Any]:
    if not _live_read_only(_resolve_mode(payload)):
        return empty_canonical_portfolio(broker="BINANCE", reason="canonical_mode_not_live_read_only")
    validation = _binance_validation(payload)
    broker_validation = _mapping(validation.get("broker_validation")) or validation
    status = str(broker_validation.get("validation_status") or validation.get("validation_status") or "").upper()
    if status and status != "PASS":
        return empty_canonical_portfolio(broker="BINANCE", reason="validation_status_not_pass")
    rows = (
        broker_validation.get("account_asset_balances")
        or validation.get("account_asset_balances")
        or _mapping(payload.get("account_summary")).get("balances")
        or []
    )
    if not isinstance(rows, list) or not rows:
        return empty_canonical_portfolio(broker="BINANCE", reason="no_trustworthy_balance_rows")
    snapshot = {
        "timestamp": _first_present(
            broker_validation.get("validation_timestamp"),
            validation.get("validation_timestamp"),
            broker_validation.get("last_successful_sync"),
            validation.get("last_successful_sync"),
            payload.get("timestamp"),
        )
    }
    freshness = evaluate_canonical_broker_snapshot_freshness(snapshot, now=now, policy=policy, policy_path=policy_path)
    if not freshness.get("ok"):
        return empty_canonical_portfolio(broker="BINANCE", reason=f"freshness_{freshness.get('reason')}")
    exposures = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        asset = str(raw.get("asset") or raw.get("currency") or "").strip().upper()
        if not asset:
            continue
        available = raw.get("available_quantity")
        if available is None and "free" in raw:
            available = raw.get("free")
        elif available is None and "available_balance" in raw:
            available = raw.get("available_balance")
        held_present = "held_quantity" in raw or "locked" in raw
        held = raw.get("held_quantity") if "held_quantity" in raw else raw.get("locked") if "locked" in raw else None
        held_avail = (
            str(raw.get("held_quantity_availability") or "").upper() == _AVAILABLE
            or held_present
        )
        total_prov = str(raw.get("total_quantity_provenance") or "")
        total = raw.get("total_quantity") if total_prov == "derived_available_plus_held" else None
        if total is None and _is_number(available) and held_avail and _is_number(held):
            total = float(available) + float(held)
            total_prov = "derived_available_plus_held"
        exposures.append(
            {
                "exposure_kind": EXPOSURE_ACCOUNT_ASSET_BALANCE,
                "section_label": "Account Asset Balances",
                "broker": "BINANCE",
                "asset": asset,
                "available_quantity": available,
                "available_quantity_availability": raw.get("available_quantity_availability")
                or (_AVAILABLE if available is not None else _UNAVAILABLE),
                "held_quantity": held if held_avail else None,
                "held_quantity_availability": _AVAILABLE if held_avail else _UNAVAILABLE,
                "held_quantity_field": "locked",
                "available_quantity_field": "free",
                "total_quantity": total,
                "total_quantity_availability": _AVAILABLE if total_prov == "derived_available_plus_held" and total is not None else _UNAVAILABLE,
                "total_quantity_provenance": total_prov or _UNAVAILABLE,
                "market_value": None,
                "market_value_availability": _UNAVAILABLE,
                "unrealized_pnl": None,
                "unrealized_pnl_availability": _UNAVAILABLE,
                "maturity": None,
                "maturity_availability": _UNAVAILABLE,
                "availability": _AVAILABLE,
                "provenance": PROVENANCE_BROKER_REPORTED,
                "source": SOURCE_BINANCE_LIVE_READ_ONLY,
                "not_a_position": True,
            }
        )
    if not exposures:
        return empty_canonical_portfolio(broker="BINANCE", reason="no_trustworthy_balance_rows")
    return {
        **empty_canonical_portfolio(broker="BINANCE", reason="ok"),
        "status": _AVAILABLE,
        "source": SOURCE_BINANCE_LIVE_READ_ONLY,
        "timestamp": snapshot["timestamp"] or _UNAVAILABLE,
        "freshness": freshness,
        "reason": "ok",
        "exposures": exposures,
    }


def _from_oanda(
    payload: Mapping[str, Any],
    *,
    now: datetime,
    policy: Mapping[str, Any] | None,
    policy_path: Any,
) -> dict[str, Any]:
    if not _live_read_only(_resolve_mode(payload)):
        return empty_canonical_portfolio(broker="OANDA", reason="canonical_mode_not_live_read_only")
    account = _oanda_account(payload)
    positions = _oanda_positions(payload)
    snapshot = {
        "timestamp": _first_present(
            account.get("timestamp"),
            account.get("last_successful_sync"),
            _mapping(payload.get("oanda_live_validation")).get("validation_timestamp"),
            _mapping(_mapping(payload.get("oanda_live_validation")).get("broker_validation")).get("validation_timestamp"),
            _mapping(payload.get("oanda_live_validation")).get("last_successful_sync"),
            payload.get("timestamp"),
        )
    }
    freshness = evaluate_canonical_broker_snapshot_freshness(snapshot, now=now, policy=policy, policy_path=policy_path)
    if not freshness.get("ok"):
        return empty_canonical_portfolio(broker="OANDA", reason=f"freshness_{freshness.get('reason')}")
    if not account and not positions:
        return empty_canonical_portfolio(broker="OANDA", reason="no_oanda_account_or_position_evidence")
    metrics = {key: unavailable_metric(reason="unsupported_or_unreported") for key in empty_canonical_portfolio()["metrics"]}
    if _is_number(account.get("balance") if "balance" in account else account.get("cash_balance")):
        metrics["cash"] = reported_metric(
            float(account.get("balance", account.get("cash_balance"))),
            origin=SOURCE_OANDA_LIVE_READ_ONLY,
        )
    if _is_number(account.get("NAV") if "NAV" in account else account.get("equity") if "equity" in account else account.get("total_equity")):
        equity_val = account.get("NAV", account.get("equity", account.get("total_equity")))
        metrics["equity"] = reported_metric(float(equity_val), origin=SOURCE_OANDA_LIVE_READ_ONLY)
        metrics["portfolio_value"] = reported_metric(float(equity_val), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "buying_power" in account and _is_number(account.get("buying_power")):
        metrics["buying_power"] = reported_metric(float(account.get("buying_power")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    elif "marginAvailable" in account and _is_number(account.get("marginAvailable")):
        metrics["buying_power"] = reported_metric(float(account.get("marginAvailable")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
        metrics["margin_available"] = reported_metric(float(account.get("marginAvailable")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "marginAvailable" in account and _is_number(account.get("marginAvailable")):
        metrics["margin_available"] = reported_metric(float(account.get("marginAvailable")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "margin_available" in account and _is_number(account.get("margin_available")):
        metrics["margin_available"] = reported_metric(float(account.get("margin_available")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "marginUsed" in account and _is_number(account.get("marginUsed")):
        metrics["margin_used"] = reported_metric(float(account.get("marginUsed")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "margin_used" in account and _is_number(account.get("margin_used")):
        metrics["margin_used"] = reported_metric(float(account.get("margin_used")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    if "unrealizedPL" in account and _is_number(account.get("unrealizedPL")):
        metrics["unrealized_pnl"] = reported_metric(float(account.get("unrealizedPL")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    elif "unrealized_pnl" in account and _is_number(account.get("unrealized_pnl")):
        metrics["unrealized_pnl"] = reported_metric(float(account.get("unrealized_pnl")), origin=SOURCE_OANDA_LIVE_READ_ONLY)
    exposures = [_oanda_position_row(item) for item in positions if isinstance(item, Mapping)]
    exposures = [row for row in exposures if row is not None]
    if "positions" in _oanda_position_container(payload) or exposures:
        metrics["open_positions"] = derived_metric(
            len(exposures),
            origin=SOURCE_OANDA_LIVE_READ_ONLY,
            reason="count_of_broker_reported_fx_positions",
        )
    return {
        **empty_canonical_portfolio(broker="OANDA", reason="ok"),
        "status": _AVAILABLE,
        "source": SOURCE_OANDA_LIVE_READ_ONLY,
        "timestamp": snapshot["timestamp"] or _UNAVAILABLE,
        "freshness": freshness,
        "reason": "ok",
        "metrics": metrics,
        "exposures": exposures,
        "session_pnl_by_instrument": {
            "status": _UNAVAILABLE,
            "rows": [],
            "reason": "oanda_session_and_realized_pnl_not_authoritative",
        },
    }


def _from_questrade(
    payload: Mapping[str, Any],
    *,
    now: datetime,
    policy: Mapping[str, Any] | None,
    policy_path: Any,
) -> dict[str, Any]:
    qt = _questrade_payload(payload)
    if _questrade_unavailable(qt):
        return empty_canonical_portfolio(
            broker="QUESTRADE",
            reason=str(qt.get("failure_reason") or qt.get("status") or "provider_unavailable"),
        )
    qt = _questrade_bridge_existing_contract(qt)
    snapshot = {
        "timestamp": _first_present(
            qt.get("provider_timestamp"),
            qt.get("timestamp"),
            qt.get("acquisition_timestamp"),
            _mapping(qt.get("balances_contract")).get("timestamp"),
            _mapping(qt.get("balances_contract")).get("provider_timestamp"),
        )
    }
    if snapshot["timestamp"] in (None, ""):
        balances = qt.get("balances")
        if isinstance(balances, Mapping):
            snapshot["timestamp"] = _first_present(balances.get("timestamp"), balances.get("provider_timestamp"))
        positions = qt.get("positions") if isinstance(qt.get("positions"), Mapping) else qt
        if snapshot["timestamp"] in (None, "") and isinstance(positions, Mapping):
            snapshot["timestamp"] = _first_present(positions.get("timestamp"), positions.get("provider_timestamp"))
    freshness = evaluate_canonical_broker_snapshot_freshness(snapshot, now=now, policy=policy, policy_path=policy_path)
    if not freshness.get("ok"):
        return empty_canonical_portfolio(broker="QUESTRADE", reason=f"freshness_{freshness.get('reason')}")
    balance_rows = _questrade_balance_rows(qt)
    holding_rows = _questrade_holdings(qt)
    option_rows = _questrade_option_positions(qt)
    if not balance_rows and not holding_rows and not option_rows:
        return empty_canonical_portfolio(broker="QUESTRADE", reason="no_trustworthy_questrade_rows")
    metrics = {key: unavailable_metric(reason="unsupported_or_unreported") for key in empty_canonical_portfolio()["metrics"]}
    primary = balance_rows[0] if balance_rows else {}
    if _is_number(primary.get("cash")):
        metrics["cash"] = reported_metric(float(primary.get("cash")), origin="QUESTRADE_BALANCES")
    if _is_number(primary.get("equity")):
        metrics["equity"] = reported_metric(float(primary.get("equity")), origin="QUESTRADE_BALANCES")
        metrics["portfolio_value"] = reported_metric(float(primary.get("equity")), origin="QUESTRADE_BALANCES")
    if _is_number(primary.get("buying_power")):
        metrics["buying_power"] = reported_metric(float(primary.get("buying_power")), origin="QUESTRADE_BALANCES")
    if _is_number(primary.get("available_cash")):
        metrics["available_balance"] = reported_metric(float(primary.get("available_cash")), origin="QUESTRADE_BALANCES")
    exposures = []
    for row in holding_rows:
        exposures.append(_questrade_holding_exposure(row))
    maturity_rows = []
    for row in option_rows:
        exposure = _questrade_option_exposure(row)
        exposures.append(exposure)
        if exposure.get("maturity_availability") == _AVAILABLE and exposure.get("maturity") not in (None, ""):
            maturity_rows.append(
                {
                    "instrument": exposure.get("instrument"),
                    "expiry": exposure.get("maturity"),
                    "security_type": "OPTION",
                    "provenance": PROVENANCE_BROKER_REPORTED,
                    "source": SOURCE_QUESTRADE_READ_ONLY,
                }
            )
    if option_rows or "option_positions" in qt or "positions" in qt or "holdings" in qt:
        metrics["open_positions"] = derived_metric(
            len(option_rows),
            origin=SOURCE_QUESTRADE_READ_ONLY,
            reason="count_of_broker_reported_option_positions",
        )
    next_maturity = _UNAVAILABLE
    if maturity_rows:
        dates = sorted(str(item["expiry"]) for item in maturity_rows if item.get("expiry"))
        next_maturity = dates[0] if dates else _UNAVAILABLE
        if next_maturity != _UNAVAILABLE:
            metrics["next_maturity"] = reported_metric(next_maturity, origin="QUESTRADE_POSITIONS")
    return {
        **empty_canonical_portfolio(broker="QUESTRADE", reason="ok"),
        "status": _AVAILABLE,
        "source": str(qt.get("provenance") or SOURCE_QUESTRADE_READ_ONLY),
        "timestamp": snapshot["timestamp"] or _UNAVAILABLE,
        "freshness": freshness,
        "reason": "ok",
        "metrics": metrics,
        "exposures": exposures,
        "maturity": {
            "status": _AVAILABLE if maturity_rows else _UNAVAILABLE,
            "profile": "QUESTRADE_OPTION_EXPIRY" if maturity_rows else _UNAVAILABLE,
            "next_maturity": next_maturity,
            "rows": maturity_rows,
            "source": SOURCE_QUESTRADE_READ_ONLY if maturity_rows else _UNAVAILABLE,
            "reason": "ok" if maturity_rows else "no_authoritative_expiry",
        },
    }


def _oanda_position_row(item: Mapping[str, Any]) -> dict[str, Any] | None:
    instrument = item.get("instrument") or item.get("symbol")
    if instrument in (None, ""):
        return None
    units = None
    side = item.get("side")
    unrealized = None
    unrealized_avail = _UNAVAILABLE
    if isinstance(item.get("long"), Mapping) or isinstance(item.get("short"), Mapping):
        long_leg = _mapping(item.get("long"))
        short_leg = _mapping(item.get("short"))
        long_units = _as_number(long_leg.get("units")) if "units" in long_leg else None
        short_units = _as_number(short_leg.get("units")) if "units" in short_leg else None
        if long_units is not None or short_units is not None:
            units = (long_units or 0.0) - (short_units or 0.0)
            side = "BUY" if units >= 0 else "SELL"
        if "unrealizedPL" in long_leg or "unrealizedPL" in short_leg:
            parts = []
            if "unrealizedPL" in long_leg and _is_number(long_leg.get("unrealizedPL")):
                parts.append(float(long_leg.get("unrealizedPL")))
            if "unrealizedPL" in short_leg and _is_number(short_leg.get("unrealizedPL")):
                parts.append(float(short_leg.get("unrealizedPL")))
            if parts:
                unrealized = sum(parts) if len(parts) > 1 else parts[0]
                unrealized_avail = _AVAILABLE
        elif "unrealized_pnl" in long_leg or "unrealized_pnl" in short_leg:
            parts = []
            if _is_number(long_leg.get("unrealized_pnl")):
                parts.append(float(long_leg.get("unrealized_pnl")))
            if _is_number(short_leg.get("unrealized_pnl")):
                parts.append(float(short_leg.get("unrealized_pnl")))
            if parts:
                unrealized = sum(parts) if len(parts) > 1 else parts[0]
                unrealized_avail = _AVAILABLE
    elif "units" in item and _is_number(item.get("units")):
        units = float(item.get("units"))
    if "unrealizedPL" in item and _is_number(item.get("unrealizedPL")):
        unrealized = float(item.get("unrealizedPL"))
        unrealized_avail = _AVAILABLE
    elif "unrealized_pnl" in item and _is_number(item.get("unrealized_pnl")):
        unrealized = float(item.get("unrealized_pnl"))
        unrealized_avail = _AVAILABLE
    if units is None and unrealized is None and instrument:
        return None
    return {
        "exposure_kind": EXPOSURE_POSITION,
        "section_label": "Open Positions",
        "broker": "OANDA",
        "instrument": instrument,
        "asset_class": "FX",
        "units": units,
        "side": side or _UNAVAILABLE,
        "unrealized_pnl": unrealized,
        "unrealized_pnl_availability": unrealized_avail,
        "unrealized_pnl_provenance": PROVENANCE_BROKER_REPORTED if unrealized_avail == _AVAILABLE else PROVENANCE_UNAVAILABLE,
        "realized_pnl": None,
        "realized_pnl_availability": _UNAVAILABLE,
        "session_pnl": None,
        "session_pnl_availability": _UNAVAILABLE,
        "maturity": None,
        "maturity_availability": _UNAVAILABLE,
        "market_value": None,
        "market_value_availability": _UNAVAILABLE,
        "availability": _AVAILABLE,
        "provenance": PROVENANCE_BROKER_REPORTED,
        "source": SOURCE_OANDA_LIVE_READ_ONLY,
        "not_a_position": False,
    }


def _questrade_holding_exposure(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "exposure_kind": EXPOSURE_HOLDING,
        "section_label": "Holdings",
        "broker": "QUESTRADE",
        "instrument": row.get("symbol") or row.get("provider_native_symbol"),
        "security_type": row.get("security_type") or "UNKNOWN",
        "quantity": row.get("quantity"),
        "market_value": row.get("market_value"),
        "market_value_availability": _AVAILABLE if _is_number(row.get("market_value")) else _UNAVAILABLE,
        "unrealized_pnl": row.get("unrealized_pnl"),
        "unrealized_pnl_availability": _AVAILABLE if _is_number(row.get("unrealized_pnl")) else _UNAVAILABLE,
        "unrealized_pnl_provenance": PROVENANCE_BROKER_REPORTED if _is_number(row.get("unrealized_pnl")) else PROVENANCE_UNAVAILABLE,
        "maturity": None,
        "maturity_availability": _UNAVAILABLE,
        "availability": _AVAILABLE,
        "provenance": PROVENANCE_BROKER_REPORTED,
        "source": str(row.get("provenance") or "QUESTRADE_POSITIONS"),
        "not_a_position": False,
    }


def _questrade_option_exposure(row: Mapping[str, Any]) -> dict[str, Any]:
    expiry = row.get("expiry") or row.get("expiryDate")
    has_expiry = expiry not in (None, "")
    return {
        "exposure_kind": EXPOSURE_POSITION,
        "section_label": "Open Positions",
        "broker": "QUESTRADE",
        "instrument": row.get("symbol") or row.get("provider_native_symbol"),
        "security_type": row.get("security_type") or "OPTION",
        "quantity": row.get("quantity"),
        "side": row.get("side"),
        "market_value": row.get("market_value"),
        "market_value_availability": _AVAILABLE if _is_number(row.get("market_value")) else _UNAVAILABLE,
        "unrealized_pnl": row.get("unrealized_pnl"),
        "unrealized_pnl_availability": _AVAILABLE if _is_number(row.get("unrealized_pnl")) else _UNAVAILABLE,
        "unrealized_pnl_provenance": PROVENANCE_BROKER_REPORTED if _is_number(row.get("unrealized_pnl")) else PROVENANCE_UNAVAILABLE,
        "maturity": expiry if has_expiry else None,
        "maturity_availability": _AVAILABLE if has_expiry else _UNAVAILABLE,
        "availability": _AVAILABLE,
        "provenance": PROVENANCE_BROKER_REPORTED,
        "source": str(row.get("provenance") or "QUESTRADE_POSITIONS"),
        "not_a_position": False,
    }


def _maybe_project_binance_spot_section(payload: dict[str, Any]) -> None:
    portfolio = payload.get("canonical_broker_portfolio")
    if not isinstance(portfolio, Mapping) or portfolio.get("broker") != "BINANCE":
        return
    if payload.get("spot_asset_balances"):
        return
    rows = []
    for item in portfolio.get("exposures") or []:
        if not isinstance(item, Mapping) or item.get("exposure_kind") != EXPOSURE_ACCOUNT_ASSET_BALANCE:
            continue
        rows.append(
            {
                "asset": item.get("asset"),
                "available_quantity": item.get("available_quantity"),
                "available_quantity_availability": item.get("available_quantity_availability"),
                "held_quantity": item.get("held_quantity"),
                "held_quantity_availability": item.get("held_quantity_availability"),
                "total_quantity": item.get("total_quantity"),
                "total_quantity_availability": item.get("total_quantity_availability"),
                "total_quantity_provenance": item.get("total_quantity_provenance"),
                "market_value": None,
                "market_value_availability": _UNAVAILABLE,
                "availability": _AVAILABLE,
                "provenance": item.get("source") or SOURCE_BINANCE_LIVE_READ_ONLY,
            }
        )
    if portfolio.get("status") == _AVAILABLE and rows:
        payload["spot_asset_balances"] = {
            "status": _AVAILABLE,
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
            "timestamp": portfolio.get("timestamp"),
            "section_kind": "spot_asset_balances",
            "section_label": "Account Asset Balances",
            "market_value_availability": _UNAVAILABLE,
            "rows": rows,
            "reason": "ok",
            "freshness": dict(portfolio.get("freshness") or {}),
        }


def _resolve_broker(payload: Mapping[str, Any]) -> str:
    for candidate in (
        payload.get("selected_broker"),
        _mapping(payload.get("account_summary")).get("broker"),
        _mapping(payload.get("broker_summary")).get("selected_broker"),
        _mapping(payload.get("session")).get("selected_broker"),
    ):
        text = str(candidate or "").strip().upper()
        if text in {"COINBASE", "BINANCE", "OANDA", "QUESTRADE"}:
            return text
    if payload.get("spot_asset_balances") or payload.get("coinbase_validation") or payload.get("coinbase_live_validation"):
        return "COINBASE"
    if payload.get("binance_live_validation") or payload.get("binance_validation"):
        return "BINANCE"
    if payload.get("oanda_live_validation") or payload.get("oanda_positions"):
        return "OANDA"
    if payload.get("questrade_read_only") or payload.get("questrade_holdings"):
        return "QUESTRADE"
    return _UNAVAILABLE


def _resolve_mode(payload: Mapping[str, Any]) -> str:
    for candidate in (
        payload.get("canonical_mode"),
        payload.get("resolved_mode"),
        _mapping(payload.get("account_summary")).get("account_mode"),
        _mapping(payload.get("runtime_status")).get("runtime_mode"),
        _mapping(payload.get("session")).get("runtime_mode"),
    ):
        if candidate not in (None, ""):
            return str(candidate).strip().upper()
    return _UNAVAILABLE


def _live_read_only(mode: str) -> bool:
    return str(mode or "").strip().upper().replace("-", "_").replace(" ", "_") in {
        item.replace("-", "_").replace(" ", "_") for item in LIVE_READ_ONLY_MODES
    } or str(mode or "").strip().upper() in LIVE_READ_ONLY_MODES


def _coinbase_validation(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("coinbase_validation", "coinbase_live_validation"):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return value
    return {}


def _binance_validation(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("binance_live_validation", "binance_validation"):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return value
    return {}


def _oanda_account(payload: Mapping[str, Any]) -> dict[str, Any]:
    validation = _mapping(payload.get("oanda_live_validation"))
    broker_validation = _mapping(validation.get("broker_validation"))
    for candidate in (
        payload.get("oanda_account"),
        validation.get("account"),
        broker_validation.get("account"),
        validation.get("canonical_account_snapshot"),
        broker_validation.get("canonical_account_snapshot"),
    ):
        extracted = _extract_oanda_account(candidate)
        if extracted:
            return extracted
    account = _mapping(payload.get("account_summary"))
    if account:
        return account
    return {}


def _extract_oanda_account(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or not raw:
        return {}
    if isinstance(raw.get("account"), Mapping):
        return dict(raw.get("account"))
    data = raw.get("data")
    if isinstance(data, Mapping) and isinstance(data.get("account"), Mapping):
        return dict(data.get("account"))
    if any(key in raw for key in ("balance", "NAV", "nav", "marginAvailable", "marginUsed", "currency")):
        return dict(raw)
    return {}


def _oanda_position_container(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("oanda_positions", "position_state", "open_positions"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
        if isinstance(value, list):
            return {"positions": value}
    return {}


def _oanda_positions(payload: Mapping[str, Any]) -> list[Any]:
    container = _oanda_position_container(payload)
    for key in ("positions", "items", "open_positions"):
        value = container.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload.get("oanda_positions"), list):
        return list(payload.get("oanda_positions"))
    return []


def _questrade_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("questrade_read_only", "questrade_holdings", "questrade"):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _questrade_bridge_existing_contract(qt: Mapping[str, Any]) -> dict[str, Any]:
    """Promote already-mapped Questrade contracts, or map raw read-only payloads locally."""
    from backend.brokers.questrade.contracts import map_balances, map_positions

    bridged = dict(qt)
    if not _questrade_balance_rows(bridged):
        raw_balances = None
        if any(key in qt for key in ("perCurrencyBalances", "combinedBalances")):
            raw_balances = qt
        elif isinstance(qt.get("balances"), Mapping) and any(
            key in qt["balances"] for key in ("perCurrencyBalances", "combinedBalances", "balances")
        ):
            raw_balances = qt["balances"]
        if raw_balances is not None:
            mapped = map_balances(
                raw_balances,
                account_type=qt.get("account_type"),
                generated_at=str(qt.get("timestamp") or "") or None,
            )
            bridged["balances"] = mapped.get("balances")
            if bridged.get("provider_timestamp") in (None, ""):
                bridged["provider_timestamp"] = mapped.get("provider_timestamp")
    if not _questrade_holdings(bridged) and not _questrade_option_positions(bridged):
        raw_positions = None
        if isinstance(qt.get("positions"), list):
            raw_positions = {"positions": qt.get("positions"), "timestamp": qt.get("timestamp")}
        elif isinstance(qt.get("positions"), Mapping) and isinstance(qt["positions"].get("positions"), list):
            raw_positions = qt["positions"]
        if raw_positions is not None:
            mapped = map_positions(raw_positions, generated_at=str(qt.get("timestamp") or "") or None)
            bridged["holdings"] = mapped.get("holdings")
            bridged["option_positions"] = mapped.get("option_positions")
            if bridged.get("provider_timestamp") in (None, ""):
                bridged["provider_timestamp"] = mapped.get("provider_timestamp")
    return bridged


def _questrade_unavailable(qt: Mapping[str, Any]) -> bool:
    if qt.get("fabricated") is True:
        return True
    for key in ("status", "runtime_status", "failure_reason"):
        token = str(qt.get(key) or "").strip().upper()
        if token in QUESTRADE_UNAVAILABLE_STATUSES or token == "QUESTRADE_PROVIDER_UNAVAILABLE":
            return True
    return not qt


def _questrade_balance_rows(qt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    balances = qt.get("balances")
    if isinstance(balances, Mapping):
        rows = balances.get("balances")
        return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []
    if isinstance(balances, list):
        return [row for row in balances if isinstance(row, Mapping)]
    return []


def _questrade_holdings(qt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    positions = qt.get("positions") if isinstance(qt.get("positions"), Mapping) else qt
    rows = positions.get("holdings") if isinstance(positions, Mapping) else None
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, Mapping)]
    return []


def _questrade_option_positions(qt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    positions = qt.get("positions") if isinstance(qt.get("positions"), Mapping) else qt
    rows = positions.get("option_positions") if isinstance(positions, Mapping) else None
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, Mapping)]
    return []


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _is_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _as_number(value: Any) -> float | None:
    if not _is_number(value):
        return None
    return float(value)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", _UNAVAILABLE, "DATA UNAVAILABLE"):
            return value
    return None


__all__ = [
    "EXPOSURE_ACCOUNT_ASSET_BALANCE",
    "EXPOSURE_HOLDING",
    "EXPOSURE_POSITION",
    "PROVENANCE_BROKER_REPORTED",
    "PROVENANCE_DERIVED",
    "PROVENANCE_UNAVAILABLE",
    "apply_canonical_broker_portfolio_bridge",
    "build_canonical_broker_portfolio",
    "empty_canonical_portfolio",
]
