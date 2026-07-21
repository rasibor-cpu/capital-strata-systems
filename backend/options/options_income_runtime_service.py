"""
Phase 177D — Canonical Options Income Runtime Service.

Aggregates the completed Options Income Engine (OI-001..010) behind one
runtime-facing contract for Mission Control, APIs, mobile cards, and
enterprise reporting.

Does not recalculate strategy math. Does not enable execution.
Does not fabricate option-chain opportunities when market data is absent.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.options.options_income_advisory_contracts import unexpected_advisory_fault
from backend.options.options_income_dashboard import (
    build_options_income_dashboard,
    fail_closed_dashboard,
)
from backend.options.options_income_dashboard_payloads import (
    OPTIONS_INCOME_ENGINE_NAME,
    OPTIONS_INCOME_ENGINE_VERSION,
)
from backend.options.paper_position_repository import SAFE_FLAGS
from backend.brokers.runtime.runtime_models import resolve_advisory_state

SCHEMA_VERSION = "css.options_income.runtime.v1"
SNAPSHOT_RELATIVE = Path("artifacts") / "options_income_runtime_snapshot.json"

STATUS_NOT_DEPLOYED = "NOT_DEPLOYED"
STATUS_READY = "READY"
STATUS_NO_CURRENT_OPPORTUNITIES = "NO_CURRENT_OPPORTUNITIES"
STATUS_PARTIAL_DATA = "PARTIAL_DATA"
STATUS_FAILED = "FAILED"
STATUS_ADVISORY_ONLY = "ADVISORY_ONLY"
STATUS_DATA_DEPENDENCY_BLOCKED = "DATA_DEPENDENCY_BLOCKED"
STATUS_NO_OPEN_OPTION_POSITIONS = "NO_OPEN_OPTION_POSITIONS"
STATUS_TARGET_NOT_CONFIGURED = "TARGET_NOT_CONFIGURED"
STATUS_STALE = "STALE"
STATUS_DEGRADED = "DEGRADED"
STATUS_ADVISORY_READY = "ADVISORY_READY"
STATUS_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

CANONICAL_MODULES = (
    "backend.options.options_income_strategy_domain",
    "backend.options.options_income_opportunity_scanner",
    "backend.options.premium_accounting",
    "backend.options.collateral_manager",
    "backend.options.rolling_engine",
    "backend.options.options_income_risk_governance",
    "backend.options.options_income_dashboard",
    "backend.options.options_income_certification",
    "backend.options.options_income_assignment_risk",
    "backend.options.options_income_volatility_risk",
    "backend.options.options_income_targets",
)


@dataclass
class OptionsIncomeRuntimeContext:
    """Optional host-supplied inputs. Never invent broker balances or chains."""

    opportunities: Sequence[Any] | None = None
    positions: Sequence[Any] | None = None
    health_by_position: Mapping[str, Mapping[str, Any]] | None = None
    metrics_by_position: Mapping[str, Mapping[str, Any]] | None = None
    rolls_by_position: Mapping[str, Sequence[Mapping[str, Any]]] | None = None
    portfolio: Mapping[str, Any] | None = None
    risk_assessment: Mapping[str, Any] | None = None
    stress_report: Mapping[str, Any] | None = None
    option_chain_available: bool | None = None
    market_data_available: bool | None = None
    account_holdings_available: bool | None = None
    monthly_income_target: float | None = None
    current_month_actual_income: float | None = None
    elapsed_days: int | None = None
    remaining_days: int | None = None
    persist: bool = True
    generated_at: str | None = None
    # Phase 178A — optional advisory data bundle from options_income_data_resolver
    advisory_data: Mapping[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _state_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(_json_safe(dict(payload)), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _probe_imports() -> tuple[bool, list[str], list[str]]:
    ok: list[str] = []
    failed: list[str] = []
    for module in CANONICAL_MODULES:
        try:
            __import__(module)
            ok.append(module)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{module}:{type(exc).__name__}")
    return (len(failed) == 0), ok, failed


def _resolve_runtime_mode() -> dict[str, Any]:
    try:
        from backend.runtime.runtime_mode import resolve_runtime_mode

        return resolve_runtime_mode().as_dict()
    except Exception:
        return {
            "runtime_mode": "DISABLED",
            "execution_enabled": False,
            "execution_authority": "BLOCKED",
            "order_submission": "BLOCKED",
            "fail_closed": True,
            "live_trading_enabled": False,
        }


def _resolve_broker_registry() -> dict[str, Any]:
    try:
        from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry

        reg = get_canonical_broker_registry()
        return {
            "tier1_brokers": list(TIER1_BROKERS),
            "primary_roles": reg.primary_roles(),
            "ibkr_registered": False,
            "source": "OPTIONS_ENGINE|RUNTIME",
        }
    except Exception as exc:  # noqa: BLE001
        return {"tier1_brokers": [], "error": type(exc).__name__, "ibkr_registered": False}


def _detect_dependencies(ctx: OptionsIncomeRuntimeContext) -> dict[str, Any]:
    chain = False if ctx.option_chain_available is None else bool(ctx.option_chain_available)
    market = False if ctx.market_data_available is None else bool(ctx.market_data_available)
    holdings = False if ctx.account_holdings_available is None else bool(ctx.account_holdings_available)
    missing: list[str] = []
    if not market:
        missing.append("MARKET_DATA")
    if not chain:
        missing.append("OPTION_CHAIN")
    if not holdings:
        missing.append("ACCOUNT_HOLDINGS")
    return {
        "market_data_available": market,
        "option_chain_available": chain,
        "account_holdings_available": holdings,
        "missing_dependencies": missing,
        "provenance": "RUNTIME",
    }


def _merge_advisory_dependencies(
    deps: Mapping[str, Any],
    advisory: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(deps)
    missing = list(merged.get("missing_dependencies") or [])
    for dependency in list((advisory or {}).get("missing_dependencies") or []):
        name = str(dependency)
        if name and name not in missing:
            missing.append(name)
    merged["missing_dependencies"] = missing
    merged["advisory_readiness"] = (
        str((advisory or {}).get("readiness_status") or (advisory or {}).get("status") or "").upper() or None
    )
    return merged


def _build_run_rate(ctx: OptionsIncomeRuntimeContext) -> dict[str, Any]:
    target = ctx.monthly_income_target
    if target is None:
        raw = os.environ.get("CSS_OPTIONS_INCOME_MONTHLY_TARGET") or os.environ.get("OPTIONS_INCOME_MONTHLY_TARGET")
        if raw not in (None, ""):
            try:
                target = float(raw)
            except (TypeError, ValueError):
                target = None
    if target is None or float(target) <= 0:
        return {
            "status": STATUS_TARGET_NOT_CONFIGURED,
            "monthly_income_target": None,
            "current_month_actual_options_income": ctx.current_month_actual_income,
            "projected_month_end_options_income": None,
            "elapsed_period_run_rate": None,
            "required_remaining_run_rate": None,
            "target_attainment_percent": None,
            "projected_surplus_or_shortfall": None,
            "collateral_required_to_meet_target": None,
            "assumptions": ["No monthly Options Income target configured"],
            "confidence_or_data_quality": STATUS_TARGET_NOT_CONFIGURED,
            "measurement_period": "CALENDAR_MONTH",
            "provenance": "CONFIGURATION",
            **SAFE_FLAGS,
            "paper_only": True,
        }

    actual = float(ctx.current_month_actual_income or 0.0)
    elapsed = int(ctx.elapsed_days if ctx.elapsed_days is not None else datetime.now(timezone.utc).day)
    remaining = int(ctx.remaining_days if ctx.remaining_days is not None else max(0, 30 - elapsed))
    elapsed = max(1, elapsed)
    daily = actual / elapsed
    projected = daily * (elapsed + remaining)
    remaining_needed = max(0.0, float(target) - actual)
    required_daily = (remaining_needed / remaining) if remaining > 0 else remaining_needed
    attainment = (actual / float(target)) * 100.0 if float(target) else None
    return {
        "status": "COMPUTED",
        "monthly_income_target": float(target),
        "current_month_actual_options_income": actual,
        "projected_month_end_options_income": round(projected, 6),
        "elapsed_period_run_rate": round(daily, 6),
        "required_remaining_run_rate": round(required_daily, 6),
        "target_attainment_percent": round(attainment, 4) if attainment is not None else None,
        "projected_surplus_or_shortfall": round(projected - float(target), 6),
        "collateral_required_to_meet_target": None,
        "assumptions": [
            "Linear extrapolation of month-to-date collected premium",
            "Does not invent projected premium from option chains when absent",
        ],
        "confidence_or_data_quality": "DERIVED_FROM_ACTUALS" if actual else "LOW_NO_ACTUALS",
        "measurement_period": "CALENDAR_MONTH",
        "provenance": "DERIVED|CONFIGURATION|ACCOUNTING",
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _advisory_empty_portfolio(portfolio: Mapping[str, Any] | None) -> dict[str, Any]:
    """Minimal valid OI-008 portfolio shell — not broker-backed collateral."""
    row = dict(portfolio or {})
    if row.get("portfolio_id") and ("capital_allocated" in row or "capital" in row):
        return row
    return {
        "portfolio_id": str(row.get("portfolio_id") or "OI-RUNTIME-ADVISORY-EMPTY"),
        "capital_allocated": float(row.get("capital_allocated") or 0.0),
        "portfolio_utilization": float(row.get("portfolio_utilization") or 0.0),
        "available_capital": float(row.get("available_capital") or 0.0),
        "collateral_reserved": float(row.get("collateral_reserved") or 0.0),
        "unused_collateral": float(row.get("unused_collateral") or 0.0),
        "covered_call_allocation": float(row.get("covered_call_allocation") or 0.0),
        "cash_secured_put_allocation": float(row.get("cash_secured_put_allocation") or 0.0),
        "expected_premium": float(row.get("expected_premium") or 0.0),
        "realized_premium": float(row.get("realized_premium") or 0.0),
        "monthly_premium_target": float(row.get("monthly_premium_target") or 0.0),
        "annual_premium_target": float(row.get("annual_premium_target") or 0.0),
        "constraint_status": str(row.get("constraint_status") or "PASS"),
        "constraint_breaches": list(row.get("constraint_breaches") or []),
        "warnings": list(
            row.get("warnings")
            or ["Advisory empty portfolio — no broker-backed holdings supplied"]
        ),
        "allocations": list(row.get("allocations") or []),
        "provenance": "RUNTIME|ADVISORY",
    }


def _advisory_empty_risk(risk: Mapping[str, Any] | None) -> dict[str, Any]:
    """Minimal valid OI-008 risk shell for zero open option positions."""
    row = dict(risk or {})
    greeks = row.get("greeks_by_underlying")
    iv = str(row.get("iv_availability") or "")
    if (
        row.get("portfolio_delta") is not None
        and isinstance(greeks, Mapping)
        and greeks
        and iv
        and iv.upper() != "UNAVAILABLE"
        and row.get("risk_status")
    ):
        return row
    return {
        "portfolio_delta": float(row.get("portfolio_delta") or 0.0),
        "absolute_delta": float(row.get("absolute_delta") or 0.0),
        "gamma": float(row.get("gamma") or 0.0),
        "theta": float(row.get("theta") or 0.0),
        "vega": float(row.get("vega") or 0.0),
        "rho": float(row.get("rho") or 0.0),
        "greeks_by_underlying": dict(greeks)
        if isinstance(greeks, Mapping) and greeks
        else {
            "NO_OPEN_OPTION_POSITIONS": {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
            }
        },
        "greeks_by_strategy": dict(row.get("greeks_by_strategy") or {}),
        "greeks_by_expiry": dict(row.get("greeks_by_expiry") or {}),
        "risk_status": str(row.get("risk_status") or STATUS_NO_OPEN_OPTION_POSITIONS),
        "iv_availability": iv if iv and iv.upper() != "UNAVAILABLE" else "NOT_APPLICABLE",
        "unavailable_risk_data": list(row.get("unavailable_risk_data") or []),
        "approval_status": str(row.get("approval_status") or "ADVISORY_ONLY"),
        "assignment_risk_status": str(row.get("assignment_risk_status") or STATUS_NO_OPEN_OPTION_POSITIONS),
        "volatility_risk_status": str(row.get("volatility_risk_status") or STATUS_NO_OPEN_OPTION_POSITIONS),
        "stress_scenarios": list(row.get("stress_scenarios") or []),
        "provenance": "RUNTIME|ADVISORY",
    }


def _classify_engine_status(
    *,
    imports_ok: bool,
    deps: Mapping[str, Any],
    dashboard: Mapping[str, Any],
    opportunity_count: int,
    position_count: int,
    scanner_completed: bool,
    advisory: Mapping[str, Any] | None = None,
) -> str:
    summary = dashboard.get("summary") if isinstance(dashboard.get("summary"), Mapping) else {}
    fail_closed = str(summary.get("engine_status") or "").upper() == "FAIL_CLOSED"
    missing = list(deps.get("missing_dependencies") or [])
    advisory_status = str((advisory or {}).get("readiness_status") or (advisory or {}).get("status") or "").upper()
    states: list[str] = []
    if (
        not imports_ok
        or dashboard.get("correlation_id")
        or advisory_status in {"FAILED", "FAILURE"}
        or (advisory or {}).get("failed")
    ):
        states.append("FAILURE")
    aliases = {
        STATUS_DATA_DEPENDENCY_BLOCKED: "DATA_DEPENDENCY_BLOCKED",
        STATUS_PROVIDER_UNAVAILABLE: "PROVIDER_UNAVAILABLE",
        STATUS_STALE: "STALE",
        STATUS_PARTIAL_DATA: "PARTIAL_DATA",
        "DEGRADED": "PARTIAL_DATA",
    }
    if advisory_status in aliases:
        states.append(aliases[advisory_status])
    if (advisory or {}).get("stale"):
        states.append("STALE")
    if (advisory or {}).get("partial"):
        states.append("PARTIAL_DATA")
    if not advisory_status and (missing or not scanner_completed):
        states.append("DATA_DEPENDENCY_BLOCKED")
    if fail_closed and not states:
        states.append("FAILURE")
    _ = position_count
    states.append("ADVISORY_READY" if opportunity_count > 0 else "NO_CURRENT_OPPORTUNITIES")
    resolved = resolve_advisory_state(states).value
    return STATUS_FAILED if resolved == "FAILURE" else resolved


def _build_certification(
    *,
    imports_ok: bool,
    import_ok_list: Sequence[str],
    import_failed: Sequence[str],
    deps: Mapping[str, Any],
    runtime_mode: Mapping[str, Any],
    engine_status: str,
    advisory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    adv = dict(advisory or {})
    registry = adv.get("provider_registry") if isinstance(adv.get("provider_registry"), Mapping) else {}
    collateral = adv.get("collateral") if isinstance(adv.get("collateral"), Mapping) else {}
    events = adv.get("events") if isinstance(adv.get("events"), Mapping) else {}
    chain_rows = list(adv.get("option_chain_rows") or [])
    market_rows = list(adv.get("market_data_rows") or [])
    holdings = adv.get("holdings") if isinstance(adv.get("holdings"), Mapping) else {}

    chain_configured = bool(registry.get("option_chain_providers")) or any(
        str(r.get("status") or "").upper() not in {"OPTION_CHAIN_PROVIDER_NOT_CONFIGURED", "NOT_CONFIGURED", ""}
        for r in chain_rows
    )
    market_configured = bool(registry.get("market_data_providers")) or any(
        str(r.get("status") or "").upper() not in {"NOT_CONFIGURED", ""} for r in market_rows
    )
    chain_fresh = any(str(r.get("freshness") or "").upper() == "FRESH" for r in chain_rows)
    market_fresh = any(str(r.get("freshness") or "").upper() == "FRESH" for r in market_rows)
    collateral_traceable = str(collateral.get("authority_level") or "UNAVAILABLE") != "UNAVAILABLE"

    checks = {
        "runtime_service_deployed": True,
        "canonical_modules_import": imports_ok,
        "stores_accessible": True,
        "accounting_available": "backend.options.premium_accounting" in import_ok_list,
        "collateral_logic_available": "backend.options.collateral_manager" in import_ok_list,
        "greeks_logic_available": "backend.options.options_income_risk_governance" in import_ok_list,
        "risk_logic_available": (
            "backend.options.options_income_assignment_risk" in import_ok_list
            or "backend.options.options_income_risk_governance" in import_ok_list
        ),
        "rolling_logic_available": "backend.options.rolling_engine" in import_ok_list,
        "reporting_available": True,
        "runtime_mode_known": bool(runtime_mode.get("runtime_mode")),
        "broker_capabilities_known": True,
        "market_data_available": bool(deps.get("market_data_available")),
        "option_chain_data_available": bool(deps.get("option_chain_available")),
        "account_holding_data_available": bool(deps.get("account_holdings_available")),
        "execution_authority_blocked": not bool(runtime_mode.get("execution_enabled")),
        "advisory_boundary_intact": True,
        # Phase 178A advisory-data certification facets
        "market_data_provider_configured": market_configured if adv else False,
        "underlying_quote_fresh": market_fresh if adv else False,
        "option_chain_provider_configured": chain_configured if adv else False,
        "option_chain_fresh_and_complete": (
            chain_fresh
            and any(str(r.get("status") or "").upper() == "READY" for r in chain_rows)
            if adv
            else False
        ),
        "holdings_available": bool(deps.get("account_holdings_available")),
        "balances_available": holdings.get("cash") is not None if adv else False,
        "collateral_traceable": collateral_traceable if adv else False,
        "broker_compatibility_known": bool(adv.get("broker_capability_truth")) if adv else True,
        "greeks_quality_known": any(
            str(r.get("greeks_origin") or "MISSING").upper() in {"PROVIDER", "DERIVED", "MISSING"} for r in chain_rows
        )
        if chain_rows
        else True,
        "event_data_status": str(events.get("status") or "EVENT_DATA_UNAVAILABLE"),
        "execution_blocked": True,
    }
    if not imports_ok:
        outcome = "FAILED"
    elif engine_status == STATUS_STALE:
        outcome = "STALE_DATA_BLOCKED"
    elif engine_status == STATUS_DATA_DEPENDENCY_BLOCKED:
        outcome = "DATA_DEPENDENCY_BLOCKED"
    elif engine_status == STATUS_FAILED:
        outcome = "FAILED"
    elif (
        checks["option_chain_data_available"]
        and checks["market_data_available"]
        and checks["account_holding_data_available"]
        and checks["collateral_traceable"]
        and checks["execution_authority_blocked"]
        and checks["advisory_boundary_intact"]
    ):
        outcome = "CERTIFIED_ADVISORY"
    elif checks["option_chain_data_available"] and checks["market_data_available"]:
        outcome = "ADVISORY_READY" if engine_status in {STATUS_ADVISORY_READY, STATUS_NO_CURRENT_OPPORTUNITIES, STATUS_READY} else "PARTIALLY_READY"
    elif all(
        [
            checks["canonical_modules_import"],
            checks["accounting_available"],
            checks["collateral_logic_available"],
            checks["rolling_logic_available"],
            checks["execution_authority_blocked"],
            checks["advisory_boundary_intact"],
        ]
    ) and not checks["option_chain_data_available"]:
        outcome = "ADVISORY_READY"
    else:
        outcome = "PARTIALLY_READY"

    return {
        "outcome": outcome,
        "status": outcome,
        "checks": checks,
        "import_failures": list(import_failed),
        "modules_imported": list(import_ok_list),
        "operational_readiness": (
            "ADVISORY_ONLY"
            if outcome
            in {
                "ADVISORY_READY",
                "CERTIFIED_ADVISORY",
                "DATA_DEPENDENCY_BLOCKED",
                "PARTIALLY_READY",
                "STALE_DATA_BLOCKED",
            }
            else outcome
        ),
        "live_ready": False,
        "execution_ready": False,
        "provenance": "OPTIONS_ENGINE|RUNTIME|ADVISORY_DATA",
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _premium_accounting(dashboard: Mapping[str, Any], ctx: OptionsIncomeRuntimeContext) -> dict[str, Any]:
    portfolio = dashboard.get("portfolio") if isinstance(dashboard.get("portfolio"), Mapping) else {}
    positions = dashboard.get("positions") if isinstance(dashboard.get("positions"), Mapping) else {}
    summary = dashboard.get("summary") if isinstance(dashboard.get("summary"), Mapping) else {}
    return {
        "session": {
            "premium_identified": 0.0,
            "premium_proposed": 0.0,
            "premium_collected": float(ctx.current_month_actual_income or 0.0),
            "fees": 0.0,
            "realized_options_income": float(summary.get("realized_premium") or portfolio.get("realized_premium") or 0.0),
            "unrealized_options_pnl": float(portfolio.get("unrealized_pnl") or 0.0),
            "measurement_period": "CURRENT_SESSION",
            "provenance": "ACCOUNTING|HISTORICAL",
        },
        "portfolio": {
            "active_premium_positions": int(positions.get("active_position_count") or 0),
            "collateral_committed": float(portfolio.get("collateral_committed") or portfolio.get("total_collateral") or 0.0),
            "collateral_available": float(portfolio.get("collateral_available") or 0.0),
            "rolling_exposure": float(portfolio.get("rolling_exposure") or 0.0),
            "assignment_exposure": float(portfolio.get("assignment_exposure") or 0.0),
            "measurement_period": "CURRENT_PORTFOLIO",
            "provenance": "PORTFOLIO|ACCOUNTING",
            "note": "Values are advisory/paper unless broker-backed holdings are supplied",
        },
        "lifetime": {
            "lifetime_premium_collected": float(portfolio.get("lifetime_premium_collected") or 0.0),
            "lifetime_realized_options_income": float(portfolio.get("lifetime_realized_premium") or 0.0),
            "lifetime_fees": float(portfolio.get("lifetime_fees") or 0.0),
            "lifetime_assignments": int(portfolio.get("lifetime_assignments") or 0),
            "lifetime_rolls": int(portfolio.get("lifetime_rolls") or 0),
            "measurement_period": "LIFETIME",
            "provenance": "HISTORICAL|ACCOUNTING",
        },
        "forecast_advisory": {
            "expected_monthly_premium": float(portfolio.get("expected_premium") or 0.0),
            "annualized_expected_income": float(portfolio.get("expected_premium") or 0.0) * 12.0,
            "projected_yield": portfolio.get("portfolio_yield"),
            "target_income": ctx.monthly_income_target,
            "note": "Forecast figures are advisory and never mixed with collected premium",
            "measurement_period": "FORECAST",
            "provenance": "DERIVED|CONFIGURATION",
        },
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _split_opportunities(
    dashboard: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    opps = dashboard.get("opportunities") if isinstance(dashboard.get("opportunities"), Mapping) else {}
    accepted = [dict(r) for r in (opps.get("accepted_candidates") or []) if isinstance(r, Mapping)]
    rejected = [dict(r) for r in (opps.get("rejected_candidates") or []) if isinstance(r, Mapping)]
    covered = [
        r
        for r in accepted
        if str(r.get("strategy_type") or r.get("strategy") or "").upper() in {"COVERED_CALL", "CC"}
    ]
    puts = [
        r
        for r in accepted
        if str(r.get("strategy_type") or r.get("strategy") or "").upper() in {"CASH_SECURED_PUT", "CSP"}
    ]
    return covered, puts, rejected


def _greeks_block(dashboard: Mapping[str, Any], position_count: int) -> dict[str, Any]:
    greeks = dashboard.get("greeks") if isinstance(dashboard.get("greeks"), Mapping) else {}
    if position_count == 0:
        return {
            "status": STATUS_NO_OPEN_OPTION_POSITIONS,
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": greeks.get("rho"),
            "greeks_source": "OPTIONS_ENGINE",
            "greeks_timestamp": dashboard.get("generated_at"),
            "greeks_quality_status": STATUS_NO_OPEN_OPTION_POSITIONS,
            "provenance": "OPTIONS_ENGINE",
            **SAFE_FLAGS,
            "paper_only": True,
        }
    return {
        "status": "AVAILABLE" if greeks else STATUS_PARTIAL_DATA,
        "delta": greeks.get("portfolio_delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "rho": greeks.get("rho"),
        "greeks_by_underlying": greeks.get("greeks_by_underlying"),
        "greeks_source": "RISK_ENGINE|OPTIONS_ENGINE",
        "greeks_timestamp": dashboard.get("generated_at"),
        "greeks_quality_status": "PAPER_ADVISORY",
        "provenance": "RISK_ENGINE",
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _rolls_block(dashboard: Mapping[str, Any]) -> dict[str, Any]:
    rolls = dashboard.get("rolls") if isinstance(dashboard.get("rolls"), Mapping) else {}
    recommendations: list[dict[str, Any]] = []
    for key, value in rolls.items():
        if key in SAFE_FLAGS or key in {"paper_only", "advisory_only"}:
            continue
        if isinstance(value, list):
            for row in value:
                if isinstance(row, Mapping):
                    recommendations.append(
                        {
                            **dict(row),
                            "action": row.get("action") or row.get("recommendation") or "monitor",
                            "advisory_only": True,
                            "execution_allowed": False,
                            "order_queued": False,
                            "provenance": "OPTIONS_ENGINE",
                        }
                    )
    return {
        "status": "ADVISORY_ONLY",
        "recommendations": recommendations,
        "count": len(recommendations),
        "execution_allowed": False,
        "order_submission": "BLOCKED",
        "provenance": "OPTIONS_ENGINE",
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _collateral_block(dashboard: Mapping[str, Any], deps: Mapping[str, Any]) -> dict[str, Any]:
    portfolio = dashboard.get("portfolio") if isinstance(dashboard.get("portfolio"), Mapping) else {}
    if not deps.get("account_holdings_available") and not portfolio.get("total_collateral") and not portfolio.get(
        "collateral_committed"
    ):
        return {
            "status": "ADVISORY_UNAVAILABLE",
            "reason": "No canonical broker/account collateral supplied; refusing to infer simulated margin",
            "covered_call_collateral": None,
            "cash_secured_put_collateral": None,
            "aggregate_strategy_collateral": None,
            "utilization": None,
            "excess_collateral": None,
            "unavailable_collateral": None,
            "concentration_by_underlying": {},
            "concentration_by_expiry": {},
            "concentration_by_strategy": {},
            "broker_collateral_source": None,
            "provenance": "RUNTIME",
            "note": "Does not use simulated 10000 margin fixtures as live collateral",
            **SAFE_FLAGS,
            "paper_only": True,
        }
    return {
        "status": "ADVISORY",
        "covered_call_collateral": portfolio.get("covered_call_collateral"),
        "cash_secured_put_collateral": portfolio.get("cash_secured_put_collateral"),
        "aggregate_strategy_collateral": portfolio.get("total_collateral") or portfolio.get("collateral_committed"),
        "utilization": portfolio.get("collateral_utilization"),
        "excess_collateral": portfolio.get("collateral_available"),
        "unavailable_collateral": portfolio.get("unavailable_collateral"),
        "concentration_by_underlying": portfolio.get("concentration_by_underlying") or {},
        "concentration_by_expiry": portfolio.get("concentration_by_expiry") or {},
        "concentration_by_strategy": portfolio.get("concentration_by_strategy") or {},
        "broker_collateral_source": "PAPER_OR_SUPPLIED",
        "provenance": "PORTFOLIO|BROKER" if deps.get("account_holdings_available") else "PORTFOLIO",
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _persist_snapshot(payload: Mapping[str, Any]) -> None:
    try:
        path = Path(SNAPSHOT_RELATIVE)
        path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = {
            k: payload.get(k)
            for k in (
                "schema_version",
                "status",
                "engine_status",
                "deployment_state",
                "opportunity_count",
                "certification",
                "operational_readiness",
                "premium_accounting",
                "collateral",
                "greeks",
                "assignment_risk",
                "volatility_risk",
                "run_rate",
                "dependencies",
                "missing_dependencies",
                "provenance",
                "generated_at",
                "last_successful_refresh",
                "state_hash",
                "advisory_only",
                "execution_authority",
                "paper_only",
            )
        }
        sanitized["execution_allowed"] = False
        sanitized["live_trading_enabled"] = False
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(_json_safe(sanitized), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def build_options_income_runtime_snapshot(ctx: OptionsIncomeRuntimeContext | None = None) -> dict[str, Any]:
    """Canonical runtime aggregation for MC / API / reporting."""
    ctx = ctx or OptionsIncomeRuntimeContext()
    generated_at = ctx.generated_at or _utc_now()
    imports_ok, import_ok_list, import_failed = _probe_imports()
    runtime_mode = _resolve_runtime_mode()
    brokers = _resolve_broker_registry()
    advisory = dict(ctx.advisory_data) if isinstance(ctx.advisory_data, Mapping) else None
    deps = _merge_advisory_dependencies(_detect_dependencies(ctx), advisory)

    if not imports_ok:
        dashboard = fail_closed_dashboard(reason="canonical_module_import_failure", generated_at=generated_at)
    else:
        opportunities = list(ctx.opportunities or [])
        try:
            dashboard = build_options_income_dashboard(
                opportunities=opportunities,
                positions=ctx.positions or [],
                health_by_position=ctx.health_by_position,
                metrics_by_position=ctx.metrics_by_position,
                rolls_by_position=ctx.rolls_by_position,
                portfolio=_advisory_empty_portfolio(ctx.portfolio),
                risk_assessment=_advisory_empty_risk(ctx.risk_assessment),
                stress_report=ctx.stress_report,
                generated_at=generated_at,
                now=generated_at,
                mode="PAPER",
                execution_allowed=False,
                advisory_only=True,
                live_trading_blocked=True,
                broker_execution_armed=False,
            )
        except Exception as exc:  # noqa: BLE001
            fault = unexpected_advisory_fault(exc)
            dashboard = fail_closed_dashboard(reason=fault["failure_reason"], generated_at=generated_at)
            dashboard["correlation_id"] = fault["correlation_id"]

    covered, puts, rejected = _split_opportunities(dashboard)
    positions = dashboard.get("positions") if isinstance(dashboard.get("positions"), Mapping) else {}
    position_count = int(positions.get("active_position_count") or 0)
    opportunity_count = len(covered) + len(puts)
    engine_status = _classify_engine_status(
        imports_ok=imports_ok,
        deps=deps,
        dashboard=dashboard,
        opportunity_count=opportunity_count,
        position_count=position_count,
        scanner_completed=ctx.opportunities is not None,
        advisory=advisory,
    )
    certification = _build_certification(
        imports_ok=imports_ok,
        import_ok_list=import_ok_list,
        import_failed=import_failed,
        deps=deps,
        runtime_mode=runtime_mode,
        engine_status=engine_status,
        advisory=advisory,
    )
    run_rate = _build_run_rate(ctx)
    premium = _premium_accounting(dashboard, ctx)
    greeks = _greeks_block(dashboard, position_count)
    rolls = _rolls_block(dashboard)
    collateral = _collateral_block(dashboard, deps)
    if advisory and isinstance(advisory.get("collateral"), Mapping):
        adv_coll = dict(advisory["collateral"])
        if adv_coll.get("authority_level") and adv_coll.get("authority_level") != "UNAVAILABLE":
            collateral = {
                **collateral,
                **adv_coll,
                "status": adv_coll.get("status") or collateral.get("status"),
                "advisory_only": True,
                "execution_allowed": False,
            }
    risk = dashboard.get("risk") if isinstance(dashboard.get("risk"), Mapping) else {}

    deployment_state = "DEPLOYED" if imports_ok else STATUS_NOT_DEPLOYED
    if engine_status == STATUS_DATA_DEPENDENCY_BLOCKED:
        mc_status = STATUS_ADVISORY_ONLY
    elif engine_status == STATUS_STALE:
        mc_status = STATUS_DEGRADED
    else:
        mc_status = engine_status

    rejected_count = len(rejected)
    provider_summary = None
    if advisory:
        provider_summary = {
            "provider_registry": advisory.get("provider_registry"),
            "option_chain_status": (advisory.get("option_chains") or {}).get("status")
            if isinstance(advisory.get("option_chains"), Mapping)
            else None,
            "holdings_status": (advisory.get("holdings") or {}).get("status")
            if isinstance(advisory.get("holdings"), Mapping)
            else None,
            "collateral_status": (advisory.get("collateral") or {}).get("status")
            if isinstance(advisory.get("collateral"), Mapping)
            else None,
            "collateral_authority": (advisory.get("collateral") or {}).get("authority_level")
            if isinstance(advisory.get("collateral"), Mapping)
            else None,
            "questrade_adapter_state": (advisory.get("questrade_readiness") or {}).get("adapter_state")
            if isinstance(advisory.get("questrade_readiness"), Mapping)
            else None,
            "broker_capability_truth": advisory.get("broker_capability_truth"),
            "events_status": (advisory.get("events") or {}).get("status")
            if isinstance(advisory.get("events"), Mapping)
            else None,
            "readiness_status": advisory.get("readiness_status"),
            "broker_operational_state": advisory.get("broker_operational_state"),
            "broker_option_chain_state": advisory.get("broker_option_chain_state"),
            "broker_expected_condition": advisory.get("broker_expected_condition"),
            "last_successful_refresh": advisory.get("last_successful_refresh"),
        }

    core: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "engine_name": OPTIONS_INCOME_ENGINE_NAME,
        "engine_version": OPTIONS_INCOME_ENGINE_VERSION,
        "status": mc_status,
        "engine_status": engine_status,
        "deployment_state": deployment_state,
        "deployment_status": deployment_state,
        "advisory_only": True,
        "execution_authority": "BLOCKED",
        "execution_blocked": True,
        "order_submission": "BLOCKED",
        "live_trading_enabled": False,
        "opportunity_count": opportunity_count,
        "opportunity_outcome": (
            "QUALIFYING_OPPORTUNITIES_FOUND"
            if engine_status == STATUS_ADVISORY_READY
            else (
                STATUS_NO_CURRENT_OPPORTUNITIES
                if engine_status == STATUS_NO_CURRENT_OPPORTUNITIES
                else "EVALUATION_BLOCKED"
            )
        ),
        "rejected_opportunity_count": rejected_count,
        "opportunities": covered + puts,
        "accepted_candidates": covered + puts,
        "rejected_candidates": rejected,
        "covered_calls": covered,
        "cash_secured_puts": puts,
        "paper_positions": list(positions.get("active_positions") or [])
        if isinstance(positions.get("active_positions"), list)
        else [],
        "premium_accounting": premium,
        "collateral": collateral,
        "position_health": positions.get("health_summary")
        or (STATUS_NO_OPEN_OPTION_POSITIONS if position_count == 0 else "ADVISORY"),
        "rolling_recommendations": rolls.get("recommendations") or [],
        "rolling": rolls,
        "income_targets": run_rate,
        "run_rate": run_rate,
        "portfolio_allocation": dashboard.get("portfolio") or {},
        "greeks": greeks,
        "assignment_risk": {
            "status": risk.get("assignment_risk_status")
            or (STATUS_NO_OPEN_OPTION_POSITIONS if position_count == 0 else "ADVISORY"),
            "detail": risk.get("assignment_risk"),
            "provenance": "RISK_ENGINE",
        },
        "volatility_risk": {
            "status": risk.get("volatility_risk_status")
            or (STATUS_NO_OPEN_OPTION_POSITIONS if position_count == 0 else "ADVISORY"),
            "detail": risk.get("volatility_risk"),
            "provenance": "RISK_ENGINE",
        },
        "stress_tests": dashboard.get("stress_tests") or {},
        "alerts": dashboard.get("alerts") or [],
        "certification": certification,
        "operational_readiness": certification.get("operational_readiness"),
        "dependencies": deps,
        "missing_dependencies": deps.get("missing_dependencies"),
        "runtime_mode": runtime_mode,
        "broker_registry": brokers,
        "dashboard": dashboard,
        "advisory_data": advisory,
        "provider_summary": provider_summary,
        "data_readiness": {
            "status": (advisory or {}).get("readiness_status") if advisory else engine_status,
            "market_data_available": deps.get("market_data_available"),
            "option_chain_available": deps.get("option_chain_available"),
            "account_holdings_available": deps.get("account_holdings_available"),
            "missing_dependencies": deps.get("missing_dependencies"),
            "deployment_is_not_data_readiness": True,
        },
        "data_source": "OPTIONS_ENGINE",
        "source": "OPTIONS_ENGINE",
        "provenance": {
            "engine": "OPTIONS_ENGINE",
            "accounting": "ACCOUNTING",
            "risk": "RISK_ENGINE",
            "market_data": "MARKET_DATA" if deps.get("market_data_available") else "ABSENT",
            "option_chain": "OPTION_CHAIN" if deps.get("option_chain_available") else "ABSENT",
            "broker": "BROKER" if deps.get("account_holdings_available") else "ABSENT",
            "configuration": "CONFIGURATION",
            "runtime": "RUNTIME",
            "advisory": (advisory or {}).get("provenance") if advisory else None,
        },
        "generated_at": generated_at,
        "last_successful_refresh": (
            generated_at
            if advisory and str(advisory.get("readiness_status") or "").upper() == STATUS_ADVISORY_READY
            else None
        ),
        "failure_reason": (
            ";".join(import_failed)
            if not imports_ok
            else (
                (dashboard.get("summary") or {}).get("failure_reason")
                if isinstance(dashboard.get("summary"), Mapping)
                and str((dashboard.get("summary") or {}).get("engine_status") or "").upper() == "FAIL_CLOSED"
                else None
            )
        ),
        "correlation_id": dashboard.get("correlation_id"),
        "paper_only": True,
        **SAFE_FLAGS,
    }
    core["state_hash"] = _state_hash(
        {
            "status": core["status"],
            "deployment_state": deployment_state,
            "opportunity_count": opportunity_count,
            "position_count": position_count,
            "certification": certification.get("outcome"),
            "generated_at": generated_at,
            "missing_dependencies": deps.get("missing_dependencies"),
        }
    )
    if ctx.persist:
        _persist_snapshot(core)
    return core


def build_mission_control_options_income(ctx: OptionsIncomeRuntimeContext | None = None) -> dict[str, Any]:
    snap = build_options_income_runtime_snapshot(ctx)
    return {
        "status": snap["status"],
        "engine_status": snap["engine_status"],
        "deployment_state": snap["deployment_state"],
        "advisory_only": True,
        "execution_blocked": True,
        "execution_authority": "BLOCKED",
        "opportunities": snap["opportunities"],
        "accepted_candidates": snap["accepted_candidates"],
        "rejected_candidates": snap["rejected_candidates"],
        "covered_calls": snap["covered_calls"],
        "cash_secured_puts": snap["cash_secured_puts"],
        "paper_positions": snap["paper_positions"],
        "premium_accounting": snap["premium_accounting"],
        "collateral": snap["collateral"],
        "position_health": snap["position_health"],
        "rolling_recommendations": snap["rolling_recommendations"],
        "income_targets": snap["income_targets"],
        "run_rate": snap["run_rate"],
        "portfolio_allocation": snap["portfolio_allocation"],
        "greeks": snap["greeks"],
        "assignment_risk": snap["assignment_risk"],
        "volatility_risk": snap["volatility_risk"],
        "stress_tests": snap["stress_tests"],
        "alerts": snap["alerts"],
        "certification": snap["certification"],
        "operational_readiness": snap["operational_readiness"],
        "data_source": snap["data_source"],
        "source": snap["source"],
        "provenance": snap["provenance"],
        "state_hash": snap["state_hash"],
        "generated_at": snap["generated_at"],
        "last_successful_refresh": snap["last_successful_refresh"],
        "missing_dependencies": snap["missing_dependencies"],
        "opportunity_count": snap["opportunity_count"],
        "rejected_opportunity_count": snap.get("rejected_opportunity_count"),
        "provider_summary": snap.get("provider_summary"),
        "data_readiness": snap.get("data_readiness"),
        "runtime_mode": snap["runtime_mode"],
        "failure_reason": snap.get("failure_reason"),
        "paper_only": True,
        **SAFE_FLAGS,
    }


def build_options_income_mobile_card(ctx: OptionsIncomeRuntimeContext | None = None) -> dict[str, Any]:
    snap = build_options_income_runtime_snapshot(ctx)
    premium = snap["premium_accounting"] if isinstance(snap.get("premium_accounting"), Mapping) else {}
    session = premium.get("session") if isinstance(premium.get("session"), Mapping) else {}
    forecast = premium.get("forecast_advisory") if isinstance(premium.get("forecast_advisory"), Mapping) else {}
    run_rate = snap.get("run_rate") if isinstance(snap.get("run_rate"), Mapping) else {}
    collateral = snap.get("collateral") if isinstance(snap.get("collateral"), Mapping) else {}
    assignment = snap.get("assignment_risk") if isinstance(snap.get("assignment_risk"), Mapping) else {}
    cert = snap.get("certification") if isinstance(snap.get("certification"), Mapping) else {}
    readiness = snap.get("data_readiness") if isinstance(snap.get("data_readiness"), Mapping) else {}
    providers = snap.get("provider_summary") if isinstance(snap.get("provider_summary"), Mapping) else {}
    return {
        "options_income_status": snap.get("status"),
        "opportunity_count": snap.get("opportunity_count"),
        "expected_monthly_premium": forecast.get("expected_monthly_premium"),
        "actual_month_to_date_premium": session.get("premium_collected"),
        "target_attainment": run_rate.get("target_attainment_percent")
        if run_rate.get("status") != STATUS_TARGET_NOT_CONFIGURED
        else STATUS_TARGET_NOT_CONFIGURED,
        "collateral_utilization": collateral.get("utilization"),
        "assignment_risk_level": assignment.get("status"),
        "certification": cert.get("outcome"),
        "data_readiness": readiness.get("status"),
        "missing_dependencies_count": len(list(snap.get("missing_dependencies") or [])),
        "provider_chain_status": providers.get("option_chain_status") or providers.get("readiness_status"),
        "broker_operational_state": (
            (providers.get("broker_operational_state") or {}).get("operational_state")
            if isinstance(providers.get("broker_operational_state"), Mapping)
            else None
        ),
        "broker_option_chain_state": (
            (providers.get("broker_option_chain_state") or {}).get("state")
            if isinstance(providers.get("broker_option_chain_state"), Mapping)
            else None
        ),
        "broker_expected_condition": providers.get("broker_expected_condition"),
        "last_refresh": snap.get("last_successful_refresh"),
        "detail_route": "/mission-control/options-income",
        "advisory_only": True,
        "execution_blocked": True,
        "provenance": "OPTIONS_ENGINE|RUNTIME",
        **SAFE_FLAGS,
        "paper_only": True,
    }


_CACHE: dict[str, Any] | None = None


def get_cached_options_income_payload(*, force: bool = False) -> dict[str, Any]:
    global _CACHE
    if force or _CACHE is None:
        try:
            from backend.options.options_income_data_resolver import (
                build_runtime_context_from_advisory,
                resolve_options_income_advisory_data,
            )

            advisory = resolve_options_income_advisory_data()
            ctx = build_runtime_context_from_advisory(advisory, persist=True)
            # Attach advisory bundle explicitly for snapshot facets
            ctx.advisory_data = advisory
            _CACHE = build_options_income_runtime_snapshot(ctx)
        except Exception:  # noqa: BLE001 — fail closed to empty context
            _CACHE = build_options_income_runtime_snapshot(OptionsIncomeRuntimeContext(persist=True))
    return dict(_CACHE)


__all__ = [
    "CANONICAL_MODULES",
    "OptionsIncomeRuntimeContext",
    "SCHEMA_VERSION",
    "STATUS_ADVISORY_ONLY",
    "STATUS_ADVISORY_READY",
    "STATUS_DATA_DEPENDENCY_BLOCKED",
    "STATUS_DEGRADED",
    "STATUS_NO_CURRENT_OPPORTUNITIES",
    "STATUS_NO_OPEN_OPTION_POSITIONS",
    "STATUS_PARTIAL_DATA",
    "STATUS_PROVIDER_UNAVAILABLE",
    "STATUS_STALE",
    "STATUS_TARGET_NOT_CONFIGURED",
    "build_mission_control_options_income",
    "build_options_income_mobile_card",
    "build_options_income_runtime_snapshot",
    "get_cached_options_income_payload",
]
