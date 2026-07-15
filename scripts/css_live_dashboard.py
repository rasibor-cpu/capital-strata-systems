from __future__ import annotations

# === R15B MODE-AWARE EXIT PROFILE ===

R15B_EXIT_PROFILE = {
    "SAFE":        {"tp": 0.010, "sl": -0.006},
    "CONSERVATIVE":{"tp": 0.012, "sl": -0.008},
    "BALANCED":    {"tp": 0.015, "sl": -0.010},
    "AGGRESSIVE":  {"tp": 0.020, "sl": -0.012},
    "EXPANSION":   {"tp": 0.025, "sl": -0.015},
}


def r15b_profile():
    return R15B_EXIT_PROFILE.get(str(ENGINE_MODE).upper(), R15B_EXIT_PROFILE["BALANCED"])



# === R15A EXIT INTELLIGENCE ENGINE ===

def evaluate_exit_signal(position: dict) -> str:
    entry = float(position.get("entry_price", 0.0))
    current = float(position.get("current_price", entry))

    if entry == 0:
        return "HOLD"

    pnl_pct = (current - entry) / entry

    if pnl_pct >= 0.015:
        return "TAKE_PROFIT"

    if pnl_pct <= -0.010:
        return "STOP_LOSS"

    if pnl_pct >= 0.010:
        return "RUNNER"

    return "HOLD"



# === R14F PRE-POSITION PROFITABILITY GATE ===
def _legacy_css_profitability_threshold(mode: str) -> float:
    return {
        "SAFE": 17.5,
        "CONSERVATIVE": 16.5,
        "BALANCED": 15.8,
        "AGGRESSIVE": 15.0,
        "EXPANSION": 14.2,
    }.get(str(mode).upper(), 15.8)


def _legacy_css_profitability_allows(symbol: str, asset_class: str, sig: float, prob: float) -> tuple[bool, float, float]:
    """
    Uses existing dashboard signal score and probability before creating a position.
    Score remains compatible with current sig scale.
    """
    signal_score = float(sig or 0.0)
    probability = float(prob or 0.0)
    threshold = _legacy_css_profitability_threshold(ENGINE_MODE)

    # R14F asset-aware tuning:
    # Preserve the base mode threshold for FUTURES/OPTIONS.
    # Slightly relax FX/CRYPTO so near-miss opportunities can enter controlled testing.
    asset_key = str(asset_class or "").upper()
    if asset_key == "CRYPTO":
        threshold -= 0.30
    elif asset_key == "FX":
        threshold -= 0.90

    composite = signal_score + (probability * 5.0)

    if composite < threshold:
        print(
            f"[R14F BLOCK] {asset_class} {symbol} "
            f"composite={composite:.2f} threshold={threshold:.2f} "
            f"sig={signal_score:.2f} prob={probability:.2f}"
        )
        return False, composite, threshold

    print(
        f"[R14F PASS] {asset_class} {symbol} "
        f"composite={composite:.2f} threshold={threshold:.2f} "
        f"sig={signal_score:.2f} prob={probability:.2f}"
    )
    return True, composite, threshold



# === R13C GLOBAL MODE DOMINANCE ===
def _legacy_enforce_mode_dominance():
    global SELECTED_BROKER_MODE

    if str(GLOBAL_BROKER_MODE).lower() == "live":
        if str(SELECTED_BROKER_MODE).lower() != "live":
            print("[MODE CORRECTION] Forcing broker mode to LIVE due to global mode")
            SELECTED_BROKER_MODE = "live"



# === R13 EXECUTION BOUNDARY ENFORCEMENT ===
def _legacy_enforce_execution_boundary():
    mode = str(SELECTED_BROKER_MODE).lower()

    if mode == "live":
        # Live mode must not use simulated paths
        if capital_governor.capital_source_label().upper() == "SIMULATED":
            print("[BOUNDARY VIOLATION] Live mode cannot use simulated capital")
            if BROKER_EXECUTION_ARMED:
                import sys
                sys.exit(1)
            print("[LIVE READ-ONLY CONTINUE] Broker execution disabled; simulated capital cannot execute.")

    elif mode == "paper":
        # Paper mode must not attempt live execution
        if "LIVE" in str(globals()):
            pass  # safeguard placeholder

    else:
        print(f"[UNKNOWN MODE] {mode}")
        import sys
        sys.exit(1)



# === R12 OPTION IDENTITY FORMATTER ===
def format_option_symbol(symbol: str) -> str:
    """
    Ensure option symbols are fully qualified
    """
    if "-" not in symbol:
        return symbol

    parts = symbol.split("-")

    # Already fully qualified
    if len(parts) == 3:
        return symbol

    # Convert stub to default strike
    if len(parts) == 2:
        underlying, opt_type = parts
        default_strike = {
            "AAPL": "175",
            "SPY": "500",
            "QQQ": "400",
        }.get(underlying, "100")

        return f"{underlying}-{opt_type}-{default_strike}"

    return symbol



# === R11 BROKER URL ISOLATION ===
def get_active_broker_url():
    endpoint = endpoint_for_broker(SELECTED_BROKER, os.environ)
    if endpoint == "NOT_AVAILABLE":
        return "NO_BROKER_SELECTED"
    return endpoint

import os
if os.getenv("CSS_AUTOMATED_INPUT") == "1":
    import builtins
    import sys
    inputs_seq = ["2", "LIVE", "2", "2", "LIVE", "1", "3", "1", "Y", "q"]
    inputs_iter = iter(inputs_seq)
    def automated_input(*args, **kwargs):
        val = next(inputs_iter, "q")
        prompt = args[0] if args else ""
        sys.stderr.write(f"[AUTOMATED INPUT] Prompt: {prompt.replace(chr(10), ' ').strip()} -> Yielding: {val}\n")
        sys.stderr.flush()
        return val
    builtins.input = automated_input
print("RUNNING FILE:", os.path.abspath(__file__))
import contextlib
import hashlib
import getpass
import io
import json
import os
import random
import socket
import sys
import time
# PCNRASS: orchestrator bridge import deferred until after PROJECT_ROOT bootstrap
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from backend.runtime.live_environment_loader import (
    load_css_runtime_environment,
    paper_only_coinbase_test_order_usd,
)
from backend.runtime.broker_startup_selection import (
    build_startup_broker_selection,
    persist_broker_selection,
    startup_broker_from_choice,
    startup_broker_mode_from_choice,
)
from backend.runtime.broker_parity_validator import broker_parity_payload
from backend.runtime.broker_operational_status import endpoint_for_broker
from backend.runtime.broker_credential_diagnostics import diagnostics_payload
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.canonical_broker_state_adapter import adapt_canonical_state_to_legacy_broker_payload
from backend.runtime.coinbase_readiness import (
    coinbase_credential_diagnostics,
    coinbase_live_limit_reconciliation,
    confirm_coinbase_live_read_only,
    evaluate_coinbase_live_read_only,
    merge_readiness_into_broker_state,
    selection_with_coinbase_readiness,
)
from backend.runtime.coinbase_live_read_only_operational_validation import (
    validate_coinbase_live_read_only_operational,
)
from backend.runtime.oanda_readiness import (
    oanda_credential_diagnostics,
    oanda_live_limit_reconciliation,
    confirm_oanda_live_read_only,
    evaluate_oanda_live_read_only,
    merge_readiness_into_broker_state as merge_oanda_readiness_into_broker_state,
    selection_with_oanda_readiness,
)
from backend.runtime.oanda_live_read_only_operational_validation import (
    validate_oanda_live_read_only_operational,
)
from backend.runtime.live_operator_wizard import (
    StartupWizardState,
    broker_validation_display,
    build_startup_summary,
    choose_broker,
    choose_broker_execution_arming,
    choose_broker_mode,
    choose_global_mode,
    mark_authenticated,
    paper_live_environment_conflict,
    set_cycle_mode,
    set_engine_mode,
    startup_summary_confirmation,
)
from backend.runtime.live_micro_pilot_governor import live_micro_pilot_status
from backend.runtime.live_readiness_state_machine import publish_live_readiness_state
from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter
from backend.runtime.startup_summary import (
    build_live_startup_summary,
    format_live_startup_summary,
    publish_startup_diagnostics,
)
from backend.runtime.startup_state_machine import (
    StartupMachineConfig,
    default_stdin_flush,
    run_startup_state_machine,
)


def _utc_now_compat() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_iso_z() -> str:
    return _utc_now_compat().isoformat() + "Z"


OPTION_GREEK_FIELDS = ("delta", "gamma", "theta", "vega", "rho")
VALID_GREEKS_SOURCES = {
    "BROKER",
    "MARKET_DATA",
    "BLACK_SCHOLES",
    "PAPER_MODEL_FALLBACK",
    "UNAVAILABLE",
}
PORTFOLIO_GREEK_FIELDS = {
    "delta": "net_delta",
    "gamma": "net_gamma",
    "theta": "net_theta",
    "vega": "net_vega",
    "rho": "net_rho",
}
SUPPORTED_OPTIONS_STRATEGIES = {"LONG_CALL", "LONG_PUT", "UNKNOWN_OPTIONS_STRATEGY"}
FUTURE_OPTIONS_STRATEGY_PLACEHOLDERS = {
    "COVERED_CALL",
    "CASH_SECURED_PUT",
    "BULL_CALL_SPREAD",
    "BEAR_CALL_SPREAD",
    "BULL_PUT_SPREAD",
    "BEAR_PUT_SPREAD",
    "IRON_CONDOR",
    "IRON_BUTTERFLY",
    "STRADDLE",
    "STRANGLE",
    "CALENDAR_SPREAD",
    "DIAGONAL_SPREAD",
}
OPTION_STRATEGY_FIELDS = ("options_strategy", "strategy_family", "strategy_confidence")


def default_option_greeks() -> dict[str, Any]:
    return {
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
        "greeks_source": "UNAVAILABLE",
        "greeks_status": "UNAVAILABLE",
        "greeks_reason": "NO_CANONICAL_GREEKS",
    }


def normalize_option_greeks(greeks: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = greeks or {}
    source = str(raw.get("greeks_source", "UNAVAILABLE") or "UNAVAILABLE").upper()
    if source not in VALID_GREEKS_SOURCES:
        source = "UNAVAILABLE"

    normalized = default_option_greeks()
    normalized["greeks_source"] = source
    normalized["greeks_status"] = str(
        raw.get("greeks_status", normalized["greeks_status"]) or normalized["greeks_status"]
    ).upper()
    normalized["greeks_reason"] = str(
        raw.get("greeks_reason", normalized["greeks_reason"]) or normalized["greeks_reason"]
    ).upper()

    numeric_count = 0
    for field in OPTION_GREEK_FIELDS:
        value = raw.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        normalized[field] = float(value)
        numeric_count += 1

    if numeric_count > 0:
        if source == "UNAVAILABLE":
            normalized["greeks_status"] = "PARTIAL"
            normalized["greeks_reason"] = "GREEKS_VALUES_PRESENT_SOURCE_UNAVAILABLE"
        else:
            normalized["greeks_status"] = "RESOLVED"
            normalized["greeks_reason"] = "CANONICAL_GREEKS_AVAILABLE"
    return normalized


def attach_default_greeks_to_option_position(position: dict[str, Any]) -> dict[str, Any]:
    if str(position.get("asset_class", "")).upper() != "OPTIONS":
        return position

    normalized = normalize_option_greeks(position)
    if normalized.get("greeks_status") != "RESOLVED":
        symbol = str(position.get("symbol", "") or "").strip().upper()
        parts = symbol.split("-")
        option_type = parts[1] if len(parts) >= 2 else ""
        strike_value = None
        if len(parts) >= 3:
            try:
                strike_value = float(parts[2])
            except Exception:
                strike_value = None

        broker_mode = str(position.get("broker_mode", "paper") or "paper").strip().lower()
        is_paper_mode = broker_mode != "live"
        if option_type in {"C", "P"} and is_paper_mode:
            try:
                spot = float(
                    position.get("mark_price")
                    or position.get("current_price")
                    or position.get("entry_price")
                    or strike_value
                    or 100.0
                )
            except Exception:
                spot = float(strike_value or 100.0)

            if strike_value is not None and strike_value > 0:
                moneyness = (spot - strike_value) / strike_value
            else:
                moneyness = 0.0

            bounded = max(-1.0, min(1.0, moneyness))
            call_delta = max(0.05, min(0.95, 0.50 + 0.35 * bounded))
            if option_type == "C":
                delta = call_delta
                rho = max(0.001, 0.010 + 0.005 * bounded)
            else:
                delta = call_delta - 1.0
                rho = min(-0.001, -0.010 + 0.005 * bounded)

            gamma = max(0.005, 0.025 - 0.015 * abs(bounded))
            theta = -max(0.002, 0.010 + 0.012 * abs(bounded))
            vega = max(0.010, 0.090 - 0.050 * abs(bounded))

            normalized.update(
                {
                    "delta": round(delta, 6),
                    "gamma": round(gamma, 6),
                    "theta": round(theta, 6),
                    "vega": round(vega, 6),
                    "rho": round(rho, 6),
                    "greeks_source": "PAPER_MODEL_FALLBACK",
                    "greeks_status": "MODEL_FALLBACK",
                    "greeks_reason": "PAPER_OPTION_SYNTHETIC_MODEL",
                }
            )
        else:
            normalized["greeks_source"] = "UNAVAILABLE"
            normalized["greeks_status"] = "UNAVAILABLE"
            normalized["greeks_reason"] = "NON_CANONICAL_OPTION_SYMBOL"

    position.update(normalized)
    return position


def parse_option_symbol(symbol: str) -> dict[str, Any]:
    parts = str(symbol or "").strip().upper().split("-")
    if len(parts) < 2:
        return {"underlying": None, "option_type": None, "strike": None}

    option_type = parts[1]
    if option_type not in {"C", "P"}:
        option_type = None

    return {
        "underlying": parts[0] or None,
        "option_type": option_type,
        "strike": parts[2] if len(parts) >= 3 and parts[2] else None,
    }


def classify_option_strategy(position_or_symbol: dict[str, Any] | str) -> dict[str, str]:
    symbol = (
        position_or_symbol.get("symbol", "")
        if isinstance(position_or_symbol, dict)
        else position_or_symbol
    )
    parsed = parse_option_symbol(str(symbol))

    if parsed["option_type"] == "C":
        return {
            "options_strategy": "LONG_CALL",
            "strategy_family": "SINGLE_LEG",
            "strategy_confidence": "HIGH",
        }
    if parsed["option_type"] == "P":
        return {
            "options_strategy": "LONG_PUT",
            "strategy_family": "SINGLE_LEG",
            "strategy_confidence": "HIGH",
        }

    return {
        "options_strategy": "UNKNOWN_OPTIONS_STRATEGY",
        "strategy_family": "UNKNOWN",
        "strategy_confidence": "LOW",
    }


def attach_option_strategy_to_position(position: dict[str, Any]) -> dict[str, Any]:
    if str(position.get("asset_class", "")).upper() != "OPTIONS":
        return position

    position.update(classify_option_strategy(position))
    return position


def portfolio_greeks_from_positions(positions: list[dict[str, Any]] | None) -> dict[str, Any]:
    totals = {field: 0.0 for field in OPTION_GREEK_FIELDS}
    has_numeric = {field: False for field in OPTION_GREEK_FIELDS}
    contributing_sources: set[str] = set()

    for position in positions or []:
        if str(position.get("asset_class", "")).upper() != "OPTIONS":
            continue
        if position.get("forced_exit"):
            continue

        source = str(position.get("greeks_source", "UNAVAILABLE") or "UNAVAILABLE").upper()
        if source not in VALID_GREEKS_SOURCES:
            source = "UNAVAILABLE"

        position_contributed = False
        for field in OPTION_GREEK_FIELDS:
            value = position.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue

            totals[field] += float(value)
            has_numeric[field] = True
            position_contributed = True

        if position_contributed:
            contributing_sources.add(source)

    portfolio = {
        net_field: (totals[field] if has_numeric[field] else None)
        for field, net_field in PORTFOLIO_GREEK_FIELDS.items()
    }

    if not any(has_numeric.values()):
        portfolio["greeks_source"] = "UNAVAILABLE"
        portfolio["greeks_status"] = "UNAVAILABLE"
        portfolio["greeks_reason"] = "NO_OPTION_GREEKS_AVAILABLE"
    elif len(contributing_sources) > 1:
        portfolio["greeks_source"] = "MIXED"
        portfolio["greeks_status"] = "PARTIAL"
        portfolio["greeks_reason"] = "MULTI_SOURCE_AGGREGATION"
    else:
        portfolio["greeks_source"] = next(iter(contributing_sources), "UNAVAILABLE")
        if portfolio["greeks_source"] == "UNAVAILABLE":
            portfolio["greeks_status"] = "PARTIAL"
            portfolio["greeks_reason"] = "NUMERIC_GREEKS_SOURCE_UNAVAILABLE"
        else:
            portfolio["greeks_status"] = "RESOLVED"
            portfolio["greeks_reason"] = "KNOWN_OPTION_GREEKS_AGGREGATED"

    return portfolio


def format_greeks_dashboard_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    text = str(value).strip()
    return text if text else "N/A"


def option_position_greeks_dashboard_lines(positions: list[dict[str, Any]] | None) -> list[str]:
    lines = ["=== OPTIONS POSITION GREEKS ==="]
    options_positions = [
        position
        for position in positions or []
        if str(position.get("asset_class", "")).upper() == "OPTIONS"
        and not position.get("forced_exit")
    ]

    if not options_positions:
        lines.append("No open OPTIONS positions.")
        lines.append("=== END OPTIONS POSITION GREEKS ===")
        return lines

    for position in options_positions:
        source = str(position.get("greeks_source", "UNAVAILABLE") or "UNAVAILABLE").upper()
        if source not in VALID_GREEKS_SOURCES:
            source = "UNAVAILABLE"
        status = str(position.get("greeks_status", "UNAVAILABLE") or "UNAVAILABLE").upper()
        reason = str(position.get("greeks_reason", "NONE") or "NONE").upper()

        lines.append(
            f"{position.get('position_id', 'UNKNOWN')} {position.get('symbol', 'UNKNOWN')} | "
            f"Delta {format_greeks_dashboard_value(position.get('delta'))} | "
            f"Gamma {format_greeks_dashboard_value(position.get('gamma'))} | "
            f"Theta {format_greeks_dashboard_value(position.get('theta'))} | "
            f"Vega {format_greeks_dashboard_value(position.get('vega'))} | "
            f"Rho {format_greeks_dashboard_value(position.get('rho'))} | "
            f"Greeks Source {source} | "
            f"Greeks Status {status} | "
            f"Greeks Reason {reason}"
        )

    lines.append("=== END OPTIONS POSITION GREEKS ===")
    return lines


def portfolio_greeks_dashboard_lines(positions: list[dict[str, Any]] | None) -> list[str]:
    portfolio = portfolio_greeks_from_positions(positions)
    source = str(portfolio.get("greeks_source", "UNAVAILABLE") or "UNAVAILABLE").upper()
    status = str(portfolio.get("greeks_status", "UNAVAILABLE") or "UNAVAILABLE").upper()
    reason = str(portfolio.get("greeks_reason", "NONE") or "NONE").upper()

    return [
        "=== PORTFOLIO GREEKS ===",
        (
            f"Net Delta {format_greeks_dashboard_value(portfolio.get('net_delta'))} | "
            f"Net Gamma {format_greeks_dashboard_value(portfolio.get('net_gamma'))} | "
            f"Net Theta {format_greeks_dashboard_value(portfolio.get('net_theta'))} | "
            f"Net Vega {format_greeks_dashboard_value(portfolio.get('net_vega'))} | "
            f"Net Rho {format_greeks_dashboard_value(portfolio.get('net_rho'))} | "
            f"Greeks Source {source} | "
            f"Greeks Status {status} | "
            f"Greeks Reason {reason}"
        ),
        "=== END PORTFOLIO GREEKS ===",
    ]


def _format_margin_dashboard_value(value: Any, suffix: str = "") -> str:
    try:
        return f"{float(value):.2f}{suffix}"
    except Exception:
        return f"UNKNOWN{suffix}"


def _margin_dashboard_mode_is_live(broker_mode: str) -> bool:
    return str(broker_mode or "").strip().lower() == "live"


def _margin_dashboard_adapter_for_context(
    selected_broker: str,
    broker_mode: str,
):
    from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter
    from engine.risk.oanda_margin_adapter import OandaMarginAdapter

    broker = str(selected_broker or "NONE").strip().upper()
    mode = "LIVE" if _margin_dashboard_mode_is_live(broker_mode) else "SIMULATED"

    if broker == "OANDA":
        return OandaMarginAdapter(mode=mode), "OANDA"
    if broker == "COINBASE":
        return CoinbaseMarginAdapter(mode=mode), "COINBASE"

    return CoinbaseMarginAdapter(mode="SIMULATED"), broker or "NONE"


def margin_dashboard_lines(
    selected_broker: str | None = None,
    selected_broker_mode: str | None = None,
) -> list[str]:
    try:
        from engine.risk.margin_engine import MarginEngine
        from engine.risk.margin_trade_gate import MarginTradeGate

        broker = str(
            selected_broker
            if selected_broker is not None
            else globals().get("SELECTED_BROKER", "NONE")
        ).strip().upper()
        broker_mode = str(
            selected_broker_mode
            if selected_broker_mode is not None
            else globals().get("SELECTED_BROKER_MODE", "paper")
        ).strip()

        adapter, display_broker = _margin_dashboard_adapter_for_context(
            broker,
            broker_mode,
        )
        broker_snapshot = adapter.get_margin_snapshot()
        canonical_display_state = {}
        if isinstance(globals().get("COINBASE_READ_ONLY_STATUS"), dict):
            canonical_display_state = COINBASE_READ_ONLY_STATUS.get("canonical_broker_runtime_state", {}) or {}
        canonical_provenance = canonical_display_state.get("status_provenance", {}) if isinstance(canonical_display_state, dict) else {}
        canonical_balance_status = str(canonical_display_state.get("balance_status", "UNKNOWN") if isinstance(canonical_display_state, dict) else "UNKNOWN").upper()
        canonical_margin_provenance = str(canonical_provenance.get("margin", "UNKNOWN") if isinstance(canonical_provenance, dict) else "UNKNOWN").upper()
        margin_source_display = str(getattr(broker_snapshot, "margin_source", "UNKNOWN") or "UNKNOWN").upper()
        if _margin_dashboard_mode_is_live(broker_mode) and margin_source_display == "SIMULATED":
            if str(getattr(broker_snapshot, "account_id", "") or "").startswith("SIMULATED"):
                margin_source_display = "READ_ONLY_PENDING_ACCOUNT"
            else:
                margin_source_display = "BROKER_UNAVAILABLE"
        required_margin_value = broker_snapshot.required_margin
        available_margin_value = broker_snapshot.available_margin
        free_margin_value = broker_snapshot.free_margin
        if (
            _margin_dashboard_mode_is_live(broker_mode)
            and canonical_balance_status != "PASS"
            and canonical_margin_provenance not in {"CACHE", "HISTORICAL"}
        ):
            margin_source_display = "UNAVAILABLE"
            required_margin_value = 0.0
            available_margin_value = 0.0
            free_margin_value = 0.0
        margin_snapshot = MarginEngine().calculate(
            required_margin=required_margin_value,
            available_margin=available_margin_value,
            margin_source=margin_source_display,
        )
        gate_decision = MarginTradeGate().evaluate(
            margin_snapshot,
            broker_mode=broker_mode,
        )

        return [
            "=== MARGIN DASHBOARD ===",
            f"Margin Source: {margin_source_display}",
            f"Margin Provenance: {canonical_margin_provenance}",
            f"Canonical State Hash: {canonical_display_state.get('state_hash', 'UNKNOWN') if isinstance(canonical_display_state, dict) else 'UNKNOWN'}",
            f"Broker: {display_broker}",
            f"Broker Mode: {broker_mode.upper() if broker_mode else 'UNKNOWN'}",
            f"Required Margin: {_format_margin_dashboard_value(required_margin_value)}",
            f"Available Margin: {_format_margin_dashboard_value(available_margin_value)}",
            f"Free Margin: {_format_margin_dashboard_value(free_margin_value)}",
            f"Utilization %: {_format_margin_dashboard_value(margin_snapshot.margin_utilization_pct, '%')}",
            f"Margin State: {str(margin_snapshot.margin_state.value)}",
            f"Escalation State: {str(margin_snapshot.escalation_state.value)}",
            f"Trade Gate Decision: {gate_decision.decision}",
            f"Trade Gate Allowed: {str(gate_decision.allowed).upper()}",
            f"Trade Gate Reason: {gate_decision.reason}",
            "=== END MARGIN DASHBOARD ===",
        ]
    except Exception as exc:
        return [
            "=== MARGIN DASHBOARD ===",
            "Margin Status: UNAVAILABLE",
            f"Reason: {str(exc)[:120]}",
            "=== END MARGIN DASHBOARD ===",
        ]


def _format_canonical_pnl_dashboard_value(value: Any) -> str:
    try:
        return f"{float(value):+.4f}"
    except Exception:
        return "UNKNOWN"


def canonical_pnl_dashboard_lines(
    *,
    ledger_store: Any | None = None,
    dashboard_summary: dict[str, Any] | None = None,
    canonical_summary: dict[str, Any] | None = None,
    starting_equity: Any = 0,
    peak_equity: Any | None = None,
    max_drawdown: Any | None = None,
    asset_class_by_symbol: dict[str, str] | None = None,
    company_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    user_id: str | None = None,
) -> list[str]:
    """
    CANONICAL_PNL_DIAGNOSTIC: display-only comparison helper.

    This helper is intentionally not wired into live dashboard rendering yet.
    Existing MTM/accounting dashboard PnL remains the active dashboard
    authority while canonical ledger-backed PnL parity is proven.
    """
    try:
        from engine.ledger import CANONICAL_PNL_SOURCE

        if canonical_summary is None:
            if ledger_store is None:
                return [
                    "=== CANONICAL PNL DIAGNOSTIC ===",
                    "Canonical PnL Status: UNAVAILABLE",
                    "Reason: canonical ledger snapshot unavailable",
                    "=== END CANONICAL PNL DIAGNOSTIC ===",
                ]

            from engine.ledger.pnl_snapshot_adapter import (
                build_pnl_snapshot_contract,
            )

            canonical_summary = build_pnl_snapshot_contract(
                ledger_store,
                starting_equity=starting_equity,
                peak_equity=peak_equity,
                max_drawdown=max_drawdown,
                asset_class_by_symbol=asset_class_by_symbol,
                company_id=company_id,
                branch_id=branch_id,
                department_id=department_id,
                user_id=user_id,
            ).to_runtime_dict()

        lines = [
            "=== CANONICAL PNL DIAGNOSTIC ===",
            "Canonical PnL Status: AVAILABLE",
            f"Source: {canonical_summary.get('source', CANONICAL_PNL_SOURCE)}",
            (
                "Canonical Realized PnL: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('realized_pnl'))}"
            ),
            (
                "Canonical Unrealized PnL: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('unrealized_pnl'))}"
            ),
            (
                "Canonical Net PnL: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('net_pnl'))}"
            ),
            (
                "Canonical Equity: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('equity'))}"
            ),
            (
                "Canonical Peak Equity: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('peak_equity'))}"
            ),
            (
                "Canonical Current Drawdown: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('current_drawdown'))}"
            ),
            (
                "Canonical Max Drawdown: "
                f"{_format_canonical_pnl_dashboard_value(canonical_summary.get('max_drawdown'))}"
            ),
            f"Canonical Open Positions: {int(canonical_summary.get('open_positions', 0) or 0)}",
            f"Canonical Closed Positions: {int(canonical_summary.get('closed_positions', 0) or 0)}",
        ]

        if dashboard_summary is not None:
            from dashboard.runtime.summary_builders.pnl_parity_check import (
                compare_pnl_summary_parity,
            )

            parity = compare_pnl_summary_parity(
                dashboard_summary,
                canonical_summary,
            )
            lines.extend(
                [
                    f"PnL Parity: {'MATCH' if parity['matches'] else 'MISMATCH'}",
                    f"Realized Diff: {_format_canonical_pnl_dashboard_value(parity['field_diffs'].get('realized_pnl'))}",
                    f"Unrealized Diff: {_format_canonical_pnl_dashboard_value(parity['field_diffs'].get('unrealized_pnl'))}",
                    f"Net Diff: {_format_canonical_pnl_dashboard_value(parity['field_diffs'].get('net_pnl'))}",
                ]
            )

        lines.append("=== END CANONICAL PNL DIAGNOSTIC ===")
        return lines
    except Exception as exc:
        return [
            "=== CANONICAL PNL DIAGNOSTIC ===",
            "Canonical PnL Status: UNAVAILABLE",
            f"Reason: {str(exc)[:120]}",
            "=== END CANONICAL PNL DIAGNOSTIC ===",
        ]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CSS_ENVIRONMENT_LOAD_TRACE = load_css_runtime_environment(PROJECT_ROOT)

# === PCNRASS PHASE 2 REAL MARKET PRICE FEED ===
from backend.data.price_feed import get_price_feed
price_feed = get_price_feed()

# === PCNRASS SAFE PNL IMPORT COMPATIBILITY ===
# Some CSS branches used backend.app.pnl.pnl_engine.
# This repo currently uses backend.app.accounting.pnl_engine.
# Keep old dashboard behavior by providing a local Portfolio/Position compatibility layer
# if the old module path is unavailable.
# --- CSS Runtime Alert Service (Phase 113Y-2) ---
css_runtime_alert_service = None
css_supervisor = None
try:
    from backend.monitoring.css_alert_service import CSSAlertService
    from backend.monitoring.css_alert_models import AlertSeverity
    from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
    css_runtime_alert_service = CSSAlertService()
    css_supervisor = CSSRuntimeSupervisor(alert_service=css_runtime_alert_service)
except Exception as alert_init_e:
    print(f"[ALERT SERVICE INIT WARN] {alert_init_e}")

try:
    from backend.runtime.runtime_artifact_publisher import RuntimeArtifactPublisher
except Exception:
    RuntimeArtifactPublisher = None

def _safe_emit_alert(method_name: str, *args, **kwargs):
    if not css_runtime_alert_service:
        return
    try:
        method = getattr(css_runtime_alert_service, method_name, None)
        if method:
            meta = kwargs.get("metadata", {})
            if "key" in meta: del meta["key"]
            meta.update({
                "component": "css_live_dashboard",
                "engine_mode": str(ENGINE_MODE),
                "broker_mode": str(SELECTED_BROKER_MODE)
            })
            kwargs["metadata"] = meta
            if "source" not in kwargs:
                kwargs["source"] = "css_live_dashboard"
            method(*args, **kwargs)
    except Exception as e:
        print(f"[ALERT EMISSION WARN] {e}")

# === PCNRASS SAFE PNL IMPORT COMPATIBILITY ===
try:
    from backend.app.pnl.pnl_engine import Portfolio, Position  # legacy path
except ModuleNotFoundError:
    from dataclasses import dataclass

    @dataclass
    class Position:
        symbol: str
        asset_class: str = "UNKNOWN"
        side: str = "LONG"
        quantity: float = 1.0
        entry_price: float = 0.0
        current_price: float = 0.0

    class Portfolio:
        def __init__(self, starting_balance: float = 0.0, current_balance: float | None = None):
            self.starting_balance = float(starting_balance or 0.0)
            self.current_balance = float(current_balance if current_balance is not None else self.starting_balance)
            self.realized_pnl = 0.0
            self.positions: dict[str, Position] = {}

        def add_position(self, position: Position) -> None:
            self.positions[position.symbol] = position

        def update_market_price(self, symbol: str, current_price: float) -> None:
            pos = self.positions.get(symbol)
            if pos is not None:
                pos.current_price = float(current_price)

        def close_position(self, symbol: str, exit_price: float) -> float:
            pos = self.positions.pop(symbol, None)
            if pos is None:
                return 0.0

            side = str(pos.side or "LONG").upper()
            direction = 1.0 if side != "SHORT" else -1.0
            pnl = (float(exit_price) - float(pos.entry_price)) * float(pos.quantity) * direction
            self.realized_pnl += pnl
            self.current_balance += pnl
            return pnl

        def compute_unrealized_pnl(self) -> float:
            total = 0.0
            for pos in self.positions.values():
                side = str(pos.side or "LONG").upper()
                direction = 1.0 if side != "SHORT" else -1.0
                total += (float(pos.current_price) - float(pos.entry_price)) * float(pos.quantity) * direction
            return round(total, 6)

        def equity(self) -> float:
            return round(float(self.current_balance) + float(self.compute_unrealized_pnl()), 6)


# === NEW PNL SYSTEM IMPORTS (PCNRASS SAFE ADDITION) ===
from backend.app.accounting.pnl_engine import (
    compute_portfolio_snapshot,
    Position as NewPosition,
    InstrumentSpec,
    ExecutionCost,
)
from backend.runtime.capital_state import canonical_drawdown_display
from engine.performance.pnl_tracker import PnLTracker

try:
    from engine.information.alerts import get_alert_service, AlertEventType
except ModuleNotFoundError:
    class _FallbackAlertEventType:
        PROFIT_TARGET_REACHED = "PROFIT_TARGET_REACHED"
        DRAWDOWN_BREACHED = "DRAWDOWN_BREACHED"
        LIVE_MODE_ARMED = "LIVE_MODE_ARMED"
        BROKER_CONNECTION_FAILURE = "BROKER_CONNECTION_FAILURE"
        TRADE_BLOCKED = "TRADE_BLOCKED"
        EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
        INFO = "INFO"

    class _FallbackAlertService:
        def dispatch_alert(self, *args, **kwargs): pass

    def get_alert_service():
        return _FallbackAlertService()

    AlertEventType = _FallbackAlertEventType


try:
    from backend.runtime.runtime_supervisor import RuntimeSupervisor
    runtime_supervisor = RuntimeSupervisor()
    runtime_supervisor.start_watchdog()
except ModuleNotFoundError:
    class _FallbackRuntimeSupervisor:
        def start_watchdog(self): pass
        def stop_watchdog(self): pass
        def record_cycle(self, *args, **kwargs): pass
        def record_error(self, *args, **kwargs): pass
        def record_broker_disconnect(self, *args, **kwargs): pass
        def record_recovery_attempt(self, *args, **kwargs): pass
        def get_stats(self): return {}
    runtime_supervisor = _FallbackRuntimeSupervisor()


# === PCNRASS SAFE INFRASTRUCTURE IMPORT COMPATIBILITY ===
# These fallbacks prevent dashboard startup failure when a branch is missing
# optional governance/broker/security modules. Existing modules are used when present.

try:
    from backend.core.session_state import get_session_lock_state, is_session_locked, lock_session
except ModuleNotFoundError:
    _CSS_SESSION_LOCK = {"locked": False, "reason": None, "lock_time": None}

    def get_session_lock_state() -> dict:
        return {
            "locked": _CSS_SESSION_LOCK.get("locked", False),
            "reason": _CSS_SESSION_LOCK.get("reason"),
            "lock_time": _CSS_SESSION_LOCK.get("lock_time"),
        }

    def is_session_locked() -> bool:
        return bool(_CSS_SESSION_LOCK.get("locked", False))

    def lock_session(reason: str) -> None:
        _CSS_SESSION_LOCK["locked"] = True
        _CSS_SESSION_LOCK["reason"] = reason
        _CSS_SESSION_LOCK["lock_time"] = datetime.now().isoformat()


try:
    from backend.data.coinbase_historical_downloader import load_runtime_asset
except ModuleNotFoundError:
    def load_runtime_asset(symbol: str):
        print(f"[SAFE FALLBACK] load_runtime_asset unavailable for {symbol}")
        return None


try:
    from backend.app.brokers.oanda_adapter import OandaAdapter
except ModuleNotFoundError:
    class OandaAdapter:
        def get_open_trades(self):
            return {"ok": False, "data": {"trades": []}, "error": "OandaAdapter unavailable"}

        def get_account_summary(self):
            return {"ok": False, "status": "UNAVAILABLE", "error": "OandaAdapter unavailable"}

        def extract_balance_nav(self, summary):
            return {"balance": 0.0, "nav": 0.0}

        def place_order(self, *args, **kwargs):
            return {"ok": False, "status": "UNAVAILABLE", "error": "OandaAdapter unavailable"}


try:
    from backend.app.brokers.broker_bootstrap import initialize_broker
except ModuleNotFoundError:
    def initialize_broker(*args, **kwargs):
        print("[SAFE FALLBACK] initialize_broker unavailable")
        return None


try:
    from backend.app.brokers.coinbase_live_order_gate import CoinbaseLiveOrderGate
except ModuleNotFoundError:
    class _GateResult:
        def __init__(self, allowed=False, reason="CoinbaseLiveOrderGate unavailable"):
            self.allowed = allowed
            self.reason = reason

    class CoinbaseLiveOrderGate:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, *args, **kwargs):
            return _GateResult(False, "CoinbaseLiveOrderGate unavailable")


try:
    from backend.app.brokers.broker_gate_audit import BrokerGateAuditLogger
except ModuleNotFoundError:
    class BrokerGateAuditLogger:
        def log_decision(self, *args, **kwargs):
            return None


from dashboard.auth.css_sign_on import await_login_ready_state


class _PermissionResult:
    def __init__(self, allowed=True):
        self.allowed = allowed


try:
    from backend.security.access_control import AccessControl
except ModuleNotFoundError:
    class AccessControl:
        def can_login(self, role): return _PermissionResult(True)
        def can_view_dashboard(self, role): return _PermissionResult(True)
        def can_run_dashboard(self, role): return _PermissionResult(True)
        def can_arm_broker(self, role): return _PermissionResult(True)
        def can_select_broker(self, role): return _PermissionResult(True)
        def can_use_paper_broker_mode(self, role): return _PermissionResult(True)
        def can_use_live_broker_mode(self, role): return _PermissionResult(False)
        def can_execute_paper_trading(self, role): return _PermissionResult(True)
        def can_execute_live_trading(self, role): return _PermissionResult(False)
        def can_select_engine_mode(self, role, mode): return _PermissionResult(True)


try:
    from backend.security.audit_ledger import AuditLedger
except ModuleNotFoundError:
    class AuditLedger:
        def record(self, event_type, user_id, details):
            return None


try:
    from backend.security.session_manager import SessionManager
except ModuleNotFoundError:
    class _Session:
        def __init__(self, session_id="LOCAL-SESSION"):
            now = time.time()
            self.session_id = session_id
            self.created = now
            self.last_activity = now

    class SessionManager:
        def __init__(self, idle_timeout_seconds=3600, max_session_seconds=28800):
            self.idle_timeout_seconds = idle_timeout_seconds
            self.max_session_seconds = max_session_seconds
            self._sessions = {}

        def create_session(self, username, role, idle_timeout_seconds=None, max_session_seconds=None):
            session = _Session()
            self._sessions[session.session_id] = session
            return session

        def get_session_status(self, session_id):
            session = self._sessions.get(session_id)
            now = time.time()
            created = getattr(session, "created", now)
            last_activity = getattr(session, "last_activity", now)
            return {
                "active": True,
                "created": created,
                "last_activity": last_activity,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
                "end_reason": None,
            }

        def touch_session(self, session_id):
            session = self._sessions.get(session_id)
            if session:
                session.last_activity = time.time()

        def destroy_session(self, session_id, reason="operator_stop"):
            self._sessions.pop(session_id, None)


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

# ===== PCNRASS SESSION + ACCOUNT + ASSET BALANCE MODEL =====
ACCOUNT_STATE_FILE = ARTIFACTS_DIR / "css_account_state_pcnrass.json"
SESSION_STATE_FILE = ARTIFACTS_DIR / "css_session_state_pcnrass.json"
MOBILE_CONTROLS_FILE = ARTIFACTS_DIR / "css_mobile_controls.json"

def _pcnrass_read_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _pcnrass_write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

pcnrass_account_state = _pcnrass_read_json(ACCOUNT_STATE_FILE, {
    "account_balance": 200.0,
    "lifetime_realized_pnl": 0.0,
    "last_session_close": None,
})

pcnrass_session_state = {
    "session_id": datetime.now().isoformat(timespec="seconds"),
    "starting_account_balance": float(pcnrass_account_state.get("account_balance", 200.0)),
    "session_realized_pnl": 0.0,
    "session_unrealized_pnl": 0.0,
    "session_equity": float(pcnrass_account_state.get("account_balance", 200.0)),
}

pcnrass_asset_balances = {
    "CRYPTO": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FX": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FUTURES": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "OPTIONS": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
}

def pcnrass_refresh_balances(realized_by_asset, floating_by_asset):
    for asset in pcnrass_asset_balances:
        realized = float(realized_by_asset.get(asset, 0.0))
        unrealized = float(floating_by_asset.get(asset, 0.0))
        pcnrass_asset_balances[asset]["realized"] = round(realized, 4)
        pcnrass_asset_balances[asset]["unrealized"] = round(unrealized, 4)
        pcnrass_asset_balances[asset]["equity"] = round(realized + unrealized, 4)

    pcnrass_session_state["session_realized_pnl"] = round(
        sum(v["realized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_unrealized_pnl"] = round(
        sum(v["unrealized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_equity"] = round(
        float(pcnrass_session_state["starting_account_balance"])
        + float(pcnrass_session_state["session_realized_pnl"])
        + float(pcnrass_session_state["session_unrealized_pnl"]),
        4,
    )

    _pcnrass_write_json(SESSION_STATE_FILE, {
        "session": pcnrass_session_state,
        "assets": pcnrass_asset_balances,
        "account_balance_pending_close": pcnrass_session_state["session_equity"],
    })

def pcnrass_close_session_to_account():
    pcnrass_account_state["account_balance"] = round(float(pcnrass_session_state["session_equity"]), 4)
    pcnrass_account_state["lifetime_realized_pnl"] = round(
        float(pcnrass_account_state.get("lifetime_realized_pnl", 0.0))
        + float(pcnrass_session_state.get("session_realized_pnl", 0.0)),
        4,
    )
    pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")
    _pcnrass_write_json(ACCOUNT_STATE_FILE, pcnrass_account_state)

def current_startup_broker_state() -> dict[str, Any]:
    state = globals().get("STARTUP_BROKER_STATE")
    if isinstance(state, dict):
        return dict(state)
    selection = globals().get("STARTUP_BROKER_SELECTION")
    if hasattr(selection, "as_dict"):
        return selection.as_dict()
    return build_startup_broker_selection().as_dict()

def pcnrass_publish_runtime_artifacts(cycle_number, supervisor_stats=None, tracker_snapshot=None):
    if RuntimeArtifactPublisher is None:
        return {
            "status": "DATA UNAVAILABLE",
            "warnings": ["runtime_artifact_publisher_unavailable"],
            "advisory_only": True,
            "execution_allowed": False,
        }
    try:
        positions = []
        if "mtm_engine" in globals():
            positions = [dict(pos) for pos in getattr(mtm_engine, "positions", []) if not bool(pos.get("forced_exit"))]
        session_payload = {
            "session": {
                **dict(pcnrass_session_state),
                "cycle_number": int(cycle_number),
                "runtime_cycle": int(cycle_number),
                "engine_mode": str(globals().get("ENGINE_MODE", "PAPER")),
                "broker_mode": str(globals().get("SELECTED_BROKER_MODE", "NONE")),
                "selected_broker": str(globals().get("SELECTED_BROKER", "NONE")),
                "broker": str(globals().get("SELECTED_BROKER", "NONE")),
                "broker_execution_armed": bool(globals().get("BROKER_EXECUTION_ARMED", False)),
                "broker_execution_enabled": False,
                "broker_state": current_startup_broker_state(),
            },
            "assets": dict(pcnrass_asset_balances),
            "account_balance_pending_close": pcnrass_session_state.get("session_equity"),
        }
        account_payload = {
            **dict(pcnrass_account_state),
            "total_equity": pcnrass_session_state.get("session_equity"),
            "cash": pcnrass_account_state.get("account_balance"),
            "buying_power": pcnrass_account_state.get("account_balance"),
            "unrealized_pnl": pcnrass_session_state.get("session_unrealized_pnl"),
            "realized_pnl": pcnrass_session_state.get("session_realized_pnl"),
            "positions": positions,
            "selected_broker": str(globals().get("SELECTED_BROKER", "NONE")),
            "broker_mode": str(globals().get("SELECTED_BROKER_MODE", "paper")),
            "broker_execution_armed": bool(globals().get("BROKER_EXECUTION_ARMED", False)),
            "broker_execution_enabled": False,
            "broker_state": current_startup_broker_state(),
        }
        realized = float(account_payload.get("realized_pnl", 0.0) or 0.0)
        unrealized = float(account_payload.get("unrealized_pnl", 0.0) or 0.0)
        runtime_state = {
            "status": "OK",
            "portfolio_state": "NO_PORTFOLIO" if not positions else "ACTIVE_PORTFOLIO",
            "account": {
                "cash": account_payload.get("cash", 0.0),
                "equity": account_payload.get("total_equity", account_payload.get("account_balance", 0.0)),
                "buying_power": account_payload.get("buying_power", account_payload.get("account_balance", 0.0)),
                "open_pnl": account_payload.get("unrealized_pnl", 0.0),
                "realized_pnl": account_payload.get("realized_pnl", 0.0),
                "total_pnl": realized + unrealized,
            },
            "positions": positions,
            "trades": [],
            "asset_allocations": {},
            "performance_metrics": tracker_snapshot if isinstance(tracker_snapshot, dict) else {},
            "supervisor": supervisor_stats if isinstance(supervisor_stats, dict) else {},
            "runtime_cycle": int(cycle_number),
            "engine_mode": str(globals().get("ENGINE_MODE", "PAPER")),
            "broker_mode": str(globals().get("SELECTED_BROKER_MODE", "NONE")),
            "selected_broker": str(globals().get("SELECTED_BROKER", "NONE")),
            "broker_execution_armed": bool(globals().get("BROKER_EXECUTION_ARMED", False)),
            "broker_execution_enabled": False,
            "broker_state": current_startup_broker_state(),
            "advisory_only": True,
            "execution_allowed": False,
        }
        return RuntimeArtifactPublisher(
            artifacts_dir=ARTIFACTS_DIR,
            account_state_path=ACCOUNT_STATE_FILE,
            session_state_path=SESSION_STATE_FILE,
            closed_trade_ledger_path=CLOSED_TRADE_LEDGER_PATH,
        ).publish(
            runtime_cycle=int(cycle_number),
            account_state=account_payload,
            session_state=session_payload,
            runtime_portfolio_state=runtime_state,
            validation_summary={
                "status": "OK",
                "runtime_health": "GREEN" if supervisor_stats else "DATA UNAVAILABLE",
                "recommendation": "Continue advisory-only paper runtime monitoring.",
                "confidence": None,
                "warnings": [],
                "blockers": [],
            },
            session_id=str(pcnrass_session_state.get("session_id") or ""),
        )
    except Exception as exc:
        return {
            "status": "AMBER",
            "warnings": [f"runtime_artifact_publish_failed:{str(exc)[:120]}"],
            "advisory_only": True,
            "execution_allowed": False,
        }

def pcnrass_print_balance_panel():
    print("--- PCNRASS CAPITAL BALANCES ---")
    print(f"ACCOUNT BALANCE (SESSION START): ${float(pcnrass_session_state['starting_account_balance']):,.2f}")
    print(f"SESSION REALIZED PNL: {float(pcnrass_session_state['session_realized_pnl']):+.4f}")
    print(f"SESSION UNREALIZED PNL: {float(pcnrass_session_state['session_unrealized_pnl']):+.4f}")
    print(f"SESSION EQUITY: ${float(pcnrass_session_state['session_equity']):,.2f}")
    print("ASSET BALANCES:")
    for asset, bal in pcnrass_asset_balances.items():
        print(
            f"  {asset:<8} realized={bal['realized']:+.4f} "
            f"unrealized={bal['unrealized']:+.4f} equity={bal['equity']:+.4f}"
        )



RESET_SESSION_ON_BOOT = False  # PCNRASS: preserve recovery state across restarts

if RESET_SESSION_ON_BOOT and STATE_FILE.exists():
    try:
        STATE_FILE.unlink()
        print("[RESET] Previous CSS recovery state deleted on boot.")
    except Exception as e:
        print(f"[RESET WARNING] Could not delete recovery state: {e}")


SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD",
]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD",
    "USD_CAD", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY",
]

OPTION_SYMBOLS = ["AAPL-C-175", "SPY-C-500", "QQQ-C-400"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

CYCLE_SLEEP = 8
FX_LIVE_UNITS = 1
COINBASE_TEST_ORDER_USD = paper_only_coinbase_test_order_usd(mode=os.getenv("SELECTED_BROKER_MODE"))
COINBASE_MAX_LIVE_ORDER_USD = float(os.getenv("COINBASE_MAX_LIVE_ORDER_USD", "1.00") or 1.00)

SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("CSS_SESSION_IDLE_TIMEOUT_SECONDS", "3600") or 3600)
SESSION_MAX_SECONDS = int(os.getenv("CSS_SESSION_MAX_SECONDS", "28800") or 28800)

MAX_PAPER_OPEN_POSITIONS = 10

PAPER_PROFIT_TARGET_FLOATING = 0.25
PAPER_PROFIT_TARGET_MIN_AGE_CYCLES = 2

CLOSED_TRADE_LEDGER_PATH = Path("audit_logs") / "closed_trades.jsonl"
CLOSED_TRADE_LEDGER_MARKER = "CLOSED_TRADE_LEDGER"
MAX_OPEN_PER_CYCLE = 8
DEFENSIVE_REDUCTION_PER_CYCLE = 2

HARD_TOTAL_OPEN_POSITION_CAP = 10
HARD_ASSET_OPEN_CAPS = {
    "CRYPTO": 3,
    "FX": 3,
    "FUTURES": 2,
    "OPTIONS": 2,
}
MAX_NEW_PER_CYCLE_BY_ASSET = {
    "CRYPTO": 2,
    "FX": 2,
    "FUTURES": 2,
    "OPTIONS": 2,
}

SUPPORTED_BROKERS = {
    "1": "NONE",
    "2": "OANDA",
    "3": "COINBASE",
    "4": "ALPACA",
    "5": "FUTURES_RESERVED",
}

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

MODE_EXIT_PROFILE = {
    # Profit-dominance lifecycle tuning:
    # minimum max_age is now 6 cycles so strong trades have room to develop.
    "SAFE": {"take_profit": 1.75, "stop_loss": -1.25, "max_age": 6},
    "CONSERVATIVE": {"take_profit": 2.25, "stop_loss": -1.75, "max_age": 6},
    "BALANCED": {"take_profit": 3.00, "stop_loss": -2.25, "max_age": 6},
    "AGGRESSIVE": {"take_profit": 4.00, "stop_loss": -3.00, "max_age": 7},
    "EXPANSION": {"take_profit": 5.00, "stop_loss": -3.75, "max_age": 8},
}

ASSET_DRIFT_PROFILE = {
    "CRYPTO": (-0.08, 0.16),
    "FX": (-0.03, 0.06),
    "OPTIONS": (-0.22, 0.34),
    "FUTURES": (-0.25, 0.38),
}

audit_ledger = AuditLedger()


def create_session_manager_compatible() -> SessionManager:
    """
    PCNRASS compatibility helper.
    Some CSS branches accept timeout kwargs; some use a no-arg SessionManager.
    This avoids runtime regression across branches.
    """
    try:
        return SessionManager(
            idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
            max_session_seconds=SESSION_MAX_SECONDS,
        )
    except TypeError:
        try:
            manager = SessionManager()
            # Best-effort attribute injection for older/simple SessionManager versions.
            try:
                manager.idle_timeout_seconds = SESSION_IDLE_TIMEOUT_SECONDS
                manager.max_session_seconds = SESSION_MAX_SECONDS
            except Exception:
                pass
            return manager
        except TypeError:
            # Final fallback for unusual signatures.
            return SessionManager


session_manager = create_session_manager_compatible()


# === PCNRASS SESSION MANAGER COMPATIBILITY LAYER ===
# Some CSS branches have SessionManager but without get_session_status/touch/destroy methods.
# Add missing methods at runtime without changing existing behavior.
if not hasattr(session_manager, "_pcnrass_session_store"):
    session_manager._pcnrass_session_store = {}

if not hasattr(session_manager, "get_session_status"):
    def _pcnrass_get_session_status(session_id):
        now = time.time()
        session = session_manager._pcnrass_session_store.get(str(session_id), {})
        created = float(session.get("created", now))
        last_activity = float(session.get("last_activity", now))
        return {
            "active": True,
            "created": created,
            "last_activity": last_activity,
            "idle_timeout_seconds": SESSION_IDLE_TIMEOUT_SECONDS,
            "max_session_seconds": SESSION_MAX_SECONDS,
            "end_reason": None,
        }
    session_manager.get_session_status = _pcnrass_get_session_status

if not hasattr(session_manager, "touch_session"):
    def _pcnrass_touch_session(session_id):
        sid = str(session_id)
        now = time.time()
        session_manager._pcnrass_session_store.setdefault(sid, {"created": now})
        session_manager._pcnrass_session_store[sid]["last_activity"] = now
    session_manager.touch_session = _pcnrass_touch_session

if not hasattr(session_manager, "destroy_session"):
    def _pcnrass_destroy_session(session_id, reason="operator_stop"):
        session_manager._pcnrass_session_store.pop(str(session_id), None)
    session_manager.destroy_session = _pcnrass_destroy_session

# Make sure a created session is tracked even if the repo SessionManager does not track it visibly.
_original_create_session = getattr(session_manager, "create_session", None)
if callable(_original_create_session):
    def _pcnrass_create_session_compatible(*args, **kwargs):
        session = _original_create_session(*args, **kwargs)
        sid = str(getattr(session, "session_id", "LOCAL-SESSION"))
        now = time.time()
        session_manager._pcnrass_session_store.setdefault(
            sid,
            {"created": getattr(session, "created", now), "last_activity": now},
        )
        return session
    session_manager.create_session = _pcnrass_create_session_compatible

access_control = AccessControl()


# === PCNRASS ACCESS CONTROL COMPATIBILITY LAYER ===
# Some CSS branches have AccessControl but not every newer permission method.
# Missing permissions are safely defaulted so SUPER_USER can restore dashboard operation.
class _PCNRASSPermissionResult:
    def __init__(self, allowed=True):
        self.allowed = allowed


def _pcnrass_allow(*args, **kwargs):
    return _PCNRASSPermissionResult(True)


def _pcnrass_deny_live(*args, **kwargs):
    return _PCNRASSPermissionResult(False)


for _method_name in [
    "can_login",
    "can_view_dashboard",
    "can_run_dashboard",
    "can_arm_broker",
    "can_select_broker",
    "can_use_paper_broker_mode",
    "can_execute_paper_trading",
    "can_select_engine_mode",
]:
    if not hasattr(access_control, _method_name):
        setattr(access_control, _method_name, _pcnrass_allow)

# PCNRASS R2:
# SUPER_USER may enter live broker mode for real balance visibility.
# Live execution remains separately controlled by broker gates, env flags,
# live-order switches, and order-specific protections.
def _pcnrass_live_mode_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    return _PCNRASSPermissionResult(role_value == "SUPER_USER")


def _pcnrass_live_execution_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    live_orders_enabled = (
        str(os.getenv("COINBASE_ENABLE_LIVE_ORDERS", "")).strip().lower()
        in {"1", "true", "yes", "y", "on"}
    )
    return _PCNRASSPermissionResult(role_value == "SUPER_USER" and live_orders_enabled)


# Allow SUPER_USER to select live mode so real broker balances can be fetched.
access_control.can_use_live_broker_mode = _pcnrass_live_mode_permission

# Keep actual live execution more restrictive.
access_control.can_execute_live_trading = _pcnrass_live_execution_permission

SESSION_CLOSED = False


def runtime_origin_context() -> dict[str, Any]:
    computer_name = os.getenv("COMPUTERNAME") or socket.gethostname()
    return {
        "computer_name": computer_name,
        "host_name": socket.gethostname(),
        "process_id": os.getpid(),
        "cwd": str(PROJECT_ROOT),
        "script_name": "scripts/css_live_dashboard.py",
        "login_channel": "CLI",
    }


def session_policy_context() -> dict[str, Any]:
    return {
        "idle_timeout_seconds": SESSION_IDLE_TIMEOUT_SECONDS,
        "max_session_seconds": SESSION_MAX_SECONDS,
    }


def build_role_profile(role: str) -> dict[str, Any]:
    role = str(role).strip().upper()

    allowed_engine_modes = [
        mode
        for mode in ENGINE_MODES.values()
        if access_control.can_select_engine_mode(role, mode).allowed
    ]

    return {
        "can_login": access_control.can_login(role).allowed,
        "can_view_dashboard": access_control.can_view_dashboard(role).allowed,
        "can_run_dashboard": access_control.can_run_dashboard(role).allowed,
        "can_arm_broker": access_control.can_arm_broker(role).allowed,
        "can_select_broker": access_control.can_select_broker(role).allowed,
        "can_use_paper_broker_mode": access_control.can_use_paper_broker_mode(role).allowed,
        "can_use_live_broker_mode": access_control.can_use_live_broker_mode(role).allowed,
        "can_execute_paper_trading": access_control.can_execute_paper_trading(role).allowed,
        "can_execute_live_trading": access_control.can_execute_live_trading(role).allowed,
        "allowed_engine_modes": allowed_engine_modes,
    }


def record_rbac_event(
    event_type: str,
    user_ctx: dict[str, Any],
    details: dict[str, Any],
) -> None:
    audit_ledger.record(
        event_type,
        str(user_ctx.get("user_id", "UNKNOWN")),
        {
            "session_id": user_ctx.get("session_id"),
            "display_name": user_ctx.get("display_name"),
            "role": user_ctx.get("role"),
            **details,
        },
    )


def enforce_dashboard_startup_access(user_ctx: dict[str, Any]) -> dict[str, Any]:
    role = str(user_ctx.get("role", "VIEWER")).strip().upper()
    role_profile = build_role_profile(role)

    user_ctx["role_profile"] = role_profile

    if not role_profile["can_login"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "auth",
                "action": "login",
                "reason": "role_cannot_login",
            },
        )
        raise SystemExit(1)

    if not role_profile["can_view_dashboard"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "dashboard",
                "action": "view",
                "reason": "role_cannot_view_dashboard",
            },
        )
        raise SystemExit(1)

    if not role_profile["can_run_dashboard"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "dashboard",
                "action": "run",
                "reason": "role_cannot_run_dashboard",
            },
        )
        raise SystemExit(1)

    record_rbac_event(
        "startup_rbac_profile",
        user_ctx,
        {
            "role_profile": role_profile,
        },
    )
    return user_ctx


def authenticate_startup_user() -> dict[str, Any]:
    try:
        user_ctx = await_login_ready_state()
        try:
            session = session_manager.create_session(
                username=str(user_ctx.get("user_id")),
                role=str(user_ctx.get("role")),
                idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
                max_session_seconds=SESSION_MAX_SECONDS,
            )
        except TypeError:
            try:
                session = session_manager.create_session(
                    username=str(user_ctx.get("user_id")),
                    role=str(user_ctx.get("role")),
                )
            except TypeError:
                session = session_manager.create_session(str(user_ctx.get("user_id")))
        origin = runtime_origin_context()

        user_ctx["session_id"] = session.session_id
        user_ctx["session_created"] = session.created
        user_ctx["computer_name"] = origin["computer_name"]
        user_ctx["host_name"] = origin["host_name"]
        user_ctx["process_id"] = origin["process_id"]
        user_ctx["login_channel"] = origin["login_channel"]
        user_ctx["script_name"] = origin["script_name"]
        user_ctx["session_status"] = session_manager.get_session_status(session.session_id)

        audit_ledger.record(
            "login_success",
            str(user_ctx.get("user_id")),
            {
                "session_id": session.session_id,
                "display_name": user_ctx.get("display_name"),
                "role": user_ctx.get("role"),
                "unit_code": user_ctx.get("unit_code"),
                "home_branch": user_ctx.get("home_branch"),
                **origin,
                **session_policy_context(),
            },
        )

        user_ctx = enforce_dashboard_startup_access(user_ctx)

        print(
            f"[AUTH OK] user_id={user_ctx.get('user_id')} "
            f"role={user_ctx.get('role')} "
            f"unit={user_ctx.get('unit_code')} "
            f"session_id={session.session_id}"
        )
        return user_ctx

    except KeyboardInterrupt:
        try:
            pcnrass_close_session_to_account()
        except Exception as e:
            print(f"[SESSION SETTLEMENT WARN] {e}")

        print("[SESSION STOPPED] Keyboard interrupt received.")
        raise

    except SystemExit:
        raise

    except Exception as e:
        origin = runtime_origin_context()
        audit_ledger.record(
            "login_failed",
            "UNKNOWN",
            {
                "reason": str(e),
                **origin,
            },
        )
        print(f"[AUTH FAILED] {e}")
        raise SystemExit(1)


def sync_session_status() -> dict[str, Any]:
    session_id = str(SESSION_USER_CTX.get("session_id", ""))
    status = session_manager.get_session_status(session_id)
    SESSION_USER_CTX["session_status"] = status
    return status


def touch_active_session() -> dict[str, Any]:
    session_id = str(SESSION_USER_CTX.get("session_id", ""))
    session_manager.touch_session(session_id)
    return sync_session_status()


def activate_defensive_expiry_mode(reason: str, cycle: int, last_trade: str) -> dict[str, Any]:
    _safe_emit_alert(
        "emit_system_alert",
        severity=AlertSeverity.CRITICAL,
        message=f"Defensive expiry mode activated: {reason}",
        metadata={"cycle": cycle, "last_trade": last_trade}
    )
    lock_session(reason)

    lock_state = get_session_lock_state()
    audit_ledger.record(
        "session_locked_defensive_mode",
        str(SESSION_USER_CTX.get("user_id")),
        {
            "session_id": SESSION_USER_CTX.get("session_id"),
            "display_name": SESSION_USER_CTX.get("display_name"),
            "role": SESSION_USER_CTX.get("role"),
            "reason": reason,
            "cycle": cycle,
            "last_trade": last_trade,
            "lock_time": lock_state.get("lock_time"),
            "computer_name": SESSION_USER_CTX.get("computer_name"),
            "host_name": SESSION_USER_CTX.get("host_name"),
            "process_id": SESSION_USER_CTX.get("process_id"),
            "script_name": SESSION_USER_CTX.get("script_name"),
        },
    )

    print(f"[DEFENSIVE EXPIRY MODE] reason={reason} | new trades blocked, position management continues")

    return {
        "active": False,
        "end_reason": reason,
        "defensive_mode_active": True,
    }


def enforce_active_session(cycle: int, last_trade: str) -> dict[str, Any]:
    status = sync_session_status()

    if not status.get("active", False):
        reason = str(status.get("end_reason") or "session_expired")
        return activate_defensive_expiry_mode(reason, cycle, last_trade)

    return status



def select_global_broker_mode():
    result = _run_operator_startup_state_machine_once()
    return result.state.global_mode or "paper"



COINBASE_LIVE_CONFIRMATION_STATUS: dict[str, Any] = {
    "accepted": False,
    "broker_mode": "paper",
    "reason": "coinbase_live_confirmation_not_requested",
    "required_confirmation": "LIVE",
}
STARTUP_WIZARD_STATE = StartupWizardState()
STARTUP_STATE_MACHINE_RESULT: Any | None = None
PHASE153F_STARTUP_BROKER_SELECTION_LABELS = (
    "=== CSS STARTUP BROKER SELECTION ===",
    "1. NONE / PAPER ONLY",
    "2. COINBASE",
    "3. OANDA",
)


def _startup_timeout_seconds() -> int:
    try:
        return max(1, int(os.getenv("CSS_STARTUP_TIMEOUT_SECONDS", "120") or "120"))
    except ValueError:
        return 120


def _run_operator_startup_state_machine_once() -> Any:
    global STARTUP_STATE_MACHINE_RESULT, STARTUP_WIZARD_STATE, COINBASE_LIVE_CONFIRMATION_STATUS
    if STARTUP_STATE_MACHINE_RESULT is not None:
        return STARTUP_STATE_MACHINE_RESULT

    role_profile = SESSION_USER_CTX.get("role_profile", {})
    if not isinstance(role_profile, dict):
        role_profile = {}
    try:
        pilot_status = live_micro_pilot_status()
    except Exception:
        pilot_status = {
            "pilot_state": "DISARMED",
            "currency": "CAD",
            "canonical_live_pilot_limit_cad": "20.00",
            "max_live_test_capital": "20.00",
        }
    result = run_startup_state_machine(
        input_func=input,
        output_func=print,
        flush_func=default_stdin_flush,
        config=StartupMachineConfig(
            timeout_seconds=_startup_timeout_seconds(),
            audit_path=Path("audit_logs") / "startup_state_machine.jsonl",
            test_mode_auto_confirm=os.getenv("CSS_TEST_MODE") == "1",
        ),
        role_profile=role_profile,
        env=os.environ,
        pilot_status=pilot_status,
        allowed_engine_modes=role_profile.get("allowed_engine_modes", []),
    )
    STARTUP_STATE_MACHINE_RESULT = result
    machine_state = result.state
    STARTUP_WIZARD_STATE = StartupWizardState(
        step=str(machine_state.state).lower(),
        authenticated=True,
        global_mode=machine_state.global_mode or "paper",
        selected_broker=machine_state.selected_broker or "NONE",
        broker_mode=machine_state.broker_mode or "paper",
        broker_execution_armed=machine_state.broker_execution_armed,
        operator_requested_live=machine_state.operator_requested_live,
        execution_authority=machine_state.execution_authority,
        authority_reason=machine_state.authority_reason,
        live_authority_state=machine_state.live_authority_state,
        engine_mode=machine_state.engine_mode or "SAFE",
        cycle_mode=machine_state.cycle_mode or "manual",
        cycle_interval_seconds=machine_state.cycle_interval_seconds,
        execution_scope=machine_state.execution_scope,
        can_live_execute=machine_state.can_live_execute,
        restart_requested=machine_state.restart_requested,
        exit_requested=machine_state.cancelled,
        last_error=machine_state.last_error,
    )
    if machine_state.selected_broker == "COINBASE" and machine_state.broker_mode == "live":
        COINBASE_LIVE_CONFIRMATION_STATUS = {
            "accepted": True,
            "broker_mode": "live",
            "reason": "coinbase_live_read_only_confirmed",
            "required_confirmation": "LIVE",
        }
    if result.timed_out or result.cancelled or not result.runtime_start_allowed:
        raise SystemExit(0)
    return result


def select_startup_broker_selection() -> tuple[str, str]:
    result = _run_operator_startup_state_machine_once()
    selected = result.state.selected_broker or "NONE"
    broker_mode = result.state.broker_mode or "paper"
    if selected == "OANDA":
        if broker_mode == "live":
            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"
        else:
            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
    record_rbac_event(
        "broker_selected",
        SESSION_USER_CTX,
        {
            "selected_broker": selected,
            "selected_broker_mode": broker_mode,
            "read_only_validation_allowed": broker_mode == "live",
            "broker_execution_armed": False,
            "live_confirmation_reason": COINBASE_LIVE_CONFIRMATION_STATUS.get("reason") if selected == "COINBASE" else None,
        },
    )
    print(f"[BROKER SELECTED] {selected} / mode={broker_mode} / execution=DISABLED")
    return selected, broker_mode


def select_broker_execution_config(selected_broker: str, selected_broker_mode: str) -> tuple[bool, str, str]:
    # Phase 153F preserves the Phase 153C disabled-execution contract:
    # return False, selected_broker, selected_broker_mode
    result = _run_operator_startup_state_machine_once()
    armed = bool(result.state.broker_execution_armed)
    operator_requested = bool(getattr(result.state, "operator_requested_live", False))
    selected = result.state.selected_broker or selected_broker
    mode = result.state.broker_mode or selected_broker_mode
    record_rbac_event(
        "broker_execution_armed" if armed else "broker_execution_disarmed",
        SESSION_USER_CTX,
        {
            "resource": "broker",
            "action": "request_live" if operator_requested else ("arm" if armed else "disarm"),
            "reason": "phase153f_startup_state_machine",
            "selected_broker": selected,
            "selected_broker_mode": mode,
            "operator_requested_live": operator_requested,
            "execution_authority": bool(getattr(result.state, "execution_authority", False)),
        },
    )
    if operator_requested:
        print(f"[BROKER EXECUTION REQUESTED] Execution authority remains DISABLED: {selected} / mode={mode}")
    else:
        print(f"[BROKER EXECUTION {'ARMED' if armed else 'DISABLED'}] Selected broker preserved: {selected} / mode={mode}")
    return armed, selected, mode


def select_engine_mode() -> str:
    result = _run_operator_startup_state_machine_once()
    requested_mode = result.state.engine_mode or "SAFE"
    record_rbac_event(
        "engine_mode_selected",
        SESSION_USER_CTX,
        {
            "requested_mode": requested_mode,
            "selected_mode": requested_mode,
            "reason": "phase153f_startup_state_machine",
        },
    )
    return requested_mode


def select_cycle_mode() -> None:
    result = _run_operator_startup_state_machine_once()
    if result.state.cycle_mode != "continuous":
        os.environ["CSS_AUTO_CYCLE"] = "false"
        print("[CYCLE MODE SELECTED] MANUAL")
        return

    os.environ["CSS_AUTO_CYCLE"] = "true"
    interval = int(result.state.cycle_interval_seconds or 60)
    os.environ["CSS_CYCLE_SLEEP_SECONDS"] = str(interval)
    print(f"[CYCLE MODE SELECTED] CONTINUOUS interval={interval}s")


def confirm_startup_summary_before_runtime() -> None:
    result = _run_operator_startup_state_machine_once()
    if not result.runtime_start_allowed:
        print("[STARTUP NOT CONFIRMED] Runtime will not start.")
        raise SystemExit(0)
    summary = _render_final_live_startup_summary()
    _publish_final_startup_diagnostics(summary)
    print("[STARTUP CONFIRMED] Runtime cycle may start.")


def _render_final_live_startup_summary() -> dict[str, Any]:
    try:
        pilot_status = live_micro_pilot_status()
    except Exception:
        pilot_status = {
            "pilot_state": "DISARMED",
            "currency": "CAD",
            "canonical_live_pilot_limit_cad": "20.00",
            "capital_governor": "PHASE_152A_CAD20_GUARD_ONLY",
        }
    startup_state = STARTUP_WIZARD_STATE.as_dict() if hasattr(STARTUP_WIZARD_STATE, "as_dict") else {}
    startup_state.update(
        {
            "selected_broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "broker_execution_armed": bool(BROKER_EXECUTION_ARMED),
            "operator_requested_live": bool(getattr(STARTUP_WIZARD_STATE, "operator_requested_live", False)),
            "engine_mode": globals().get("ENGINE_MODE", startup_state.get("engine_mode", "SAFE")),
        }
    )
    summary = build_live_startup_summary(
        startup_state,
        broker_status=globals().get("STARTUP_BROKER_STATE", {}),
        pilot_status=pilot_status,
        gate_status={
            "capital_governor": "PHASE_152A_CAD20_GUARD_ONLY",
            "unified_trade_gate": "AUTHORITATIVE_FAIL_CLOSED",
            "margin_gate": "AUTHORITATIVE_FAIL_CLOSED",
            "anti_bleed_guard": "AUTHORITATIVE_FAIL_CLOSED",
            "kill_switch": "AUTHORITATIVE_FAIL_CLOSED",
        },
    )
    for line in format_live_startup_summary(summary):
        print(line)
    return summary


def _publish_final_startup_diagnostics(summary: dict[str, Any]) -> None:
    try:
        diagnostics = publish_startup_diagnostics(ARTIFACTS_DIR / "startup_diagnostics.json", summary)
        readiness = publish_live_readiness_state(ARTIFACTS_DIR / "live_readiness_state.json", diagnostics)
        if isinstance(globals().get("STARTUP_BROKER_STATE"), dict):
            STARTUP_BROKER_STATE.update(
                {
                    "startup_diagnostics": diagnostics,
                    "readiness_state": readiness.get("readiness_state", summary.get("readiness_state", "UNCONFIGURED")),
                    "go_no_go": readiness.get("go_no_go", summary.get("go_no_go", "NO GO")),
                    "readiness_checklist": readiness.get("readiness_checklist", summary.get("readiness_checklist", [])),
                    "operator_requested_live": bool(summary.get("operator_requested_live", False)),
                    "execution_authority": False,
                    "authority_reason": str(summary.get("authority_reason", "Operator Intent Missing")),
                    "live_authority_state": str(summary.get("live_authority_state", "BLOCKED")),
                    "live_execution_authority": dict(summary.get("live_execution_authority", {}))
                    if isinstance(summary.get("live_execution_authority"), dict)
                    else {},
                    "broker_execution_enabled": False,
                    "can_live_execute": False,
                }
            )
            pcnrass_session_state["broker_state"] = STARTUP_BROKER_STATE
            pcnrass_account_state["broker_state"] = STARTUP_BROKER_STATE
            persist_broker_selection(
                account_state_path=ACCOUNT_STATE_FILE,
                session_state_path=SESSION_STATE_FILE,
                selection=STARTUP_BROKER_SELECTION,
                broker_state_override=STARTUP_BROKER_STATE,
            )
    except Exception as exc:
        print(f"[STARTUP DIAGNOSTICS WARN] {exc}")


def safe_load_runtime_asset(symbol: str) -> bool:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            load_runtime_asset(symbol)
        print(f"Fetched candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


def record_startup_configuration(
    *,
    user_ctx: dict[str, Any],
    broker_execution_armed: bool,
    selected_broker: str,
    selected_broker_mode: str,
    engine_mode: str,
) -> None:
    audit_ledger.record(
        "session_startup_config",
        str(user_ctx.get("user_id")),
        {
            "session_id": user_ctx.get("session_id"),
            "display_name": user_ctx.get("display_name"),
            "role": user_ctx.get("role"),
            "broker_execution_armed": broker_execution_armed,
            "selected_broker": selected_broker,
            "selected_broker_mode": selected_broker_mode,
            "engine_mode": engine_mode,
            "role_profile": user_ctx.get("role_profile"),
            "computer_name": user_ctx.get("computer_name"),
            "host_name": user_ctx.get("host_name"),
            "process_id": user_ctx.get("process_id"),
            "script_name": user_ctx.get("script_name"),
            **session_policy_context(),
        },
    )


def close_active_session(reason: str, extra: Optional[dict[str, Any]] = None) -> None:
    global SESSION_CLOSED

    if SESSION_CLOSED:
        return

    payload = {
        "session_id": SESSION_USER_CTX.get("session_id"),
        "display_name": SESSION_USER_CTX.get("display_name"),
        "role": SESSION_USER_CTX.get("role"),
        "reason": reason,
        "computer_name": SESSION_USER_CTX.get("computer_name"),
        "host_name": SESSION_USER_CTX.get("host_name"),
        "process_id": SESSION_USER_CTX.get("process_id"),
        "script_name": SESSION_USER_CTX.get("script_name"),
    }

    if extra:
        payload.update(extra)

    audit_ledger.record(
        "session_end",
        str(SESSION_USER_CTX.get("user_id")),
        payload,
    )
    try:
        import time
        from dashboard.auth.css_sign_on import record_auth_audit_event
        session_created = SESSION_USER_CTX.get("session_created")
        session_age = None
        if session_created:
            try:
                session_age = float(time.time() - float(session_created))
            except Exception:
                pass
        record_auth_audit_event(
            "logout",
            str(SESSION_USER_CTX.get("user_id", "UNKNOWN")),
            "SUCCESS",
            failure_reason=None,
            session_age=session_age,
            auth_source=str(SESSION_USER_CTX.get("auth_source", "unknown")),
            details={"reason": reason}
        )
    except Exception:
        pass

    # PCNRASS: settle session balance into account balance only at session close.
    try:
        pcnrass_close_session_to_account()
    except Exception:
        pass

    session_id = SESSION_USER_CTX.get("session_id")
    if session_id:
        try:
            session_manager.destroy_session(str(session_id), reason=reason)
        except TypeError:
            try:
                session_manager.destroy_session(str(session_id))
            except TypeError:
                pass

    SESSION_CLOSED = True
    try:
        from dashboard.auth.css_sign_on import invalidate_login_session
        invalidate_login_session()
    except Exception:
        pass



# === PCNRASS RESTORED CSS AUTHENTICATION ===
# Scope: authentication only. Do not touch PnL, broker, execution, dashboard, or risk logic.
# Policy:
# - Initial super user: 00000
# - Initial password: 123456
# Duplicate auth authority removed in Phase 113A
# Using canonical dashboard.auth.css_sign_on import defined at top of file.


SESSION_USER_CTX = authenticate_startup_user()

GLOBAL_BROKER_MODE = select_global_broker_mode()

SELECTED_BROKER, SELECTED_BROKER_MODE = select_startup_broker_selection()

BROKER_EXECUTION_ARMED, SELECTED_BROKER, SELECTED_BROKER_MODE = select_broker_execution_config(
    SELECTED_BROKER,
    SELECTED_BROKER_MODE,
)

STARTUP_BROKER_SELECTION = build_startup_broker_selection(
    selected_broker=SELECTED_BROKER,
    broker_mode=SELECTED_BROKER_MODE,
    broker_execution_armed=BROKER_EXECUTION_ARMED,
    operator_requested_live=bool(getattr(STARTUP_WIZARD_STATE, "operator_requested_live", False)),
    execution_authority=False,
    authority_reason="Credentials Missing" if bool(getattr(STARTUP_WIZARD_STATE, "operator_requested_live", False)) else "Operator Intent Missing",
    live_authority_state="BLOCKED",
)
if SELECTED_BROKER == "OANDA":
    COINBASE_READ_ONLY_STATUS = evaluate_oanda_live_read_only(
        STARTUP_BROKER_SELECTION,
        legacy_limit_usd=1.0,
    )
else:
    COINBASE_READ_ONLY_STATUS = evaluate_coinbase_live_read_only(
        STARTUP_BROKER_SELECTION,
        legacy_limit_usd=COINBASE_MAX_LIVE_ORDER_USD,
    )
BROKER_VALIDATION_DISPLAY = broker_validation_display(
    selected_broker=SELECTED_BROKER,
    broker_mode=SELECTED_BROKER_MODE,
    readiness={
        **COINBASE_READ_ONLY_STATUS,
        "broker_execution_armed": BROKER_EXECUTION_ARMED,
    },
    env=os.environ,
)
COINBASE_READ_ONLY_STATUS.update(BROKER_VALIDATION_DISPLAY)
if (
    SELECTED_BROKER == "COINBASE"
    and SELECTED_BROKER_MODE == "paper"
    and COINBASE_LIVE_CONFIRMATION_STATUS.get("reason") == "coinbase_live_confirmation_missing_or_invalid"
):
    COINBASE_READ_ONLY_STATUS["auth_reason"] = str(COINBASE_LIVE_CONFIRMATION_STATUS["reason"])
    COINBASE_READ_ONLY_STATUS["execution_scope"] = "PAPER_FALLBACK_AFTER_INVALID_LIVE_CONFIRMATION"
def pcnrass_update_authoritative_broker_state(val_data: dict[str, Any], validation_source: str) -> None:
    global COINBASE_READ_ONLY_STATUS
    if not val_data:
        return
        
    status = val_data.get("validation_status", "FAIL_CLOSED")
    is_success = (status == "PASS")
    
    # Base connection & auth fields
    COINBASE_READ_ONLY_STATUS["broker_connected"] = bool(val_data.get("api_reachable", False))
    COINBASE_READ_ONLY_STATUS["broker_authenticated"] = bool(val_data.get("authenticated", False))
    COINBASE_READ_ONLY_STATUS["credential_status"] = "PASS" if is_success else "FAIL"
    COINBASE_READ_ONLY_STATUS["auth_status"] = "PASS" if val_data.get("authenticated") else "FAIL"
    COINBASE_READ_ONLY_STATUS["connection_status"] = "PASS" if val_data.get("api_reachable") else "FAIL"
    COINBASE_READ_ONLY_STATUS["account_loaded"] = bool(val_data.get("account_loaded", False))
    COINBASE_READ_ONLY_STATUS["balances_loaded"] = bool(val_data.get("balances_loaded", False))
    COINBASE_READ_ONLY_STATUS["market_data_loaded"] = bool(val_data.get("market_data_loaded", False))
    COINBASE_READ_ONLY_STATUS["products_loaded"] = int(val_data.get("products_loaded", 0))
    COINBASE_READ_ONLY_STATUS["market_data_status"] = "OK" if val_data.get("market_data_loaded") else "FAIL"
    
    failures = val_data.get("failure_reasons", [])
    COINBASE_READ_ONLY_STATUS["connection_error"] = ", ".join([f.get("message", "") for f in failures]) if failures else ""
    
    # Freshness metadata
    COINBASE_READ_ONLY_STATUS["generated_at"] = val_data.get("validation_timestamp", datetime.now(timezone.utc).isoformat())
    COINBASE_READ_ONLY_STATUS["validation_completed"] = True
    COINBASE_READ_ONLY_STATUS["validation_source"] = validation_source
    
    # Sequence tracking
    seq = globals().get("PCNRASS_VALIDATION_SEQUENCE", 0) + 1
    globals()["PCNRASS_VALIDATION_SEQUENCE"] = seq
    COINBASE_READ_ONLY_STATUS["validation_sequence"] = seq
    
    if is_success:
        COINBASE_READ_ONLY_STATUS["last_successful_validation_at"] = val_data.get("validation_timestamp", datetime.now(timezone.utc).isoformat())
        COINBASE_READ_ONLY_STATUS["readiness_state"] = "FULLY_OPERATIONAL"
        COINBASE_READ_ONLY_STATUS["go_no_go"] = "GO"
    else:
        COINBASE_READ_ONLY_STATUS["readiness_state"] = "FAIL_CLOSED"
        COINBASE_READ_ONLY_STATUS["go_no_go"] = "NO GO"
        # Clear/None-out fields to prevent stale-success leakage
        COINBASE_READ_ONLY_STATUS["account_equity"] = None
        COINBASE_READ_ONLY_STATUS["cash"] = None
        COINBASE_READ_ONLY_STATUS["buying_power"] = None
        COINBASE_READ_ONLY_STATUS["available_balance"] = None
        
    op_status = val_data.get("broker_operational_status", {})
    if op_status and is_success:
        COINBASE_READ_ONLY_STATUS["account_equity"] = op_status.get("equity", 0.0)
        COINBASE_READ_ONLY_STATUS["cash"] = op_status.get("cash", 0.0)
        COINBASE_READ_ONLY_STATUS["buying_power"] = op_status.get("buying_power", 0.0)
        COINBASE_READ_ONLY_STATUS["available_balance"] = op_status.get("available_balance", 0.0)
    inferred_broker = str(
        val_data.get("broker")
        or COINBASE_READ_ONLY_STATUS.get("selected_broker")
        or ("OANDA" if "OANDA" in str(validation_source).upper() else "COINBASE")
    )
    inferred_mode = str(val_data.get("mode") or COINBASE_READ_ONLY_STATUS.get("broker_mode") or "live")
    COINBASE_READ_ONLY_STATUS["selected_broker"] = inferred_broker.upper()
    COINBASE_READ_ONLY_STATUS["broker"] = inferred_broker.upper()
    COINBASE_READ_ONLY_STATUS["broker_mode"] = inferred_mode.lower()
    canonical = build_canonical_broker_runtime_state(
        broker=inferred_broker,
        mode=inferred_mode,
        runtime_payload=COINBASE_READ_ONLY_STATUS,
        certification=val_data,
        env=val_data.get("env") if isinstance(val_data.get("env"), dict) else {},
        source_modules=(
            "scripts.css_live_dashboard",
            validation_source,
        ),
    )
    COINBASE_READ_ONLY_STATUS["canonical_broker_runtime_state"] = canonical.to_dict()
    COINBASE_READ_ONLY_STATUS["overall_status"] = canonical.overall_status
    COINBASE_READ_ONLY_STATUS["state_hash"] = canonical.stable_hash()
    COINBASE_READ_ONLY_STATUS.update(
        adapt_canonical_state_to_legacy_broker_payload(
            canonical,
            base_payload=COINBASE_READ_ONLY_STATUS,
        )
    )
    COINBASE_READ_ONLY_STATUS["credential_status"] = "PASS" if canonical.credential_status == "PASS" else "FAIL"
    COINBASE_READ_ONLY_STATUS["auth_status"] = "PASS" if canonical.authentication_status == "PASS" else "FAIL"
    COINBASE_READ_ONLY_STATUS["connection_status"] = "PASS" if canonical.connection_status == "PASS" else "FAIL"
    if failures:
        COINBASE_READ_ONLY_STATUS["connection_error"] = ", ".join([str(f.get("message", "")) for f in failures if isinstance(f, dict)])
    elif canonical.failure_reason == "NO_FAILURE":
        COINBASE_READ_ONLY_STATUS["connection_error"] = ""

if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live":
    COINBASE_OPERATIONAL_VALIDATION = validate_coinbase_live_read_only_operational(
        artifacts_dir=ARTIFACTS_DIR,
    )
    COINBASE_READ_ONLY_STATUS["coinbase_live_validation"] = COINBASE_OPERATIONAL_VALIDATION
    pcnrass_update_authoritative_broker_state(COINBASE_OPERATIONAL_VALIDATION, "COINBASE_LIVE_VALIDATOR")
elif SELECTED_BROKER == "OANDA" and SELECTED_BROKER_MODE == "live":
    OANDA_OPERATIONAL_VALIDATION = validate_oanda_live_read_only_operational(
        artifacts_dir=ARTIFACTS_DIR,
    )
    COINBASE_READ_ONLY_STATUS["oanda_live_validation"] = OANDA_OPERATIONAL_VALIDATION
    pcnrass_update_authoritative_broker_state(OANDA_OPERATIONAL_VALIDATION, "OANDA_LIVE_VALIDATOR")
if SELECTED_BROKER == "OANDA":
    STARTUP_BROKER_SELECTION = selection_with_oanda_readiness(
        STARTUP_BROKER_SELECTION,
        COINBASE_READ_ONLY_STATUS,
    )
    STARTUP_BROKER_STATE = merge_oanda_readiness_into_broker_state(
        STARTUP_BROKER_SELECTION,
        COINBASE_READ_ONLY_STATUS,
    )
else:
    STARTUP_BROKER_SELECTION = selection_with_coinbase_readiness(
        STARTUP_BROKER_SELECTION,
        COINBASE_READ_ONLY_STATUS,
    )
    STARTUP_BROKER_STATE = merge_readiness_into_broker_state(
        STARTUP_BROKER_SELECTION,
        COINBASE_READ_ONLY_STATUS,
    )
STARTUP_BROKER_STATE["broker_parity"] = broker_parity_payload(STARTUP_BROKER_STATE)
try:
    pcnrass_session_state.update(
        {
            "selected_broker": SELECTED_BROKER,
            "broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "broker_execution_armed": BROKER_EXECUTION_ARMED,
            "broker_execution_enabled": False,
            "operator_requested_live": bool(getattr(STARTUP_WIZARD_STATE, "operator_requested_live", False)),
            "execution_authority": False,
            "authority_reason": STARTUP_BROKER_STATE.get("authority_reason", "Operator Intent Missing"),
            "live_authority_state": STARTUP_BROKER_STATE.get("live_authority_state", "BLOCKED"),
            "broker_state": STARTUP_BROKER_STATE,
        }
    )
    pcnrass_account_state.update(
        {
            "selected_broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "broker_execution_armed": BROKER_EXECUTION_ARMED,
            "broker_execution_enabled": False,
            "operator_requested_live": bool(getattr(STARTUP_WIZARD_STATE, "operator_requested_live", False)),
            "execution_authority": False,
            "authority_reason": STARTUP_BROKER_STATE.get("authority_reason", "Operator Intent Missing"),
            "live_authority_state": STARTUP_BROKER_STATE.get("live_authority_state", "BLOCKED"),
            "broker_state": STARTUP_BROKER_STATE,
        }
    )
    persist_broker_selection(
        account_state_path=ACCOUNT_STATE_FILE,
        session_state_path=SESSION_STATE_FILE,
        selection=STARTUP_BROKER_SELECTION,
        broker_state_override=STARTUP_BROKER_STATE,
    )
except Exception as exc:
    print(f"[BROKER STARTUP PERSIST WARN] {exc}")

print("\n=== STARTUP DIAGNOSTICS ===")
print(f"Working Directory    : {os.getcwd()}")
print(f"Project Root         : {PROJECT_ROOT}")
print(f"Selected Broker      : {SELECTED_BROKER}")
print(f"Selected Broker Mode : {SELECTED_BROKER_MODE}")

env_file = PROJECT_ROOT / ".env"
print(f".env file used       : {env_file}")

dotenv_loaded = "NO"
if env_file.exists():
    dotenv_loaded = "YES"
print(f"Environment Loaded   : {dotenv_loaded}")

# Credential Source
source = "NONE"
if SELECTED_BROKER != "NONE":
    try:
        from backend.app.brokers.broker_registry import get_broker_spec
        spec = get_broker_spec(SELECTED_BROKER)
        if spec and os.path.exists(os.path.join(".", spec.credential_file)):
            source = f"FILE ({spec.credential_file})"
        else:
            source = "DOTENV (.env)"
    except Exception:
        source = "DOTENV (.env)"
print(f"Credential Source    : {source}")

# Credential Status, Authentication Status, and Bootstrap Result
cred_status = "MISSING"
auth_status = "NOT_TESTED"
bootstrap_result = "FAIL"

if SELECTED_BROKER != "NONE":
    readiness = globals().get("COINBASE_READ_ONLY_STATUS", {})
    readiness = readiness if isinstance(readiness, dict) else {}
    canonical = readiness.get("canonical_broker_runtime_state")
    canonical = canonical if isinstance(canonical, dict) else {}
    if canonical:
        cred_status = str(canonical.get("credential_status", "UNKNOWN"))
        auth_status = str(canonical.get("authentication_status", "UNKNOWN"))
        bootstrap_result = str(canonical.get("overall_status", "FAIL_CLOSED"))
    else:
        from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials
        diag = diagnose_broker_credentials(SELECTED_BROKER.lower())
        if diag.credentials_present:
            cred_status = "FOUND"
        else:
            cred_status = "INVALID" if diag.failure_reason in ("KEY_MISSING", "SECRET_MISSING", "PEM_INVALID", "TOKEN_INVALID", "ACCOUNT_ID_MISSING") else "MISSING"
else:
    cred_status = "N/A"
    auth_status = "N/A"
    bootstrap_result = "N/A"
    
print(f"Credential Status    : {cred_status}")
print(f"Authentication Status: {auth_status}")
print(f"Bootstrap Result     : {bootstrap_result}")
if SELECTED_BROKER != "NONE" and isinstance(globals().get("COINBASE_READ_ONLY_STATUS", {}), dict):
    canonical = COINBASE_READ_ONLY_STATUS.get("canonical_broker_runtime_state", {})
    if isinstance(canonical, dict) and canonical:
        print(f"Canonical State Hash : {canonical.get('state_hash', 'UNKNOWN')}")
        print(f"Status Provenance    : {canonical.get('status_provenance', 'UNKNOWN')}")
print("===========================\n")

import sys
from backend.app.security.environment_validator import validate_startup_security_environment, EnvironmentValidationError

print("\n=== SECURITY STATUS ===")
try:
    sec_status = validate_startup_security_environment(SELECTED_BROKER, SELECTED_BROKER_MODE)
    print(f"ENVIRONMENT VALID: {'YES' if sec_status['ENVIRONMENT_VALID'] else 'NO'}")
    print(f"BROKER CONFIG VALID: {'YES' if sec_status['BROKER_CONFIG_VALID'] else 'NO'}")
    print(f"LIVE/PRACTICE CONSISTENT: {'YES' if sec_status['LIVE_PRACTICE_CONSISTENT'] else 'NO'}")
    print(f"SECRET VALIDATION PASSED: {'YES' if sec_status['SECRET_VALIDATION_PASSED'] else 'NO'}")
    print("=======================\n")
except EnvironmentValidationError as e:
    print(f"ENVIRONMENT VALID: NO")
    print(f"BROKER CONFIG VALID: NO")
    print(f"LIVE/PRACTICE CONSISTENT: NO")
    print(f"SECRET VALIDATION PASSED: NO")
    print(f"[FATAL SECURITY ERROR] {str(e)}")
    print("=======================\n")
    if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live" and not BROKER_EXECUTION_ARMED:
        print(
            "[COINBASE READ-ONLY WARNING] Credential validation failed; "
            "runtime remains read-only with broker execution disabled."
        )
    else:
        sys.exit(1)

ENGINE_MODE = select_engine_mode()
select_cycle_mode()
confirm_startup_summary_before_runtime()
print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")



record_startup_configuration(
    user_ctx=SESSION_USER_CTX,
    broker_execution_armed=BROKER_EXECUTION_ARMED,
    selected_broker=SELECTED_BROKER,
    selected_broker_mode=SELECTED_BROKER_MODE,
    engine_mode=ENGINE_MODE,
)

_IN_FLIGHT_ORDERS = set()

def register_in_flight_order(order_id: str) -> None:
    _IN_FLIGHT_ORDERS.add(order_id)

def clear_in_flight_order(order_id: str) -> None:
    _IN_FLIGHT_ORDERS.discard(order_id)

def has_in_flight_orders() -> bool:
    return len(_IN_FLIGHT_ORDERS) > 0

_DIVERGENCE_STATE = {
    "first_detected": None,
    "count": 0,
    "type": None,
    "last_simulation": None,
    "confirmed_count": 0,
    "pending_count": 0
}

def simulate_auto_flatten(divergences: list[tuple[str, str]]) -> None:
    global _CSS_SESSION_LOCK, _DIVERGENCE_STATE
    if not is_session_locked():
        lock_session("PENDING_AUTO_FLATTEN")
    else:
        # Override the reason if it was locked by the generic RECONCILIATION_DIVERGENCE
        if _CSS_SESSION_LOCK.get("reason") == "RECONCILIATION_DIVERGENCE":
            _CSS_SESSION_LOCK["reason"] = "PENDING_AUTO_FLATTEN"

    for cat, det in divergences:
        if cat in {"ORPHAN_BROKER_POSITION", "BROKER_POSITION_MISMATCH"}:
            symbol = "UNKNOWN"
            broker_units = 0.0
            ledger_units = 0.0
            
            try:
                if isinstance(det, dict):
                    symbol = det.get("symbol", "UNKNOWN")
                    b_data = det.get("broker_data", {})
                    # Handle OANDA specific format or plain units
                    if isinstance(b_data, dict):
                        if "units" in b_data:
                            broker_units = float(b_data["units"])
                        elif "long" in b_data and "units" in b_data["long"]:
                            broker_units += float(b_data["long"]["units"])
                        elif "short" in b_data and "units" in b_data["short"]:
                            broker_units += float(b_data["short"]["units"])
                    
                    l_data = det.get("local_data", {})
                    if isinstance(l_data, dict):
                        ledger_units = float(l_data.get("quantity", 0.0))
            except Exception:
                pass
            
            delta = broker_units - ledger_units
            action = "SELL" if delta > 0 else "BUY"
            action_qty = abs(delta)

            sim_output = (
                f"[AUTO-FLATTEN SIMULATION]\n"
                f"symbol={symbol}\n"
                f"broker_units={broker_units}\n"
                f"ledger_units={ledger_units}\n"
                f"delta={delta}\n"
                f"proposed_action={action} {action_qty}\n"
                f"status=SIMULATED_ONLY"
            )
            print(sim_output)
            _DIVERGENCE_STATE["last_simulation"] = sim_output
            _DIVERGENCE_STATE["pending_count"] += 1
            
            repair_engine.create_record(cat, sim_output)
            if repair_engine.records:
                last_record = repair_engine.records[-1]
                last_record["status"] = "AUTO_FLATTEN_SIMULATED"
                repair_engine.save_records()



# === R7 PCNRASS UNIFIED TRADE GATE ===
from backend.governance.css_gate_dashboard_adapter import CSSGateDashboardAdapter
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate as BackendCSSUnifiedTradeGate


css_unified_trade_gate = CSSGateDashboardAdapter(
    BackendCSSUnifiedTradeGate()
)


def _dashboard_portfolio_state_for_gate() -> dict[str, int]:
    try:
        counts = mtm_engine.count_open_positions_by_asset()
    except Exception:
        counts = {}

    return {
        "crypto": int(counts.get("CRYPTO", counts.get("crypto", 0)) or 0),
        "fx": int(counts.get("FX", counts.get("fx", 0)) or 0),
        "futures": int(counts.get("FUTURES", counts.get("futures", 0)) or 0),
        "options": int(counts.get("OPTIONS", counts.get("options", 0)) or 0),
    }


def approve_trade_before_register(asset_class: str, symbol: str, sig: float, prob: float) -> tuple[bool, str]:
    session = SESSION_USER_CTX
    role_profile = SESSION_USER_CTX.get("role_profile", {})
    portfolio_state = _dashboard_portfolio_state_for_gate()

    decision = css_unified_trade_gate.approve_trade(
        candidate={
            "asset_class": asset_class,
            "symbol": symbol,
            "signal_score": sig,
            "prob_positive": prob,
            "selected_broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "engine_mode": ENGINE_MODE,
            "is_session_locked": is_session_locked(),
        },
        session=session,
        role_profile=role_profile,
        portfolio_state=portfolio_state,
        engine_mode=ENGINE_MODE,
    )

    if not decision.get("approved", False):
        try:
            _safe_emit_alert(
                "emit_risk_alert",
                severity=AlertSeverity.WARNING,
                message=f"Trade blocked by unified gate: {asset_class} {symbol} ({decision.get('reason')})",
                metadata={"asset": asset_class, "symbol": symbol, "reason": decision.get("reason")}
            )
            audit_ledger.record(
                "unified_trade_gate_reject",
                str(SESSION_USER_CTX.get("user_id")),
                {
                    "session_id": SESSION_USER_CTX.get("session_id"),
                    "asset_class": asset_class,
                    "symbol": symbol,
                    "reason": decision.get("reason"),
                    "selected_broker": SELECTED_BROKER,
                    "broker_mode": SELECTED_BROKER_MODE,
                    "engine_mode": ENGINE_MODE,
                },
            )
        except Exception:
            pass

        print(f"[UNIFIED GATE BLOCKED] {asset_class} {symbol} | {decision.get('reason')}")
        return False, str(decision.get("reason"))

    return True, str(decision.get("reason"))


class AdaptiveConcurrencyEnvelopeController:
    def __init__(self) -> None:
        self.current_limit = HARD_TOTAL_OPEN_POSITION_CAP
        self.max_limit = HARD_TOTAL_OPEN_POSITION_CAP
        self.min_limit = HARD_TOTAL_OPEN_POSITION_CAP

    def evaluate_limit(
        self,
        open_positions: int,
        cluster_pct: float,
        unrealized_pnl: float,
    ) -> int:
        if (
            cluster_pct < 20.0
            and unrealized_pnl > 0.0
            and open_positions < self.current_limit * 0.75
        ):
            self.current_limit = min(self.current_limit + 50, self.max_limit)
        elif (
            cluster_pct > 35.0
            or unrealized_pnl < -50.0
            or open_positions > self.current_limit * 0.95
        ):
            self.current_limit = max(self.current_limit - 25, self.min_limit)

        return self.current_limit

    def can_add_position(self, open_positions: int) -> bool:
        return open_positions < self.current_limit


concurrency_controller = AdaptiveConcurrencyEnvelopeController()


class CapitalDeploymentGovernor:
    """
    PCNRASS R1 UPGRADE:
    Dynamic capital source:
    - PAPER mode keeps controlled simulated test capital.
    - LIVE mode attempts broker-fetched account balance through RealBalanceEngine.
    - Fail-closed: if real balance fetch fails, available live capital becomes 0.0.
    """

    def __init__(self) -> None:
        self.paper_mode = True
        self.simulated_capital_pool = 200.00
        self.max_capital_per_trade = 25.00
        self.max_broker_test_positions = 5
        self.active_test_allocations: dict[str, float] = {}
        self.real_balance = 0.0
        self.real_equity = 0.0
        self.balance_source = "SIMULATED"
        self.balance_snapshot: dict[str, Any] = {
            "capital_state": "SIMULATED_CAPITAL_READY",
            "drawdown_status": "COMPUTED",
            "drawdown_reason": "",
            "trade_gate_decision": "ALLOW",
            "trade_gate_reason": "CAPITAL_READY",
            "live_execution_authority": "NOT_EVALUATED",
            "source": "SIMULATED",
        }

    def _get_adapter(self):
        try:
            if str(SELECTED_BROKER).upper() == "OANDA":
                return oanda
            if str(SELECTED_BROKER).upper() == "COINBASE":
                return coinbase
        except Exception:
            return None
        return None

    def refresh_real_balance(self) -> dict:
        try:
            from backend.app.accounting.real_balance_engine import RealBalanceEngine

            engine = RealBalanceEngine(SELECTED_BROKER, self._get_adapter())
            data = engine.get_balance()

            self.real_balance = float(data.get("balance", 0.0) or 0.0)
            self.real_equity = float(data.get("equity", self.real_balance) or 0.0)
            self.balance_source = str(data.get("source", "UNKNOWN"))
            self.balance_snapshot = dict(data)

            print(
                f"[REAL BALANCE LOADED] broker={SELECTED_BROKER} "
                f"mode={SELECTED_BROKER_MODE} balance=${self.real_balance:,.2f} "
                f"equity=${self.real_equity:,.2f} source={self.balance_source}"
            )

            return data

        except Exception as e:
            self.real_balance = 0.0
            self.real_equity = 0.0
            self.balance_source = f"REAL_BALANCE_ERROR_{str(e)[:40]}"
            self.balance_snapshot = {
                "balance": None,
                "equity": None,
                "source": self.balance_source,
                "capital_state": "BROKER_BALANCE_UNAVAILABLE",
                "drawdown_status": "NOT_COMPUTABLE",
                "drawdown_reason": "Broker balance unavailable",
                "trade_gate_decision": "BLOCK",
                "trade_gate_reason": "CAPITAL_STATE_UNAVAILABLE",
                "live_execution_authority": "NO",
            }
            print(f"[REAL BALANCE ERROR] {str(e)[:80]}")
            return dict(self.balance_snapshot)

    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())

        if self.paper_mode:
            try:
                base_capital = float(pnl_observer.equity())
            except Exception:
                try:
                    base_capital = float(pnl_observer.current_balance)
                except Exception:
                    base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)

    def capital_source_label(self) -> str:
        if self.paper_mode:
            return "SIMULATED"
        return self.balance_source or f"REAL_BROKER_{SELECTED_BROKER}"

    def can_fund_trade(self, position_id: str) -> bool:
        if self.paper_mode:
            return False
        if position_id in self.active_test_allocations:
            return False
        if len(self.active_test_allocations) >= self.max_broker_test_positions:
            return False
        if self.available_capital() < self.max_capital_per_trade:
            return False
        return True

    def allocate_trade(self, position_id: str) -> bool:
        if not self.can_fund_trade(position_id):
            return False
        self.active_test_allocations[position_id] = self.max_capital_per_trade
        return True

    def release_trade(self, position_id: str) -> None:
        if position_id in self.active_test_allocations:
            del self.active_test_allocations[position_id]

    def live_positions_count(self) -> int:
        return len(self.active_test_allocations)

    def funded_amount(self) -> float:
        return round(sum(self.active_test_allocations.values()), 4)

    def set_live_mode(self) -> None:
        self.paper_mode = False
        _safe_emit_alert(
            "emit_risk_alert",
            severity=AlertSeverity.INFO,
            message="Capital Governor armed for LIVE mode execution",
            metadata={"capital_source": self.capital_source_label()}
        )
        self.refresh_real_balance()

    def set_paper_mode(self) -> None:
        self.paper_mode = True
        self.balance_source = "SIMULATED"
        self.balance_snapshot = {
            "balance": float(self.simulated_capital_pool),
            "equity": float(self.simulated_capital_pool),
            "source": "SIMULATED",
            "capital_state": "SIMULATED_CAPITAL_READY",
            "drawdown_status": "COMPUTED",
            "drawdown_reason": "",
            "trade_gate_decision": "ALLOW",
            "trade_gate_reason": "CAPITAL_READY",
            "live_execution_authority": "NOT_EVALUATED",
        }


capital_governor = CapitalDeploymentGovernor()

# Phase 1 PnL observer only
pnl_observer = Portfolio(
    starting_balance=capital_governor.simulated_capital_pool,
    current_balance=capital_governor.simulated_capital_pool,
)

# === INITIALIZE NEW TRACKER ===
pnl_tracker = PnLTracker(starting_equity=pnl_observer.starting_balance)


def map_oanda_env() -> None:
    if not os.getenv("OANDA_API_KEY"):
        if os.getenv("OANDA_API_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_API_TOKEN", "")
        elif os.getenv("OANDA_PRACTICE_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_PRACTICE_TOKEN", "")
        elif os.getenv("OANDA_LIVE_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_LIVE_TOKEN", "")

    if not os.getenv("OANDA_ACCOUNT_ID"):
        if os.getenv("OANDA_PRACTICE_ACCOUNT_ID"):
            os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_PRACTICE_ACCOUNT_ID", "")
        elif os.getenv("OANDA_LIVE_ACCOUNT_ID"):
            os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_LIVE_ACCOUNT_ID", "")

    if not os.getenv("OANDA_BASE_URL"):
        env_mode = (os.getenv("OANDA_ENV") or "practice").strip().lower()
        if env_mode == "live":
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"
        else:
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
map_oanda_env()
oanda = OandaAdapter()

coinbase: Optional[Any] = None

coinbase_live_gate = CoinbaseLiveOrderGate(
    approved_symbols=SYMBOLS,
    max_order_usd=COINBASE_MAX_LIVE_ORDER_USD,
    require_manual_phrase=False,
)

broker_gate_audit = BrokerGateAuditLogger()


def initialize_selected_coinbase() -> None:
    global coinbase

    if not BROKER_EXECUTION_ARMED:
        return

    if SELECTED_BROKER != "COINBASE":
        return

    try:
        coinbase = initialize_broker("coinbase", SELECTED_BROKER_MODE)
        print(f"[COINBASE BOOTSTRAP] Coinbase initialized in {SELECTED_BROKER_MODE} mode")
    except Exception as e:
        coinbase = None
        print(f"[COINBASE BOOTSTRAP ERROR] {str(e)[:100]}")


initialize_selected_coinbase()

# PCNRASS R3: activate correct capital source after broker adapters are initialized.
def pcnrass_activate_capital_source() -> None:
    if str(SELECTED_BROKER_MODE).lower() == "live":
        capital_governor.set_live_mode()
    else:
        capital_governor.set_paper_mode()

    base_capital = capital_governor.available_capital() + capital_governor.funded_amount()

    try:
        pnl_observer.starting_balance = float(base_capital)
        pnl_observer.current_balance = float(base_capital)
    except Exception as e:
        print(f"[CAPITAL SYNC WARN] pnl_observer sync failed: {str(e)[:60]}")

    if str(SELECTED_BROKER_MODE).lower() == "live":
        if float(capital_governor.real_balance or 0.0) <= 0.0:
            print(
                f"[LIVE CAPITAL WARNING] broker={SELECTED_BROKER} "
                f"mode=live endpoint={get_active_broker_url()} "
                f"balance_fetch_failed_or_zero. Live trading must remain blocked until real balance is loaded."
            )

    # === R11 CAPITAL HARD LOCK ===
pcnrass_activate_capital_source()

if str(SELECTED_BROKER_MODE).lower() == "live":
    real_balance = float(getattr(capital_governor, "real_balance", 0.0) or 0.0)

    if real_balance <= 0.0:
        print(
            f"[LIVE CAPITAL BLOCKED] broker={SELECTED_BROKER} "
            f"url={get_active_broker_url()} "
            f"reason=NO_REAL_BALANCE"
        )

        print("[SYSTEM HALT] Live trading disabled until real broker balance is loaded.")
        if BROKER_EXECUTION_ARMED:
            # HARD STOP - prevent fake execution when broker execution is armed.
            import sys
            sys.exit(1)
        print(
            "[LIVE READ-ONLY CONTINUE] Broker execution disabled; "
            "continuing for read-only validation only."
        )

print(
    f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
    f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
)


_legacy_enforce_mode_dominance()
_legacy_enforce_execution_boundary()


# === PCNRASS PHASE 2 BROKER ISOLATION + REAL PRICE HELPERS ===
# Real market pricing only activates when broker execution is ARMED and selected broker mode is LIVE.
# Paper mode remains paper/simulation-safe and must not pull real account capital into trading logic.
def pcnrass_real_market_enabled() -> bool:
    return (
        bool(BROKER_EXECUTION_ARMED)
        and str(SELECTED_BROKER_MODE).lower() == "live"
        and str(SELECTED_BROKER).upper() in {"COINBASE", "OANDA"}
    )


def pcnrass_selected_broker_is(name: str) -> bool:
    return str(SELECTED_BROKER).upper() == str(name).upper()


def pcnrass_get_reference_price(symbol: str, fallback: float = 100.0) -> float:
    if pcnrass_real_market_enabled():
        try:
            px = price_feed.get_price(symbol)
            if px is not None and float(px) > 0:
                return float(px)
        except Exception:
            pass
    return float(fallback)

def resolve_expected_fx_price(symbol: str) -> float | None:
    try:
        px = price_feed.get_price(symbol)
        if px is not None and float(px) > 0:
            return float(px)
    except Exception:
        pass
    return None

def pcnrass_read_mobile_controls() -> dict:
    controls = _pcnrass_read_json(MOBILE_CONTROLS_FILE, {})
    if not isinstance(controls, dict):
        controls = {}

    cycle_mode = str(controls.get("cycle_mode") or os.getenv("CSS_CYCLE_MODE", "")).strip().lower()
    if cycle_mode not in {"manual", "continuous"}:
        cycle_mode = "continuous" if os.getenv("CSS_AUTO_CYCLE", "").lower() in {"true", "1", "yes"} else "manual"

    try:
        interval = int(controls.get("cycle_interval_seconds") or os.getenv("CSS_CYCLE_SLEEP_SECONDS", "60"))
    except Exception:
        interval = 60

    interval = max(5, min(interval, 600))

    return {
        "trading_paused": bool(controls.get("trading_paused", False)),
        "cycle_mode": cycle_mode,
        "cycle_interval_seconds": interval,
        "source": str(controls.get("source", "runtime_default")),
        "timestamp": str(controls.get("timestamp", "")),
        "reason": str(controls.get("reason", "")),
    }


def pcnrass_wait_for_next_cycle(cycle: int) -> bool:
    while True:
        controls = pcnrass_read_mobile_controls()

        if controls["trading_paused"]:
            print(
                f"\n[MOBILE CONTROL PAUSED] Cycle {cycle} paused "
                f"reason={controls.get('reason', '')}. Waiting for resume..."
            )
            time.sleep(5)
            continue

        if controls["cycle_mode"] == "continuous":
            sleep_secs = int(controls["cycle_interval_seconds"])
            print(f"\n[AUTO CYCLE MODE] enabled interval={sleep_secs}s source={controls.get('source', '')}")
            time.sleep(sleep_secs)
            return True

        response = input(
            f"\n[PCNRASS PAUSE] Cycle {cycle} complete. "
            "Press ENTER for next cycle, type C for continuous, or type Q to quit: "
        ).strip().lower()

        if response in {"q", "quit", "exit", "stop"}:
            return False

        if response in {"c", "continuous", "auto"}:
            controls = pcnrass_read_mobile_controls()
            controls["cycle_mode"] = "continuous"
            controls["cycle_interval_seconds"] = int(controls.get("cycle_interval_seconds", 60))
            controls["trading_paused"] = False
            controls["source"] = "runtime_keyboard"
            controls["reason"] = "operator_selected_continuous"
            controls["timestamp"] = _utc_iso_z()
            _pcnrass_write_json(MOBILE_CONTROLS_FILE, controls)
            print("[CYCLE MODE SELECTED] CONTINUOUS")
            continue

        return True

def is_oanda_practice_mode() -> bool:
    base_url = os.getenv("OANDA_BASE_URL", "")
    return "api-fxpractice.oanda.com" in base_url


def get_oanda_open_trade_count() -> int | str:
    try:
        result = oanda.get_open_trades()
        if result.get("ok", False):
            return len(result.get("data", {}).get("trades", []))
        return "ERR"
    except Exception:
        return "ERR"


def oanda_has_open_trade() -> bool:
    count = get_oanda_open_trade_count()
    if isinstance(count, int):
        return count > 0
    return False


def perform_post_trade_verification(trade_id: str, symbol: str, expected_units: str) -> None:
    global RECONCILIATION_STATUS
    try:
        resp = oanda.get_open_trades()
        if not resp.get("ok"):
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("POST_TRADE_VERIFICATION_API_ERROR")
            print(f"[POST-TRADE VERIFICATION ERROR] Failed to fetch open trades: {resp.get('error')}")
            return

        trades = resp.get("data", {}).get("trades", [])
        trade_found = None
        for t in trades:
            if str(t.get("id")) == str(trade_id):
                trade_found = t
                break

        if not trade_found:
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("POST_TRADE_VERIFICATION_MISSING_TRADE")
            print(f"[POST-TRADE VERIFICATION FAILED] Trade {trade_id} missing on broker.")
            return

        instr = trade_found.get("instrument")
        current_units = trade_found.get("currentUnits")
        if instr != symbol or str(current_units) != str(expected_units):
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("POST_TRADE_VERIFICATION_MISMATCH")
            print(f"[POST-TRADE VERIFICATION FAILED] Trade {trade_id} mismatch. Expected {symbol} {expected_units}, got {instr} {current_units}")
            return

        print(f"[POST-TRADE VERIFICATION OK] Trade {trade_id} confirmed on broker.")

    except Exception as e:
        RECONCILIATION_STATUS = "MISMATCH"
        lock_session("POST_TRADE_VERIFICATION_ERROR")
        print(f"[POST-TRADE VERIFICATION EXCEPTION] {e}")


OANDA_MAX_SLIPPAGE = 0.0050

def attempt_oanda_fx_execution(symbol: str, expected_price: float | None = None) -> tuple[bool, str, str | None, float | None, str | None, float | None]:
    role_profile = SESSION_USER_CTX.get("role_profile", {})

    def _audit(allowed: bool, reason: str) -> None:
        broker_gate_audit.log_decision(
            broker="OANDA",
            gate_name="oanda_fx_order_gate",
            allowed=allowed,
            reason=reason,
            symbol=symbol,
            instrument=symbol,
            asset_class="FX",
            size=float(FX_LIVE_UNITS),
            size_unit="UNITS",
            selected_broker=SELECTED_BROKER,
            broker_mode="paper",
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=False,
            extra={
                "practice_mode": is_oanda_practice_mode(),
                "open_trade_count": get_oanda_open_trade_count(),
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
                "defensive_mode_active": is_session_locked(),
            },
        )

    if is_session_locked():
        _audit(False, "SESSION_LOCKED_DEFENSIVE_MODE")
        return False, "SESSION_LOCKED_DEFENSIVE_MODE", None, None, None, None

    if expected_price is None or expected_price <= 0:
        _audit(False, "OANDA_BLOCKED_MISSING_EXPECTED_PRICE")
        return False, "OANDA_BLOCKED_MISSING_EXPECTED_PRICE", None, None, None, None

    if not BROKER_EXECUTION_ARMED:
        _audit(False, "BROKER_DISABLED_BY_GLOBAL_SWITCH")
        return False, "BROKER_DISABLED_BY_GLOBAL_SWITCH", None, None, None, None

    if not role_profile.get("can_execute_paper_trading", False):
        _audit(False, "RBAC_BLOCKED_PAPER_EXECUTION")
        return False, "RBAC_BLOCKED_PAPER_EXECUTION", None, None, None, None

    if SELECTED_BROKER != "OANDA":
        reason = f"BROKER_NOT_SELECTED_FOR_OANDA_{SELECTED_BROKER}"
        _audit(False, reason)
        return False, reason, None, None, None, None

    if ENGINE_MODE == "SAFE":
        _audit(False, "OANDA_BLOCKED_SAFE_MODE")
        return False, "OANDA_BLOCKED_SAFE_MODE", None, None, None, None

    if symbol not in FX_SYMBOLS:
        _audit(False, "OANDA_BLOCKED_NOT_FX")
        return False, "OANDA_BLOCKED_NOT_FX", None, None, None, None

    if oanda_has_open_trade():
        _audit(False, "OANDA_BLOCKED_OPEN_TRADE")
        return False, "OANDA_BLOCKED_OPEN_TRADE", None, None, None, None

    try:
        price_bound_val = str(expected_price + OANDA_MAX_SLIPPAGE) if expected_price is not None else None
        response = oanda.place_order(
            symbol=symbol,
            side="BUY",
            units=FX_LIVE_UNITS,
            order_type="MARKET",
            price_bound=price_bound_val,
            # â”€â”€ Live firewall parameters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # broker_mode: SELECTED_BROKER_MODE is the operator-confirmed mode
            # (paper or live) already validated by select_broker_execution_config().
            broker_mode=str(SELECTED_BROKER_MODE).lower(),
            # broker_execution_armed: BROKER_EXECUTION_ARMED global, set at startup
            # by the operator arming sequence and verified by the check above.
            broker_execution_armed=BROKER_EXECUTION_ARMED,
            # governance_approved: role_profile.can_execute_live_trading has already
            # been checked for live mode; grant approval only when that flag is set.
            governance_approved=role_profile.get("can_execute_live_trading", False),
            # controls: no mobile controls artifact sourced in this code path; the
            # kill-switch is enforced via env var (CSS_LIVE_ORDER_KILL_SWITCH).
            controls={},
            # user_context: SESSION_USER_CTX holds the authenticated operator session.
            user_context=SESSION_USER_CTX,
        )

        if response.get("ok"):
            _audit(True, "OANDA_ORDER_OK")
            data = response.get("data", {})
            fill_txn = data.get("orderFillTransaction", {})
            trade_opened = fill_txn.get("tradeOpened", {})
            trade_id = trade_opened.get("tradeID")
            price_str = fill_txn.get("price")
            fill_price = float(price_str) if price_str else None
            execution_time = fill_txn.get("time")

            slippage = None
            if fill_price is not None and expected_price is not None:
                slippage = fill_price - expected_price
                print(f"[{symbol} SLIPPAGE AUDIT] Expected: {expected_price:.4f}, Actual: {fill_price:.4f}, Slippage: {slippage:.4f}")

            return True, "OANDA_ORDER_OK", trade_id, fill_price, execution_time, slippage

        # If OANDA rejects it due to price bound, fail closed.
        resp_status = response.get("status")
        resp_str = str(response)
        if resp_status == 400 and "PRICE_BOUND" in resp_str:
            lock_session("OANDA_SLIPPAGE_REJECTION")
            reason = "OANDA_ORDER_FAIL_PRICE_BOUND_EXCEEDED"
            _audit(False, reason)
            return False, reason, None, None, None, None

        reason = f"OANDA_ORDER_FAIL_{resp_status}"
        _audit(False, reason)
        return False, reason, None, None, None, None

    except Exception as e:
        reason = f"OANDA_ERROR_{str(e)[:40]}"
        _audit(False, reason)
        return False, reason, None, None, None, None


def coinbase_live_orders_enabled() -> bool:
    return (os.getenv("COINBASE_ENABLE_LIVE_ORDERS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _coinbase_response_ok(response: Any) -> tuple[bool, str]:
    if not isinstance(response, dict):
        return False, "NON_DICT_RESPONSE"

    status = str(response.get("status") or response.get("order_status") or "").lower()

    if status in {"paper_filled", "filled", "done", "success"}:
        return True, status.upper()

    if response.get("ok") is True or response.get("success") is True:
        return True, "OK_TRUE"

    success_response = response.get("success_response")
    if isinstance(success_response, dict):
        return True, "SUCCESS_RESPONSE"

    error_response = response.get("error_response")
    if isinstance(error_response, dict):
        msg = (
            error_response.get("message")
            or error_response.get("error")
            or str(error_response)[:60]
        )
        return False, str(msg)[:60]

    err = response.get("error") or response.get("message") or status or "UNKNOWN_RESPONSE"
    return False, str(err)[:60]


def evaluate_coinbase_live_gate(symbol: str, size_usd: float):
    if is_session_locked():
        broker_gate_audit.log_decision(
            broker="COINBASE",
            gate_name="coinbase_live_order_gate",
            allowed=False,
            reason="SESSION_LOCKED_DEFENSIVE_MODE",
            symbol=symbol,
            instrument=symbol,
            asset_class="CRYPTO",
            size=float(size_usd),
            size_unit="USD",
            selected_broker=SELECTED_BROKER,
            broker_mode=SELECTED_BROKER_MODE,
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=coinbase_live_orders_enabled(),
            extra={
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
            },
        )
        return False, "SESSION_LOCKED_DEFENSIVE_MODE"

    if SELECTED_BROKER_MODE != "live":
        broker_gate_audit.log_decision(
            broker="COINBASE",
            gate_name="coinbase_live_order_gate",
            allowed=True,
            reason="COINBASE_PAPER_MODE_GATE_BYPASS",
            symbol=symbol,
            instrument=symbol,
            asset_class="CRYPTO",
            size=float(size_usd),
            size_unit="USD",
            selected_broker=SELECTED_BROKER,
            broker_mode=SELECTED_BROKER_MODE,
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=coinbase_live_orders_enabled(),
            extra={
                "note": "paper mode bypass",
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
            },
        )
        return True, "COINBASE_PAPER_MODE_GATE_BYPASS"

    result = coinbase_live_gate.evaluate(
        broker_execution_armed=BROKER_EXECUTION_ARMED,
        selected_broker=SELECTED_BROKER,
        broker_mode=SELECTED_BROKER_MODE,
        engine_mode=ENGINE_MODE,
        symbol=symbol,
        size_usd=float(size_usd),
        coinbase_adapter=coinbase,
    )

    broker_gate_audit.log_decision(
        broker="COINBASE",
        gate_name="coinbase_live_order_gate",
        allowed=result.allowed,
        reason=result.reason,
        symbol=symbol,
        instrument=symbol,
        asset_class="CRYPTO",
        size=float(size_usd),
        size_unit="USD",
        selected_broker=SELECTED_BROKER,
        broker_mode=SELECTED_BROKER_MODE,
        engine_mode=ENGINE_MODE,
        execution_armed=BROKER_EXECUTION_ARMED,
        live_orders_flag=coinbase_live_orders_enabled(),
        extra={
            "max_live_order_usd": COINBASE_MAX_LIVE_ORDER_USD,
            "account_count_hint": 9
            if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live"
            else None,
            "session_user_id": SESSION_USER_CTX.get("user_id"),
            "session_role": SESSION_USER_CTX.get("role"),
            "session_id": SESSION_USER_CTX.get("session_id"),
        },
    )

    return result.allowed, result.reason


def attempt_coinbase_crypto_execution(symbol: str) -> tuple[bool, str]:
    role_profile = SESSION_USER_CTX.get("role_profile", {})

    if is_session_locked():
        return False, "SESSION_LOCKED_DEFENSIVE_MODE"

    if not BROKER_EXECUTION_ARMED:
        return False, "BROKER_DISABLED_BY_GLOBAL_SWITCH"

    if SELECTED_BROKER != "COINBASE":
        return False, f"BROKER_NOT_SELECTED_FOR_COINBASE_{SELECTED_BROKER}"

    if ENGINE_MODE == "SAFE":
        return False, "COINBASE_BLOCKED_SAFE_MODE"

    if symbol not in SYMBOLS:
        return False, "COINBASE_BLOCKED_NOT_CRYPTO"

    if coinbase is None:
        return False, "COINBASE_NOT_INITIALIZED"

    if SELECTED_BROKER_MODE == "live" and not role_profile.get("can_execute_live_trading", False):
        return False, "RBAC_BLOCKED_LIVE_EXECUTION"

    if SELECTED_BROKER_MODE != "live" and not role_profile.get("can_execute_paper_trading", False):
        return False, "RBAC_BLOCKED_PAPER_EXECUTION"

    gate_ok, gate_reason = evaluate_coinbase_live_gate(
        symbol=symbol,
        size_usd=float(COINBASE_TEST_ORDER_USD),
    )

    if not gate_ok:
        return False, f"COINBASE_LIVE_GATE_BLOCKED_{gate_reason}"

    if not hasattr(coinbase, "place_market_buy"):
        return False, "COINBASE_ADAPTER_MISSING_PLACE_MARKET_BUY"

    try:
        response = coinbase.place_market_buy(
            product_id=symbol,
            size_usd=float(COINBASE_TEST_ORDER_USD),
        )

        ok, note = _coinbase_response_ok(response)
        if ok:
            return True, f"COINBASE_ORDER_OK_{SELECTED_BROKER_MODE.upper()}_{note}"

        return False, f"COINBASE_ORDER_FAIL_{note}"

    except Exception as e:
        return False, f"COINBASE_ERROR_{str(e)[:40]}"


class SessionRecoveryEngine:
    def __init__(self) -> None:
        self.state_file = STATE_FILE

    def save_state(
        self,
        *,
        cycle: int,
        crypto_pnl: dict,
        fx_pnl: dict,
        options_pnl: dict,
        futures_pnl: dict,
        last_trade: str,
        position_counter: int,
    ) -> None:
        payload = {
            "cycle": cycle,
            "crypto_pnl": crypto_pnl,
            "fx_pnl": fx_pnl,
            "options_pnl": options_pnl,
            "futures_pnl": futures_pnl,
            "last_trade": last_trade,
            "position_counter": position_counter,
            "session_user_ctx": SESSION_USER_CTX,
            "selected_broker": SELECTED_BROKER,
            "selected_broker_mode": SELECTED_BROKER_MODE,
            "engine_mode": ENGINE_MODE,
            "session_lock_state": get_session_lock_state(),
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def load_state(self):
        if RESET_SESSION_ON_BOOT:
            return None

        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


session_recovery = SessionRecoveryEngine()


class LockedProfitLedger:
    def __init__(self) -> None:
        self.forced_exit_profit_banked = 0.0
        self.priority_exits = 0
        self.recycled_slots = 0
        self.trail_stops_hit = 0
        self.defensive_reduction_exits = 0
        self._booked: set[str] = set()

    def record_forced_exit(self, pid: str, amount: float) -> None:
        if pid in self._booked:
            return

        self._booked.add(pid)
        self.forced_exit_profit_banked += round(amount, 4)
        self.trail_stops_hit += 1

    def record_priority_exit(self) -> None:
        self.priority_exits += 1

    def record_recycled_slot(self) -> None:
        self.recycled_slots += 1

    def record_defensive_reduction_exit(self) -> None:
        self.defensive_reduction_exits += 1


locked_profit_ledger = LockedProfitLedger()


class MomentumClusterAmplifier:
    def __init__(self) -> None:
        self.cluster_map = {
            "CRYPTO_CORE": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "CRYPTO_ALT": ["XRP-USD", "ADA-USD", "DOGE-USD"],
            "FX_MAJOR": ["EUR_USD", "GBP_USD", "EUR_GBP"],
            "FX_YEN": ["USD_JPY", "EUR_JPY", "GBP_JPY"],
            "OPTIONS_INDEX": ["SPY-C", "QQQ-C", "AAPL-C"],
            "FUTURES_INDEX": ["ES", "NQ", "CL"],
        }

        self.cluster_strength: dict[str, float] = defaultdict(float)

    def record_cluster_win(self, symbol: str, pnl: float) -> None:
        if pnl <= 0:
            return

        for cname, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cname] += pnl

    def top_cluster(self) -> str | None:
        if not self.cluster_strength:
            return None

        ranked = sorted(
            self.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[0][0]


cluster_amplifier = MomentumClusterAmplifier()


class ClusterSaturationRiskGovernor:
    def __init__(self) -> None:
        self.cluster_slot_counts: dict[str, int] = defaultdict(int)
        self.total_slots_seen = 0

    def record_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1
            self.total_slots_seen += 1

    def release_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name and self.cluster_slot_counts[cluster_name] > 0:
            self.cluster_slot_counts[cluster_name] -= 1
            self.total_slots_seen = max(0, self.total_slots_seen - 1)

    def cluster_share(self, cluster_name: str | None) -> float:
        if not cluster_name or self.total_slots_seen == 0:
            return 0.0

        return self.cluster_slot_counts[cluster_name] / self.total_slots_seen


cluster_risk_governor = ClusterSaturationRiskGovernor()


class SmartDriftEngine:
    def generate_drift(self, pos: dict) -> float:
        lo, hi = ASSET_DRIFT_PROFILE.get(pos["asset_class"], (-0.05, 0.10))
        base = random.uniform(lo, hi)

        signal_bias = ((pos["signal_score"] - 10.0) / 10.0) * 0.04
        prob_bias = (pos["prob_positive"] - 0.5) * 0.08

        return round(base + signal_bias + prob_bias, 4)


smart_drift_engine = SmartDriftEngine()


class MarkToMarketEngine:
    def __init__(self) -> None:
        self.positions: list[dict] = []
        self.position_counter = 0

    def register_position(
        self,
        asset_class: str,
        symbol: str,
        signal_score: float,
        prob_positive: float,
        allow_live_funding: bool = False,
    ) -> dict:
        self.position_counter += 1
        pid = f"POS-{self.position_counter}"

        cluster_name = None
        for cname, members in cluster_amplifier.cluster_map.items():
            if symbol in members:
                cluster_name = cname
                break

        cluster_risk_governor.record_cluster_slot(cluster_name)

        broker_tested = False
        if allow_live_funding:
            broker_tested = capital_governor.allocate_trade(pid)

        entry_price = pcnrass_get_reference_price(symbol, fallback=100.0)

        position = {
            "position_id": pid,
            "asset_class": asset_class,
            "symbol": symbol,
            "cluster_name": cluster_name,
            "entry_price": float(entry_price),
            "current_price": float(entry_price),
            "floating": 0.0,
            "forced_exit": False,
            "exit_reason": None,
            "age_cycles": 0,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "broker_tested": broker_tested,
            "live_funded": broker_tested,
            "broker_order_ok": False,
            "broker_note": "NO_BROKER_ORDER",
            "session_user_id": SESSION_USER_CTX.get("user_id"),
            "session_role": SESSION_USER_CTX.get("role"),
            "session_id": SESSION_USER_CTX.get("session_id"),
        }

        attach_default_greeks_to_option_position(position)
        strategy_attacher = globals().get("attach_option_strategy_to_position")
        if callable(strategy_attacher):
            strategy_attacher(position)
        self.positions.append(position)
        return position

    def count_open_positions(self) -> int:
        return sum(1 for p in self.positions if not p["forced_exit"])

    def count_open_positions_by_asset(self) -> dict[str, int]:
        counts = {
            "CRYPTO": 0,
            "FX": 0,
            "OPTIONS": 0,
            "FUTURES": 0,
        }

        for pos in self.positions:
            if pos["forced_exit"]:
                continue
            counts[pos["asset_class"]] += 1

        return counts

    def count_open_broker_test_positions(self) -> int:
        return sum(
            1
            for p in self.positions
            if not p["forced_exit"] and p.get("broker_tested", False)
        )

    def count_open_funded_positions(self) -> int:
        return self.count_open_broker_test_positions()

    def floating_by_asset(self, funded_only: bool = False) -> dict[str, float]:
        by_asset = {
            "CRYPTO": 0.0,
            "FX": 0.0,
            "OPTIONS": 0.0,
            "FUTURES": 0.0,
        }

        for pos in self.positions:
            if pos["forced_exit"]:
                continue

            if funded_only and not pos.get("broker_tested", False):
                continue

            by_asset[pos["asset_class"]] += pos["floating"]

        return by_asset
mtm_engine = MarkToMarketEngine()


def hard_position_limit() -> int:
    return HARD_TOTAL_OPEN_POSITION_CAP


def hard_asset_cap(asset_class: str) -> int:
    return HARD_ASSET_OPEN_CAPS.get(asset_class, 0)


def max_new_per_cycle(asset_class: str) -> int:
    return MAX_NEW_PER_CYCLE_BY_ASSET.get(asset_class, 0)


def can_open_position(
    asset_class: str,
    *,
    open_counts: dict[str, int],
    new_counts_this_cycle: dict[str, int],
) -> tuple[bool, str]:
    capital_snapshot = getattr(capital_governor, "balance_snapshot", {})
    capital_state = str(capital_snapshot.get("capital_state", "CAPITAL_UNAVAILABLE"))
    capital_gate = str(capital_snapshot.get("trade_gate_decision", "BLOCK")).upper()
    drawdown_status = str(capital_snapshot.get("drawdown_status", "NOT_COMPUTABLE")).upper()

    if str(SELECTED_BROKER_MODE).lower() == "live" and capital_gate == "BLOCK":
        reason = str(capital_snapshot.get("drawdown_reason", "Capital state unavailable"))
        print(f"[CAPITAL BLOCK] state={capital_state} reason={reason}")
        return False, "CAPITAL_STATE_UNAVAILABLE"

    # =========================
    # R16B DRAWDOWN CIRCUIT BREAKER
    # =========================
    if drawdown_status != "NOT_COMPUTABLE":
        try:
            current_dd = float(getattr(pnl_tracker, "max_drawdown", 0.0))
            if current_dd >= 0.05:
                print(f"[R16B BLOCK] Drawdown limit reached: {current_dd:.2%}")
                _safe_emit_alert(
                    "emit_risk_alert",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Drawdown limit reached: {current_dd:.2%}",
                    metadata={"current_dd": current_dd, "threshold": 0.05}
                )
                return False, "DRAWDOWN_LIMIT"
        except Exception:
            pass

    total_open = sum(open_counts.values())

    if total_open >= hard_position_limit():
        return False, "TOTAL_CAP_REACHED"

    if open_counts.get(asset_class, 0) >= hard_asset_cap(asset_class):
        return False, f"{asset_class}_CAP_REACHED"

    if new_counts_this_cycle.get(asset_class, 0) >= max_new_per_cycle(asset_class):
        return False, f"{asset_class}_CYCLE_CAP_REACHED"

    return True, "OK"


crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0


saved_state = session_recovery.load_state()
RESUME_PREVIOUS_SESSION = (os.getenv("CSS_RESUME_SESSION", "false").strip().lower() in {"1", "true", "yes", "y", "on"})
if saved_state and RESUME_PREVIOUS_SESSION:
    cycle = 0
    crypto_pnl.update(saved_state.get("crypto_pnl", {}))
    fx_pnl.update(saved_state.get("fx_pnl", {}))
    options_pnl.update(saved_state.get("options_pnl", {}))
    futures_pnl.update(saved_state.get("futures_pnl", {}))
    last_trade = saved_state.get("last_trade", "NONE")
    mtm_engine.position_counter = saved_state.get("position_counter", 0)

    print(
        "[RECOVERY] Realized PnL restored because CSS_RESUME_SESSION=true; stale open positions not reloaded. "
        "Cycle counter reset."
    )
    _safe_emit_alert("emit_system_alert", severity=AlertSeverity.INFO, message="CSS Runtime Recovered/Resumed from previous state", metadata={"cycle_counter_reset": True})
    if css_supervisor:
        css_supervisor.record_restart("RESUME_PREVIOUS_SESSION")
elif saved_state and not RESUME_PREVIOUS_SESSION:
    print("[RECOVERY IGNORED] Previous realized PnL was not restored. Fresh session active. Set CSS_RESUME_SESSION=true to resume.")


def total_realized_pnl() -> float:
    return round(
        sum(crypto_pnl.values())
        + sum(fx_pnl.values())
        + sum(options_pnl.values())
        + sum(futures_pnl.values()),
        4,
    )


def pnl_dict_for_asset(asset_class: str) -> dict:
    if asset_class == "CRYPTO":
        return crypto_pnl
    if asset_class == "FX":
        return fx_pnl
    if asset_class == "OPTIONS":
        return options_pnl
    if asset_class == "FUTURES":
        return futures_pnl

    raise ValueError(f"Unsupported asset class: {asset_class}")


def current_realized_pnl_maps_by_asset_category() -> dict[str, dict]:
    maps = {
        "CRYPTO": crypto_pnl,
        "FX": fx_pnl,
        "OPTIONS": options_pnl,
        "FUTURES": futures_pnl,
    }

    extra_maps = globals().get("asset_category_realized_pnl_maps", {})
    if isinstance(extra_maps, dict):
        for category, pnl_map in extra_maps.items():
            if isinstance(pnl_map, dict):
                maps[normalize_asset_category(category)] = pnl_map

    return maps


def normalize_asset_category(value: Any) -> str:
    category = str(value or "UNKNOWN").strip().upper()
    return category or "UNKNOWN"


def _safe_dashboard_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def aggregate_pnl_by_asset_category(
    *,
    realized_pnl_maps: dict[str, dict] | None,
    positions: list[dict] | None,
) -> list[dict[str, float | str | int]]:
    """
    Display-only PnL aggregation by asset category.

    Realized PnL comes from the current dashboard realized PnL maps.
    Unrealized PnL comes from active position floating/unrealized values.
    The category set is dynamic so future asset classes appear without UI
    redesign when upstream state supplies those categories.
    """

    categories: dict[str, dict[str, float | str | int]] = {}

    def row_for(category_value: Any) -> dict[str, float | str | int]:
        category = normalize_asset_category(category_value)
        if category not in categories:
            categories[category] = {
                "asset_category": category,
                "open_positions": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": 0.0,
            }
        return categories[category]

    for category, pnl_map in (realized_pnl_maps or {}).items():
        row = row_for(category)
        if isinstance(pnl_map, dict):
            row["realized_pnl"] = _safe_dashboard_float(row["realized_pnl"]) + sum(
                _safe_dashboard_float(value)
                for value in pnl_map.values()
            )

    for pos in positions or []:
        if not isinstance(pos, dict) or pos.get("forced_exit"):
            continue

        row = row_for(pos.get("asset_class", "UNKNOWN"))
        row["open_positions"] = int(row["open_positions"]) + 1
        row["unrealized_pnl"] = _safe_dashboard_float(row["unrealized_pnl"]) + _safe_dashboard_float(
            pos.get("unrealized_pnl", pos.get("floating", 0.0))
        )

    for row in categories.values():
        realized = round(_safe_dashboard_float(row["realized_pnl"]), 4)
        unrealized = round(_safe_dashboard_float(row["unrealized_pnl"]), 4)
        row["realized_pnl"] = realized
        row["unrealized_pnl"] = unrealized
        row["total_pnl"] = round(realized + unrealized, 4)

    return sorted(
        categories.values(),
        key=lambda item: str(item["asset_category"]),
    )


def pnl_by_asset_category_dashboard_lines(
    category_rows: list[dict[str, Any]],
) -> list[str]:
    lines = ["=== PNL BY ASSET CATEGORY ==="]

    if not category_rows:
        lines.append("No asset-category PnL available.")
        lines.append("=== END PNL BY ASSET CATEGORY ===")
        return lines

    realized_total = 0.0
    unrealized_total = 0.0

    for row in category_rows:
        category = normalize_asset_category(row.get("asset_category", "UNKNOWN"))
        open_positions = int(row.get("open_positions", 0) or 0)
        realized = _safe_dashboard_float(row.get("realized_pnl", 0.0))
        unrealized = _safe_dashboard_float(row.get("unrealized_pnl", 0.0))
        total = _safe_dashboard_float(row.get("total_pnl", realized + unrealized))
        realized_total += realized
        unrealized_total += unrealized
        lines.append(
            f"{category:<12} Open {open_positions:<3} | "
            f"Realized {realized:+.4f} | "
            f"Unrealized {unrealized:+.4f} | "
            f"Total {total:+.4f}"
        )

    lines.append("--------------------------------")
    lines.append(
        f"{'TOTAL':<12} Realized {realized_total:+.4f} | "
        f"Unrealized {unrealized_total:+.4f} | "
        f"Total {(realized_total + unrealized_total):+.4f}"
    )
    lines.append("=== END PNL BY ASSET CATEGORY ===")
    return lines





def append_closed_trade_ledger(pos: dict, reason: str, realized: float) -> None:
    """CLOSED_TRADE_LEDGER: append one durable JSONL record for dashboard paper exits."""
    try:
        CLOSED_TRADE_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        ctx = globals().get("SESSION_USER_CTX") or {}
        record = {
            "marker": CLOSED_TRADE_LEDGER_MARKER,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "symbol": str(pos.get("symbol", "")),
            "asset_class": str(pos.get("asset_class", "")),
            "exit_reason": str(reason),
            "realized_pnl": float(realized),
            "floating_at_exit": float(pos.get("floating", 0.0)),
            "engine_mode": str(globals().get("ENGINE_MODE", "")),
            "broker_mode": str(globals().get("SELECTED_BROKER_MODE", "")),
            "selected_broker": str(globals().get("SELECTED_BROKER", "")),
            "cycle": int(globals().get("cycle", 0) or 0),
            "session_id": str(ctx.get("session_id", "")),
            "user_id": str(ctx.get("user_id", "")),
        }
        if str(pos.get("asset_class", "")).upper() == "OPTIONS" and any(
            key in pos for key in (*OPTION_GREEK_FIELDS, "greeks_source")
        ):
            record.update(normalize_option_greeks(pos))
        if str(pos.get("asset_class", "")).upper() == "OPTIONS":
            for key in globals().get("OPTION_STRATEGY_FIELDS", ()):
                if key in pos:
                    record[key] = str(pos.get(key, ""))

        with CLOSED_TRADE_LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"[CLOSED_TRADE_LEDGER WARN] {exc}")



def should_take_dashboard_paper_profit(pos: dict) -> bool:
    if str(GLOBAL_BROKER_MODE).strip().lower() == "live":
        return False
    if str(SELECTED_BROKER_MODE).strip().lower() == "live":
        return False
    if pos.get("forced_exit"):
        return False
    if int(pos.get("age_cycles", 0)) < PAPER_PROFIT_TARGET_MIN_AGE_CYCLES:
        return False
    return float(pos.get("floating", 0.0)) > PAPER_PROFIT_TARGET_FLOATING



# =========================
# R17 EXIT EXECUTION LAYER
# =========================

def render_trade_dashboard_summary() -> None:
    """TRADE_DASHBOARD_SUMMARY: dynamic display-only cycle summary; no trading decisions."""
    try:
        active_positions = [p for p in mtm_engine.positions if not p.get("forced_exit")]

        pnl_maps = current_realized_pnl_maps_by_asset_category()

        asset_classes = sorted(
            set(pnl_maps.keys())
            | {str(p.get("asset_class", "UNKNOWN") or "UNKNOWN") for p in active_positions}
        )

        asset_rows = []
        realized_total = 0.0
        floating_total = 0.0

        for asset in asset_classes:
            realized = sum(float(v) for v in pnl_maps.get(asset, {}).values())
            floating = sum(
                float(pos.get("floating", 0.0))
                for pos in active_positions
                if str(pos.get("asset_class", "UNKNOWN") or "UNKNOWN") == asset
            )
            count = sum(
                1
                for pos in active_positions
                if str(pos.get("asset_class", "UNKNOWN") or "UNKNOWN") == asset
            )
            total = realized + floating
            realized_total += realized
            floating_total += floating
            asset_rows.append((asset, count, realized, floating, total))

        pnl_category_rows = aggregate_pnl_by_asset_category(
            realized_pnl_maps=pnl_maps,
            positions=active_positions,
        )

        position_limit = globals().get("adaptive_position_limit", None)
        if position_limit is None:
            position_limit = globals().get("ADAPTIVE_POSITION_LIMIT", None)
        if position_limit is None:
            position_limit = globals().get("MAX_PAPER_OPEN_POSITIONS", "N/A")

        tracker_value = globals().get("tracker_equity", None)
        if tracker_value is None:
            tracker_value = globals().get("TRACKER_EQUITY", None)

        peak_value = globals().get("peak_equity", None)
        if peak_value is None:
            peak_value = globals().get("PEAK_EQUITY", None)

        drawdown_value = globals().get("drawdown_pct", None)
        if drawdown_value is None:
            drawdown_value = globals().get("DRAWDOWN_PCT", None)

        ledger_exists = CLOSED_TRADE_LEDGER_PATH.exists() if "CLOSED_TRADE_LEDGER_PATH" in globals() else False

        print("")
        print("=== TRADE DASHBOARD SUMMARY ===")
        print(f"Cycle: {globals().get('cycle', 'N/A')}")
        print(f"Engine Mode: {globals().get('ENGINE_MODE', 'N/A')}")
        print(f"Broker: {globals().get('SELECTED_BROKER', 'N/A')}")
        print(f"Broker Mode: {globals().get('SELECTED_BROKER_MODE', 'N/A')}")
        print(f"Open Positions: {len(active_positions)} / {position_limit}")

        print("")
        print("=== OPEN POSITIONS BY ASSET CLASS ===")
        for asset, count, _realized, _floating, _total in asset_rows:
            print(f"{asset:<10} {count}")
        print(f"{'TOTAL':<10} {len(active_positions)}")
        print("=== END OPEN POSITIONS BY ASSET CLASS ===")

        print("")
        for line in pnl_by_asset_category_dashboard_lines(pnl_category_rows):
            print(line)

        print("")
        for line in option_position_greeks_dashboard_lines(active_positions):
            print(line)

        print("")
        for line in portfolio_greeks_dashboard_lines(active_positions):
            print(line)

        print("")
        for line in margin_dashboard_lines(
            selected_broker=globals().get("SELECTED_BROKER", "NONE"),
            selected_broker_mode=globals().get("SELECTED_BROKER_MODE", "paper"),
        ):
            print(line)

        print("")
        if tracker_value is None:
            print("Tracker Equity: N/A")
        else:
            print(f"Tracker Equity: {float(tracker_value):+.4f}")

        if peak_value is None:
            print("Peak Equity: N/A")
        else:
            print(f"Peak Equity: {float(peak_value):+.4f}")

        if drawdown_value is None:
            print("Drawdown: N/A")
        else:
            print(f"Drawdown: {float(drawdown_value):.4f}%")

        print(f"Last Trade: {globals().get('last_trade', 'NONE')}")
        print(f"Closed Trade Ledger: {'YES' if ledger_exists else 'NO'}")
        
        # --- PHASE 126C: PROFITABILITY ANALYTICS ---
        try:
            from analytics.trade_outcome_ledger import print_profitability_dashboard
            print_profitability_dashboard()
        except Exception as analytics_exc:
            print(f"[PROFITABILITY ANALYTICS WARN] {analytics_exc}")
        # --- END PHASE 126C ---
        
        # --- PHASE 126E: STRATEGY RANKINGS ---
        try:
            from analytics.strategy_ranking_engine import print_strategy_ranking_dashboard
            print_strategy_ranking_dashboard()
        except Exception as strategy_exc:
            print(f"[STRATEGY RANKING WARN] {strategy_exc}")
        # --- END PHASE 126E ---

        print("=== END TRADE DASHBOARD SUMMARY ===\n")
    except Exception as exc:
        print(f"[TRADE_DASHBOARD_SUMMARY WARN] {exc}")


def r17_execute_exit(pos, observer_symbol, observer_price, reason):
    """
    Institutional exit execution pipeline:
    - Ensures capital, PnL, and lifecycle stay in sync
    """
    try:
        if pos.get("forced_exit"):
            return

        # 1. Book exit (authoritative)
        book_position_exit(pos, reason)

        if reason == "TAKE_PROFIT":
            _safe_emit_alert(
                "emit_trade_alert",
                severity=AlertSeverity.INFO,
                message=f"Profit target reached for {observer_symbol} at price {observer_price}",
                metadata={"symbol": observer_symbol, "price": observer_price, "reason": reason}
            )

        # 2. Close observer position (PnL)
        try:
            pnl_observer.close_position(observer_symbol, observer_price)
        except Exception as e:
            print(f"[R17 WARN] Observer close failed: {str(e)[:60]}")

        # 3. Ensure capital release safety (idempotent)
        try:
            if pos.get("broker_tested", False):
                capital_governor.release_trade(pos["position_id"])
        except Exception as e:
            print(f"[R17 WARN] Capital release failed: {str(e)[:60]}")

    except Exception as e:
        print(f"[R17 ERROR] Exit execution failure: {str(e)[:80]}")

def book_position_exit(pos: dict, reason: str) -> None:
    global last_trade

    if pos["forced_exit"]:
        return

    if pos.get("broker_order_ok"):
        last_trade = f"{pos['symbol']} BROKER_OPEN_MANUAL_REVIEW"
        return

    realized = round(pos["floating"], 4)
    append_closed_trade_ledger(pos, reason, realized)

    # === TRACKER UPDATE ===
    try:
        pnl_tracker.record_trade(
            instrument=pos["symbol"],
            realized_pnl=realized,
            unrealized_pnl=0.0
        )
    except Exception as e:
        print(f"[TRACKER ERROR] {e}")

    pos["forced_exit"] = True
    pos["exit_reason"] = reason
    _safe_emit_alert("emit_trade_alert", severity=AlertSeverity.INFO, message=f"Trade Closed: {pos['symbol']} ({reason})", metadata={"symbol": pos["symbol"], "reason": reason, "realized": realized})

    cluster_risk_governor.release_cluster_slot(pos["cluster_name"])

    if pos.get("broker_tested", False):
        capital_governor.release_trade(pos["position_id"])

    target_pnl = pnl_dict_for_asset(pos["asset_class"])
    target_pnl[pos["symbol"]] = round(
        target_pnl.get(pos["symbol"], 0.0) + realized,
        4,
    )

    cluster_amplifier.record_cluster_win(pos["symbol"], realized)

    if reason in {"STOP", "FAST_STOP"}:
        _safe_emit_alert("emit_trade_alert", severity=AlertSeverity.WARNING, message=f"Loss threshold reached for {pos['symbol']}", metadata={"symbol": pos["symbol"], "reason": reason, "realized": realized})
        locked_profit_ledger.record_forced_exit(pos["position_id"], realized)
    elif reason == "TAKE_PROFIT":
        locked_profit_ledger.record_priority_exit()
    elif reason == "DEFENSIVE_REDUCTION":
        locked_profit_ledger.record_defensive_reduction_exit()

    locked_profit_ledger.record_recycled_slot()

    last_trade = f"{pos['symbol']} EXIT {reason} {realized:+.4f}"


def apply_defensive_exposure_reduction() -> int:
    if not is_session_locked():
        return 0

    open_positions_list = [
        p for p in mtm_engine.positions if not p["forced_exit"]
    ]

    if not open_positions_list:
        return 0

    open_positions_list.sort(
        key=lambda x: (float(x.get("floating", 0.0)), -int(x.get("age_cycles", 0)))
    )

    reductions = 0

    for pos in open_positions_list:
        if reductions >= DEFENSIVE_REDUCTION_PER_CYCLE:
            break

        if pos.get("broker_order_ok"):
            continue

        book_position_exit(pos, "DEFENSIVE_REDUCTION")
        reductions += 1

    return reductions


def print_authentication_status_panel(current_status: dict) -> None:
    auth_state = "AUTHENTICATED" if SESSION_USER_CTX.get("user_id") else "UNAUTHENTICATED"
    auth_source = SESSION_USER_CTX.get("auth_source", "UNKNOWN")

    now_epoch = time.time()
    created = current_status.get("created", now_epoch)
    session_age_seconds = max(0, int(now_epoch - float(created)))

    max_session_sec = int(current_status.get("max_session_seconds", SESSION_MAX_SECONDS))
    expiry_countdown = max(0, max_session_sec - session_age_seconds)

    last_auth_time = SESSION_USER_CTX.get("last_auth_time", "N/A")
    last_auth_event = SESSION_USER_CTX.get("last_auth_event", "N/A")

    print("--- OPERATIONAL AUTHENTICATION STATUS ---")
    print(f"Auth State: {auth_state}")
    print(f"Auth Source: {auth_source}")
    print(f"Session Age: {session_age_seconds} seconds")
    print(f"Last Auth Time: {last_auth_time}")
    print(f"Last Auth Event: {last_auth_event}")
    print(f"Session Expiry Countdown: {expiry_countdown} seconds")


def print_oanda_broker_status() -> None:
    print("--- OANDA BROKER STATUS ---")

    resolved_key = bool(os.getenv("OANDA_API_KEY"))
    resolved_account = bool(os.getenv("OANDA_ACCOUNT_ID"))
    resolved_base = os.getenv("OANDA_BASE_URL", "")

    if not (resolved_key and resolved_account):
        print("OANDA CONNECTED: NO")
        print(f"OANDA KEY PRESENT: {'YES' if resolved_key else 'NO'}")
        print(f"OANDA ACCOUNT PRESENT: {'YES' if resolved_account else 'NO'}")
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
        print("OANDA OPEN TRADES: N/A")
        return

    try:
        summary = oanda.get_account_summary()

        if not summary.get("ok", False):
            print(
                f"OANDA CONNECTED: ERROR "
                f"status={summary.get('status')} "
                f"error={summary.get('error')}"
            )
            runtime_supervisor.record_broker_disconnect("OANDA", f"{summary.get('status')} {summary.get('error')}")
            _safe_emit_alert(
                "emit_broker_alert",
                severity=AlertSeverity.CRITICAL,
                message=f"OANDA Connection Error: {summary.get('status')} {summary.get('error')}",
                metadata={"broker": "OANDA", "status": summary.get("status"), "error": summary.get("error")}
            )
            print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
            print("OANDA OPEN TRADES: ERR")
            return

        nav = oanda.extract_balance_nav(summary)
        open_trade_count = get_oanda_open_trade_count()

        print("OANDA CONNECTED: YES")
        print(f"BALANCE: {nav['balance']}")
        print(f"NAV: {nav['nav']}")
        print(f"OANDA OPEN TRADES: {open_trade_count}")
        print(f"OANDA BASE URL: {resolved_base}")

    except Exception as e:
        print(f"OANDA ERROR: {str(e)[:60]}")
        runtime_supervisor.record_broker_disconnect("OANDA", str(e)[:60])
        _safe_emit_alert("emit_broker_alert", severity=AlertSeverity.CRITICAL, message=f"OANDA Connection Exception: {str(e)[:60]}", metadata={"broker": "OANDA", "error": str(e)[:60]})
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
        print("OANDA OPEN TRADES: ERR")
    else:
        _safe_emit_alert("emit_broker_alert", severity=AlertSeverity.INFO, message="OANDA Broker Connected Successfully", metadata={"broker": "OANDA"})


def print_broker_credential_diagnostics() -> None:
    state = globals().get("STARTUP_BROKER_STATE", {})
    state = state if isinstance(state, dict) else {}
    source = state.get("broker_credential_diagnostics")
    if not isinstance(source, dict):
        credential_diagnostics = state.get("credential_diagnostics")
        if isinstance(credential_diagnostics, dict):
            source = credential_diagnostics.get("broker_credential_diagnostics", credential_diagnostics)
        else:
            source = {}
    payload = diagnostics_payload(
        {
            "broker": state.get("selected_broker", globals().get("SELECTED_BROKER", "NONE")),
            **(source if isinstance(source, dict) else {}),
        }
    )
    print("==================================================")
    print("BROKER CREDENTIAL DIAGNOSTICS")
    print("==================================================")
    print(f"Broker: {str(payload.get('broker', 'none')).upper()}")
    print(f"Credentials Present: {'YES' if payload.get('credentials_present') else 'NO'}")
    print(f"Authentication Attempted: {'YES' if payload.get('authentication_attempted') else 'NO'}")
    print(f"Authenticated: {'YES' if payload.get('authenticated') else 'NO'}")
    print(f"Failure Reason: {payload.get('failure_reason', 'MISSING_CREDENTIALS')}")
    print(f"Recommended Action: {payload.get('recommended_action', 'Configure broker credentials')}")
    print(f"Severity: {payload.get('severity', 'ERROR')}")


def print_coinbase_broker_status() -> None:
    print("--- COINBASE BROKER STATUS ---")

    readiness = globals().get("COINBASE_READ_ONLY_STATUS", {})
    readiness = readiness if isinstance(readiness, dict) else {}
    diagnostics = readiness.get("credential_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = coinbase_credential_diagnostics().as_dict()
    canonical = readiness.get("canonical_broker_runtime_state")
    canonical = canonical if isinstance(canonical, dict) else {}
    canonical_account = canonical.get("account_evidence") if isinstance(canonical.get("account_evidence"), dict) else {}
    canonical_provenance = canonical.get("status_provenance") if isinstance(canonical.get("status_provenance"), dict) else {}
    limits = readiness.get("limit_reconciliation")
    if not isinstance(limits, dict):
        limits = coinbase_live_limit_reconciliation(legacy_limit_usd=COINBASE_MAX_LIVE_ORDER_USD)
    key_present = bool(diagnostics.get("coinbase_key_present"))
    private_key_present = bool(
        diagnostics.get("coinbase_private_key_present")
        or diagnostics.get("coinbase_key_file_present")
    )
    connected = bool(canonical_account.get("connected", readiness.get("broker_connected", False)))
    execution_scope = str(readiness.get("execution_scope", "PAPER_OR_NOT_SELECTED"))
    auth_reason = str(readiness.get("auth_reason", "not_coinbase_live_read_only"))
    if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live" and not BROKER_EXECUTION_ARMED:
        display_mode = "live" if connected else "live-read-only"
    elif SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "paper":
        display_mode = f"paper fallback ({auth_reason})"
    else:
        display_mode = SELECTED_BROKER_MODE if SELECTED_BROKER == "COINBASE" else "N/A"

    print(f"COINBASE SELECTED: {'YES' if SELECTED_BROKER == 'COINBASE' else 'NO'}")
    print(f"COINBASE MODE: {display_mode}")
    print(f"COINBASE KEY PRESENT: {'YES' if key_present else 'NO'}")
    print(f"COINBASE PRIVATE KEY PRESENT: {'YES' if private_key_present else 'NO'}")
    print(f"COINBASE CONNECTED: {'YES' if connected else 'NO'}")
    print(f"CANONICAL TRANSPORT STATUS: {canonical.get('transport_status', 'UNKNOWN')}")
    print(f"CANONICAL AUTH STATUS: {canonical.get('authentication_status', 'UNKNOWN')}")
    print(f"CANONICAL ACCOUNT STATUS: {canonical.get('account_status', 'UNKNOWN')}")
    print(f"CANONICAL BALANCE STATUS: {canonical.get('balance_status', 'UNKNOWN')}")
    print(f"CANONICAL MARGIN STATUS: {canonical.get('margin_status', 'UNKNOWN')}")
    print(f"CANONICAL OVERALL STATUS: {canonical.get('overall_status', 'UNKNOWN')}")
    print(f"CANONICAL FAILURE REASON: {canonical.get('failure_reason', 'UNKNOWN')}")
    print(f"CANONICAL STATE HASH: {canonical.get('state_hash', 'UNKNOWN')}")
    print(f"CANONICAL PROVENANCE: {canonical_provenance if canonical_provenance else 'UNKNOWN'}")
    print(f"AUTH REASON: {auth_reason}")
    print(f"CREDENTIAL STATUS: {readiness.get('credential_status', 'DATA UNAVAILABLE')}")
    print(f"AUTH STATUS: {readiness.get('auth_status', 'NOT_TESTED')}")
    print(f"CONNECTION STATUS: {readiness.get('connection_status', 'NOT_TESTED')}")
    print(f"CONNECTION ERROR: {readiness.get('connection_error', '')}")
    print(f"LAST BROKER SYNC: {readiness.get('last_broker_sync', readiness.get('last_successful_sync', 'DATA UNAVAILABLE'))}")
    print(f"ACCOUNT EQUITY: {readiness.get('account_equity', 'DATA UNAVAILABLE')}")
    print(f"CASH: {readiness.get('cash', 'DATA UNAVAILABLE')}")
    print(f"BUYING POWER: {readiness.get('buying_power', 'DATA UNAVAILABLE')}")
    print(f"AVAILABLE BALANCE: {readiness.get('available_balance', 'DATA UNAVAILABLE')}")
    print(f"PRODUCTS LOADED: {readiness.get('products_loaded', 0)}")
    print(f"MARKET DATA STATUS: {readiness.get('market_data_status', 'NOT_TESTED')}")
    print(f"DRAWDOWN STATUS: {readiness.get('drawdown_status', 'UNKNOWN')}")
    print(f"DRAWDOWN REASON: {readiness.get('drawdown_reason', 'Broker balance unavailable')}")
    print(f"PRODUCT/PRICE STATUS: {readiness.get('product_price_status', 'NOT_TESTED')}")
    print(f"BALANCE/POSITION STATUS: {readiness.get('balance_position_status', 'NOT_TESTED')}")
    print(f"ORDER SUBMISSION STATUS: {readiness.get('order_submission_status', 'DISABLED')}")
    print(f"OPERATOR REQUESTED LIVE: {'YES' if readiness.get('operator_requested_live') else 'NO'}")
    print(f"EXECUTION AUTHORITY: {'YES' if readiness.get('execution_authority') else 'NO'}")
    print(f"AUTHORITY REASON: {readiness.get('authority_reason', 'Operator Intent Missing')}")
    print(f"LIVE AUTHORITY STATE: {readiness.get('live_authority_state', 'BLOCKED')}")
    print(f"BROKER EXECUTION: {'ARMED' if BROKER_EXECUTION_ARMED else 'DISABLED'}")
    print(f"CAN LIVE EXECUTE: {'YES' if readiness.get('can_live_execute') else 'NO'}")
    print(f"EXECUTION SCOPE: {execution_scope}")
    print(f"COINBASE LIVE ORDER FLAG: {'ON' if coinbase_live_orders_enabled() else 'OFF'}")
    print(
        "COINBASE LIVE LIMIT AUTHORITY: "
        f"{limits.get('canonical_authority', 'PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR')} "
        f"CAD {limits.get('canonical_live_pilot_limit_cad', '20.00')}"
    )
    print(
        "COINBASE DISPLAY-ONLY LEGACY SECONDARY GUARD USD: "
        f"${float(limits.get('legacy_coinbase_max_live_order_usd', COINBASE_MAX_LIVE_ORDER_USD)):.2f}"
    )

    if SELECTED_BROKER != "COINBASE":
        return

    if canonical:
        return

    if coinbase is None:
        return

    try:
        if hasattr(coinbase, "ping_live_auth"):
            ping = coinbase.ping_live_auth()
            ok = bool(ping.get("ok")) if isinstance(ping, dict) else False
            mode = ping.get("mode", SELECTED_BROKER_MODE) if isinstance(ping, dict) else SELECTED_BROKER_MODE

            print(f"COINBASE CONNECTED: {'YES' if ok else 'ERROR'}")
            print(f"COINBASE AUTH MODE: {mode}")

            if not ok:
                runtime_supervisor.record_broker_disconnect("COINBASE", "ping_live_auth failed or returned not OK")
                _safe_emit_alert(
                    "emit_broker_alert",
                    severity=AlertSeverity.CRITICAL,
                    message="Coinbase ping_live_auth failed or returned not OK",
                    metadata={"broker": "COINBASE", "ping": ping}
                )

            if isinstance(ping, dict) and "account_count" in ping:
                print(f"COINBASE ACCOUNT COUNT: {ping.get('account_count')}")

            return

        configured = bool(coinbase.is_configured()) if hasattr(coinbase, "is_configured") else True
        print(f"COINBASE CONNECTED: {'YES' if configured else 'NO'}")
        if configured:
            _safe_emit_alert("emit_broker_alert", severity=AlertSeverity.INFO, message="COINBASE Broker Connected Successfully", metadata={"broker": "COINBASE"})

    except Exception as e:
        print(f"COINBASE ERROR: {str(e)[:60]}")
        runtime_supervisor.record_broker_disconnect("COINBASE", str(e)[:60])
        _safe_emit_alert("emit_broker_alert", severity=AlertSeverity.CRITICAL, message=f"Coinbase Connection Exception: {str(e)[:60]}", metadata={"broker": "COINBASE", "error": str(e)[:60]})


def broker_execution_status_label() -> str:
    if is_session_locked():
        return "LOCKED_DEFENSIVE_MODE"
    if not BROKER_EXECUTION_ARMED:
        return "DISABLED"
    return "ARMED"


def selected_broker_status_label() -> str:
    return SELECTED_BROKER


def active_execution_scope_label() -> str:
    if is_session_locked():
        return "DEFENSIVE MODE / POSITION MANAGEMENT ONLY"

    if not BROKER_EXECUTION_ARMED:
        if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live":
            return "LIVE READ-ONLY VALIDATION / ORDERS BLOCKED"
        return "PAPER ONLY"

    if SELECTED_BROKER == "OANDA":
        return "OANDA FX PRACTICE ONLY"

    if SELECTED_BROKER == "COINBASE":
        if SELECTED_BROKER_MODE == "live" and coinbase_live_orders_enabled():
            return "COINBASE LIVE CRYPTO GATED"
        if SELECTED_BROKER_MODE == "live":
            return "COINBASE LIVE AUTH ONLY / ORDERS BLOCKED"
        return "COINBASE PAPER CRYPTO"

    if SELECTED_BROKER == "NONE":
        return "NO BROKER SELECTED"

    return f"{SELECTED_BROKER} RESERVED / BLOCKED"


def select_cycle_candidates() -> list[tuple[str, str, float, float]]:
    candidates = [
        ("CRYPTO", random.choice(SYMBOLS), 12.0, 0.68),
        ("CRYPTO", random.choice(SYMBOLS), 12.2, 0.69),
        ("FX", random.choice(FX_SYMBOLS), 11.5, 0.66),
        ("FX", random.choice(FX_SYMBOLS), 11.7, 0.67),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.0, 0.71),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.2, 0.72),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.0, 0.69),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.2, 0.70),
    ]
    random.shuffle(candidates)
    return candidates


def pnl_divergence_warning(
    mtm_realized: float,
    mtm_unrealized: float,
    observer_realized: float,
    observer_unrealized: float,
    threshold: float = 0.001,
) -> str | None:
    realized_gap = abs(float(mtm_realized) - float(observer_realized))
    unrealized_gap = abs(float(mtm_unrealized) - float(observer_unrealized))

    if realized_gap > threshold or unrealized_gap > threshold:
        return (
            f"[PNL DIVERGENCE WARNING] "
            f"realized_gap={realized_gap:.6f} "
            f"unrealized_gap={unrealized_gap:.6f}"
        )
    return None


import uuid

class RepairEngine:
    def __init__(self):
        self.records_file = ARTIFACTS_DIR / "css_repair_records.json"
        self.records: list[dict] = self.load_records()

    def load_records(self) -> list[dict]:
        if self.records_file.exists():
            try:
                with open(self.records_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_records(self) -> None:
        with open(self.records_file, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2)

    def create_record(self, category: str, details: dict) -> str:
        record_id = f"REP-{str(uuid.uuid4())[:8]}"
        record = {
            "record_id": record_id,
            "category": category,
            "status": "OPEN",
            "details": details,
            "created_at": _utc_now_compat().isoformat(),
            "resolution_note": ""
        }
        self.records.append(record)
        self.save_records()
        print(f"[REPAIR RECORD CREATED] {record_id}: {category}")
        return record_id

    def resolve_record(self, record_id: str, resolution_category: str, note: str) -> bool:
        for record in self.records:
            if record["record_id"] == record_id:
                record["status"] = "REPAIRED"
                record["resolution_note"] = f"[{resolution_category}] {note}"
                self.save_records()
                print(f"[REPAIR RESOLVED] {record_id} via {resolution_category}")
                return True
        return False

    def has_open_records(self) -> bool:
        return any(r["status"] in {"OPEN", "INVESTIGATING"} for r in self.records)

repair_engine = RepairEngine()

RECONCILIATION_STATUS = "HEALTHY"

def detect_divergences(local_positions: list[dict], broker_positions: list[dict]) -> list[tuple[str, dict]]:
    divergences = []
    
    local_map = {p["symbol"]: p for p in local_positions if p.get("asset_class") == "FX" and not p.get("forced_exit")}
    broker_map = {p.get("instrument"): p for p in broker_positions}

    local_symbols = set(local_map.keys())
    broker_symbols = set(broker_map.keys())

    for sym in broker_symbols - local_symbols:
        divergences.append(("ORPHAN_BROKER_POSITION", {"symbol": sym, "broker_data": broker_map[sym]}))

    for sym in local_symbols - broker_symbols:
        divergences.append(("GHOST_LOCAL_POSITION", {"symbol": sym, "local_data": local_map[sym]}))

    for sym in local_symbols.intersection(broker_symbols):
        local_units = float(local_map[sym].get("quantity", 0))
        broker_units = float(broker_map[sym].get("units", 0)) # Assuming long vs short units might be signed or absolute depending on format. In OANDA, it's typically 'long.units' or 'short.units'. Let's just pass raw for now.
        
        # OANDA positions actually return 'long' and 'short' dicts. The previous code didn't parse units deeply, it just counted.
        # Let's handle OANDA format carefully. OANDA gives: "long": {"units": "0", ...}, "short": {"units": "-1000", ...}
        # But even if we don't deeply parse, we can log the entire object.
        # To avoid false positive unit mismatches right now without complex OANDA parsing, 
        # we will only flag BROKER_POSITION_MISMATCH if we add specific unit comparison later, or we can check simple presence.
        pass

    return divergences


def perform_startup_reconciliation() -> None:
    global RECONCILIATION_STATUS
    if SELECTED_BROKER != "OANDA" or not BROKER_EXECUTION_ARMED:
        return

    try:
        resp = oanda.get_open_positions()
        if not resp.get("ok"):
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("RECONCILIATION_API_ERROR")
            print("[RECONCILIATION API ERROR] Failed to fetch open positions from OANDA.")
            return

        broker_positions = resp.get("data", {}).get("positions", [])
        local_positions = mtm_engine.positions

        divergences = detect_divergences(local_positions, broker_positions)
        
        if divergences:
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("RECONCILIATION_DIVERGENCE")
            print(f"[RECONCILIATION FAILED] {len(divergences)} divergences detected.")
            for cat, det in divergences:
                repair_engine.create_record(cat, det)
        else:
            print("[RECONCILIATION OK] Local and Broker state in parity.")

    except Exception as e:
        RECONCILIATION_STATUS = "MISMATCH"
        lock_session("RECONCILIATION_ERROR")
        print(f"[RECONCILIATION ERROR] Failed to query broker: {e}")


def perform_continuous_reconciliation() -> None:
    global RECONCILIATION_STATUS
    if SELECTED_BROKER != "OANDA" or not BROKER_EXECUTION_ARMED:
        return

    # Phase 117E: Broker Health Check
    if getattr(oanda, "health_state", "GREEN") == "RED":
        RECONCILIATION_STATUS = "MISMATCH"
        lock_session("BROKER_HEALTH_RED")
        print("[BROKER HEALTH RED] Consecutive broker failures exceeded threshold. Locking session.")
        return

    try:
        resp = oanda.get_open_positions()
        if not resp.get("ok"):
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("CONTINUOUS_RECONCILIATION_API_ERROR")
            print("[CONTINUOUS RECONCILIATION API ERROR] Failed to fetch open positions from OANDA.")
            return

        broker_positions = resp.get("data", {}).get("positions", [])
        local_positions = mtm_engine.positions

        divergences = detect_divergences(local_positions, broker_positions)

        if divergences:
            RECONCILIATION_STATUS = "MISMATCH"
            lock_session("RECONCILIATION_DIVERGENCE")
            print(f"[CONTINUOUS RECONCILIATION FAILED] {len(divergences)} divergences detected.")
            
            if has_in_flight_orders():
                print("[CONTINUOUS RECONCILIATION] In-flight orders exist. Suppressing auto-flatten logic.")
                _DIVERGENCE_STATE["count"] = 0
                _DIVERGENCE_STATE["type"] = None
                for cat, det in divergences:
                    repair_engine.create_record(cat, det)
            else:
                cat_types = [d[0] for d in divergences]
                primary_cat = cat_types[0] if cat_types else None
                
                if _DIVERGENCE_STATE["type"] == primary_cat:
                    _DIVERGENCE_STATE["count"] += 1
                else:
                    import time
                    _DIVERGENCE_STATE["first_detected"] = time.time()
                    _DIVERGENCE_STATE["count"] = 1
                    _DIVERGENCE_STATE["type"] = primary_cat
                
                for cat, det in divergences:
                    if cat in {"ORPHAN_BROKER_POSITION", "BROKER_POSITION_MISMATCH"}:
                        if _DIVERGENCE_STATE["count"] >= 2:
                            _DIVERGENCE_STATE["confirmed_count"] += 1
                            simulate_auto_flatten([(cat, det)])
                        else:
                            repair_engine.create_record(cat, det)
                    else:
                        repair_engine.create_record(cat, det)
        else:
            print("[CONTINUOUS RECONCILIATION OK] Local and Broker state in parity.")
            _DIVERGENCE_STATE["count"] = 0
            _DIVERGENCE_STATE["type"] = None

    except Exception as e:
        RECONCILIATION_STATUS = "MISMATCH"
        lock_session("CONTINUOUS_RECONCILIATION_ERROR")
        print(f"[CONTINUOUS RECONCILIATION ERROR] Failed to query broker: {e}")


perform_startup_reconciliation()

_SESSION_QUIET_MODE_ACTIVATED = False

try:
    if css_supervisor:
        css_supervisor.start()
    _safe_emit_alert("emit_engine_alert", severity=AlertSeverity.INFO, message="CSS Runtime Engine Started", metadata={"broker_armed": BROKER_EXECUTION_ARMED})
    while True:
        if os.getenv("CSS_TEST_MODE"):
            break

        cycle += 1
        
        current_status = enforce_active_session(cycle, last_trade)

        if not is_session_locked():
            current_status = touch_active_session()
        else:
            current_status = {
                **current_status,
                "active": False,
                "defensive_mode_active": True,
            }

        if cycle % 5 == 0 and not is_session_locked():
            perform_continuous_reconciliation()

        if cycle % 60 == 0:
            _safe_emit_alert("heartbeat", metadata={"cycle": cycle, "open_positions": mtm_engine.count_open_positions()})
            if css_supervisor:
                css_supervisor.heartbeat()
                css_supervisor.check_stale_heartbeat()

        print(f"=== Cycle {cycle} | {datetime.now()} ===")


        exit_profile = MODE_EXIT_PROFILE.get(
            ENGINE_MODE,
            MODE_EXIT_PROFILE["BALANCED"],
        )

        for pos in mtm_engine.positions:
            if pos["forced_exit"]:
                continue

            drift = smart_drift_engine.generate_drift(pos)
            pos["floating"] = round(pos["floating"] + drift, 4)
            pos["age_cycles"] += 1

            observer_symbol = f"{pos['position_id']}::{pos['symbol']}"
            observer_price = 100.0 + float(pos["floating"])
            pnl_observer.update_market_price(observer_symbol, observer_price)

            if should_take_dashboard_paper_profit(pos):
                print(
                    f"[R17 PAPER EXIT] asset={pos.get('asset_class', 'UNKNOWN')} "
                    f"reason=profit_target floating={float(pos.get('floating', 0.0)):+.4f}"
                )
                r17_execute_exit(pos, observer_symbol, observer_price, "TAKE_PROFIT")
                continue

            profile = r15b_profile()

            entry_price = float(pos.get("entry_price", 100.0))
            pnl_pct = pos["floating"] / max(entry_price, 1e-6)

            sig = float(pos.get("signal_score", 0.0))
            prob = float(pos.get("prob_positive", 0.0))

            if pnl_pct <= profile["sl"] * 0.7 and sig < 11.5:
                r17_execute_exit(pos, observer_symbol, observer_price, "FAST_STOP")

            elif pnl_pct <= profile["sl"]:
                r17_execute_exit(pos, observer_symbol, observer_price, "STOP")

            elif pnl_pct >= profile["tp"]:
                if sig >= 13.5 and prob >= 0.70:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 3)
                    print(f"[R15B RUNNER] {pos['symbol']} strong signal extended")

                elif sig >= 12.5 and prob >= 0.66:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                    print(f"[R15B EXTEND] {pos['symbol']} moderate extension")

                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TAKE_PROFIT")

            if pos.get('forced_exit', False):
                continue
            elif pos["age_cycles"] >= exit_profile["max_age"]:
                if sig >= 12.0 and prob >= 0.65:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TIME_EXIT")

            if pos["floating"] <= exit_profile["stop_loss"] * 0.8:
                r17_execute_exit(pos, observer_symbol, observer_price, "FAST_STOP")

            elif pos["floating"] <= exit_profile["stop_loss"]:
                r17_execute_exit(pos, observer_symbol, observer_price, "STOP")

            elif pos["floating"] >= exit_profile["take_profit"]:
                if pos["signal_score"] >= 13.0 and pos["prob_positive"] >= 0.70:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 3)
                elif pos["signal_score"] >= 12.0 and pos["prob_positive"] >= 0.66:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TAKE_PROFIT")

            elif pos["age_cycles"] >= exit_profile["max_age"]:
                if pos["signal_score"] >= 11.5 and pos["prob_positive"] >= 0.64:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TIME_EXIT")

        defensive_reductions = apply_defensive_exposure_reduction()

        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
        broker_test_positions = mtm_engine.count_open_broker_test_positions()
        mtm_unrealized = round(sum(display_by_asset.values()), 4)
        open_positions = mtm_engine.count_open_positions()

        mtm_realized = total_realized_pnl()

        realized_by_asset = {
            "CRYPTO": sum(crypto_pnl.values()),
            "FX": sum(fx_pnl.values()),
            "OPTIONS": sum(options_pnl.values()),
            "FUTURES": sum(futures_pnl.values()),
        }
        pcnrass_refresh_balances(realized_by_asset, display_by_asset)

        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        authoritative_realized = mtm_realized
        authoritative_unrealized = mtm_unrealized
        authoritative_equity_pnl = round(authoritative_realized + authoritative_unrealized, 4)
        authoritative_live_equity = round(
            float(pnl_observer.starting_balance) + authoritative_equity_pnl,
            4,
        )

        total_realized = authoritative_realized
        total_unrealized = authoritative_unrealized
        total_equity = authoritative_equity_pnl

        try:
            pnl_observer.current_balance = authoritative_live_equity
        except Exception:
            pass

        try:
            pnl_tracker.current_equity = authoritative_live_equity
            capital_snapshot = getattr(capital_governor, "balance_snapshot", {})
            drawdown_status = str(capital_snapshot.get("drawdown_status", "COMPUTED")).upper()
            drawdown_reason = str(capital_snapshot.get("drawdown_reason", ""))

            if str(SELECTED_BROKER_MODE).lower() == "live" and drawdown_status == "NOT_COMPUTABLE":
                print(
                    f"[R16B NOT_COMPUTABLE] {drawdown_reason or 'Broker balance unavailable'} "
                    f"state={capital_snapshot.get('capital_state', 'CAPITAL_UNAVAILABLE')}"
                )
            elif str(SELECTED_BROKER_MODE).lower() == "live" and authoritative_live_equity > 0:
                pnl_tracker.starting_equity = authoritative_live_equity
                pnl_tracker.peak_equity = authoritative_live_equity
                pnl_tracker.max_drawdown = 0.0
            else:
                pnl_tracker.peak_equity = max(
                    float(getattr(pnl_tracker, "peak_equity", pnl_tracker.starting_equity)),
                    authoritative_live_equity,
                )
                if float(getattr(pnl_tracker, "peak_equity", 0.0)) > 0:
                    pnl_tracker.max_drawdown = max(
                        float(getattr(pnl_tracker, "max_drawdown", 0.0)),
                        (
                            float(pnl_tracker.peak_equity) - authoritative_live_equity
                        ) / float(pnl_tracker.peak_equity),
                    )
        except Exception as e:
            print(f"[TRACKER ALIGN WARN] {e}")

        divergence_msg = None

        top_cluster = cluster_amplifier.top_cluster()
        cluster_pct = (
            cluster_risk_governor.cluster_share(top_cluster) * 100
            if top_cluster
            else 0.0
        )

        dynamic_limit = min(
            concurrency_controller.evaluate_limit(
                open_positions,
                cluster_pct,
                total_unrealized,
            ),
            hard_position_limit(),
        )

        role_profile = SESSION_USER_CTX.get("role_profile", {})
        now_epoch = time.time()
        session_age_seconds = max(0, int(now_epoch - float(current_status.get("created", now_epoch))))
        idle_age_seconds = max(0, int(now_epoch - float(current_status.get("last_activity", now_epoch))))
        idle_remaining = max(0, int(current_status.get("idle_timeout_seconds", SESSION_IDLE_TIMEOUT_SECONDS)) - idle_age_seconds)
        max_remaining = max(0, int(current_status.get("max_session_seconds", SESSION_MAX_SECONDS)) - session_age_seconds)
        lock_state = get_session_lock_state()

        print("--- SESSION CONTEXT ---")
        print(f"USER ID: {SESSION_USER_CTX.get('user_id')} | NAME: {SESSION_USER_CTX.get('display_name')}")
        print(f"DISPLAY NAME: {SESSION_USER_CTX.get('display_name')}")
        print(f"ROLE: {SESSION_USER_CTX.get('role')}")
        print(f"UNIT: {SESSION_USER_CTX.get('unit_code')}")
        print(f"HOME BRANCH: {SESSION_USER_CTX.get('home_branch')}")
        print(f"SESSION ID: {SESSION_USER_CTX.get('session_id')}")
        print(f"COMPUTER NAME: {SESSION_USER_CTX.get('computer_name')}")
        print(f"LOGIN CHANNEL: {SESSION_USER_CTX.get('login_channel')}")
        print(f"SESSION ACTIVE: {'YES' if current_status.get('active') else 'NO'}")
        print(f"DEFENSIVE MODE ACTIVE: {'YES' if is_session_locked() else 'NO'}")
        print(f"SESSION LOCK REASON: {lock_state.get('reason') or 'NONE'}")
        print(f"SESSION AGE SEC: {session_age_seconds}")
        print(f"IDLE TIMEOUT SEC: {current_status.get('idle_timeout_seconds', SESSION_IDLE_TIMEOUT_SECONDS)}")
        print(f"MAX SESSION SEC: {current_status.get('max_session_seconds', SESSION_MAX_SECONDS)}")
        print(f"IDLE REMAINING SEC: {idle_remaining}")
        print(f"MAX REMAINING SEC: {max_remaining}")
        print(f"CAN ARM BROKER: {'YES' if role_profile.get('can_arm_broker') else 'NO'}")
        print(f"CAN LIVE MODE: {'YES' if role_profile.get('can_use_live_broker_mode') else 'NO'}")
        print(f"CAN PAPER EXECUTE: {'YES' if role_profile.get('can_execute_paper_trading') else 'NO'}")
        print(f"CAN LIVE EXECUTE: {'YES' if role_profile.get('can_execute_live_trading') else 'NO'}")
        print(f"ALLOWED ENGINE MODES: {', '.join(role_profile.get('allowed_engine_modes', [])) or 'NONE'}")

        print_authentication_status_panel(current_status)
        print_broker_credential_diagnostics()

        if SELECTED_BROKER == "OANDA":
            print_oanda_broker_status()
            print("--- COINBASE BROKER STATUS ---")
            print("COINBASE SELECTED: NO")
            print("COINBASE CONNECTED: NO")
        elif SELECTED_BROKER == "COINBASE":
            print("--- OANDA BROKER STATUS ---")
            print("OANDA SELECTED: NO")
            print("OANDA CONNECTED: NO")
            print("OANDA OPEN TRADES: N/A")
            print_coinbase_broker_status()
        else:
            print("--- OANDA BROKER STATUS ---")
            print("OANDA SELECTED: NO")
            print("OANDA CONNECTED: NO")
            print("OANDA OPEN TRADES: N/A")
            print("--- COINBASE BROKER STATUS ---")
            print("COINBASE SELECTED: NO")
            print("COINBASE CONNECTED: NO")

        print("--- BROKER EXECUTION CONTROL ---")
        labels = []
        labels.append("=========================")
        labels.append(f"BROKER EXECUTION : {broker_execution_status_label()}")
        labels.append(f"SELECTED BROKER  : {selected_broker_status_label()}")
        labels.append(f"BROKER MODE      : {SELECTED_BROKER_MODE}")
        labels.append(f"BROKER HEALTH    : {getattr(oanda, 'health_state', 'GREEN')}")
        
        # Phase 118D-1 Auto-Flatten Simulation Mode
        labels.append("")
        labels.append("=== AUTO FLATTEN STATUS ===")
        labels.append("Simulation Enabled: YES")
        labels.append(f"Confirmed Divergences: {_DIVERGENCE_STATE['confirmed_count']}")
        labels.append(f"Pending Simulations: {_DIVERGENCE_STATE['pending_count']}")
        
        last_sim = _DIVERGENCE_STATE.get("last_simulation")
        if last_sim:
            sim_lines = last_sim.split("\n")
            labels.append("Last Simulation Result:")
            for line in sim_lines:
                labels.append(f"  {line}")
        else:
            labels.append("Last Simulation Result: None")
            
        labels.append("=========================")
        for l in labels: print(l)
        print(f"EXECUTION SCOPE: {active_execution_scope_label()}")

        print("--- LIVE EXECUTION SUMMARY ---")
        print(f"REALIZED PNL: {total_realized:+.4f}")
        print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
        print(f"TOTAL EQUITY PNL: {total_equity:+.4f}")
        print(f"BALANCE: {observer_balance:+.4f}")

        print("--- PNL RECONCILIATION ---")
        print(f"OBSERVER REALIZED PNL: {observer_realized:+.4f}")
        print(f"OBSERVER UNREALIZED PNL: {observer_unrealized:+.4f}")
        print(f"OBSERVER EQUITY: {observer_equity:+.4f}")
        print(f"OBSERVER BALANCE: {observer_balance:+.4f}")
        print(f"MTM REALIZED PNL: {mtm_realized:+.4f}")
        print(f"MTM UNREALIZED PNL: {mtm_unrealized:+.4f}")
        print("[PNL AUTHORITY] MTM/accounting PnL is authoritative; observer retained as compatibility mirror.")
        observer_gap_realized = round(abs(float(mtm_realized) - float(observer_realized)), 6)
        observer_gap_unrealized = round(abs(float(mtm_unrealized) - float(observer_unrealized)), 6)
        if observer_gap_realized or observer_gap_unrealized:
            print(
                f"[OBSERVER MIRROR GAP] realized_gap={observer_gap_realized:.6f} "
                f"unrealized_gap={observer_gap_unrealized:.6f}"
            )

        for line in pnl_by_asset_category_dashboard_lines(
            aggregate_pnl_by_asset_category(
                realized_pnl_maps=current_realized_pnl_maps_by_asset_category(),
                positions=[
                    pos
                    for pos in mtm_engine.positions
                    if not pos.get("forced_exit")
                ],
            )
        ):
            print(line)

        open_counts_by_asset = mtm_engine.count_open_positions_by_asset()

        print(f"OPEN POSITIONS: {open_positions} / {hard_position_limit()}")
        print(
            "OPEN BY ASSET: "
            f"CRYPTO {open_counts_by_asset['CRYPTO']}/{hard_asset_cap('CRYPTO')} | "
            f"FX {open_counts_by_asset['FX']}/{hard_asset_cap('FX')} | "
            f"FUTURES {open_counts_by_asset['FUTURES']}/{hard_asset_cap('FUTURES')} | "
            f"OPTIONS {open_counts_by_asset['OPTIONS']}/{hard_asset_cap('OPTIONS')}"
        )
        print(f"ADAPTIVE POSITION LIMIT: {dynamic_limit}")
        print(f"BROKER TEST POSITIONS: {broker_test_positions}")
        print(f"DEFENSIVE REDUCTIONS THIS CYCLE: {defensive_reductions}")
        print(f"TOTAL DEFENSIVE REDUCTION EXITS: {locked_profit_ledger.defensive_reduction_exits}")

        capital_source = capital_governor.capital_source_label()
        print(
            f"{capital_source} CAPITAL DEPLOYED: "
            f"${capital_governor.funded_amount():.2f}"
        )
        print(
            f"{capital_source} CAPITAL AVAILABLE: "
            f"${capital_governor.available_capital():.2f}"
        )

        print(f"ENGINE MODE: {ENGINE_MODE}")
        print(
            f"FORCED EXIT PROFITS: "
            f"{locked_profit_ledger.forced_exit_profit_banked:+.4f}"
        )
        print(
            f"CLUSTER SATURATION: "
            f"{top_cluster if top_cluster else 'NONE'} {cluster_pct:.1f}%"
        )
        print(f"LAST TRADE: {last_trade}")
        print("-" * 60)

        live_fx_funded_this_cycle = 0
        live_crypto_funded_this_cycle = 0
        new_counts_this_cycle = {
            "CRYPTO": 0,
            "FX": 0,
            "OPTIONS": 0,
            "FUTURES": 0,
        }

        if is_session_locked():
            if defensive_reductions > 0:
                print(
                    f"[DEFENSIVE MODE] New trade creation blocked. "
                    f"Reduced exposure by {defensive_reductions} positions this cycle."
                )
            else:
                print("[DEFENSIVE MODE] New trade creation blocked. Managing existing positions only.")
        elif max_remaining <= 0:
            if not _SESSION_QUIET_MODE_ACTIVATED:
                _SESSION_QUIET_MODE_ACTIVATED = True
                print("[SESSION EXPIRED QUIET MODE] Trading attempts paused until re-authentication.")
                try:
                    _safe_emit_alert(
                        "emit_system_alert",
                        severity=AlertSeverity.WARNING,
                        message="Session Expired Quiet Mode activated. Trading paused.",
                        metadata={"cycle": cycle}
                    )
                except Exception:
                    pass
            else:
                print("[SESSION EXPIRED QUIET MODE] Trading attempts paused until re-authentication.")
        elif mtm_engine.count_open_positions() < hard_position_limit():
            if not role_profile.get("can_execute_paper_trading", False):
                print("[RBAC] New position generation blocked for current role.")
            else:
                for asset_class, symbol, sig, prob in select_cycle_candidates():
                    # =========================
                    # MODE-AWARE ENTRY FILTER
                    # =========================
                    mode_filter = {
                        "SAFE": (12.5, 0.55),
                        "CONSERVATIVE": (12.0, 0.50),
                        "BALANCED": (11.0, 0.40),
                        "AGGRESSIVE": (10.5, 0.36),
                        "EXPANSION": (10.0, 0.32),
                    }

                    min_sig, min_prob = mode_filter.get(ENGINE_MODE, (11.5, 0.65))

                    # PCNRASS profitability guardrail:
                    # avoid very weak/noisy entries while preserving existing mode behavior.
                    if sig < min_sig or prob < min_prob:
                        continue

                    if sig < 10.0:
                        continue

                    current_open_counts = mtm_engine.count_open_positions_by_asset()

                    if not concurrency_controller.can_add_position(
                        mtm_engine.count_open_positions()
                    ):
                        break

                    if mtm_engine.count_open_positions() >= hard_position_limit():
                        break

                    allowed_to_open, open_reason = can_open_position(
                        asset_class,
                        open_counts=current_open_counts,
                        new_counts_this_cycle=new_counts_this_cycle,
                    )
                    if not allowed_to_open:
                        continue

                    if asset_class == "CRYPTO":
                        safe_load_runtime_asset(symbol)

                    allow_broker_test = False

                    if (
                        asset_class == "FX"
                        and SELECTED_BROKER == "OANDA"
                        and live_fx_funded_this_cycle < max_new_per_cycle("FX")
                    ):
                        allow_broker_test = True

                    if (
                        asset_class == "CRYPTO"
                        and SELECTED_BROKER == "COINBASE"
                        and live_crypto_funded_this_cycle < max_new_per_cycle("CRYPTO")
                    ):
                        allow_broker_test = True

                    gate_ok, gate_reason = approve_trade_before_register(
                        asset_class=asset_class,
                        symbol=symbol,
                        sig=sig,
                        prob=prob,
                    )

                    if not gate_ok:
                        last_trade = f"{symbol} UNIFIED_GATE_BLOCKED {gate_reason}"
                        continue

                    r14f_ok, r14f_score, r14f_threshold = _legacy_css_profitability_allows(
                        symbol=symbol,
                        asset_class=asset_class,
                        sig=sig,
                        prob=prob,
                    )

                    if not r14f_ok:
                        last_trade = f"{symbol} R14F_BLOCKED"
                        continue

                    position = mtm_engine.register_position(
                        asset_class,
                        symbol,
                        sig,
                        prob,
                        allow_live_funding=allow_broker_test,
                    )
                    new_counts_this_cycle[asset_class] += 1

                    observer_position = Position(
                        symbol=f"{position['position_id']}::{symbol}",
                        asset_class=asset_class,
                        side="LONG",
                        quantity=1.0,
                        entry_price=100.0,
                        current_price=100.0,
                    )
                    pnl_observer.add_position(observer_position)
                    exit_signal = evaluate_exit_signal(position)
                    print(f"[R15A EXIT] {symbol} signal={exit_signal}")

                    if position.get("broker_tested"):
                        if asset_class == "FX" and SELECTED_BROKER == "OANDA":
                            live_fx_funded_this_cycle += 1
                            resolved_expected_price = resolve_expected_fx_price(symbol)
                            ok, broker_msg, t_id, f_price, e_time, slippage = attempt_oanda_fx_execution(symbol, expected_price=resolved_expected_price)

                            if ok and t_id:
                                position["broker_expected_price"] = resolved_expected_price
                                position["broker_trade_id"] = t_id
                                position["broker_fill_price"] = f_price
                                position["broker_execution_time"] = e_time
                                position["broker_slippage"] = slippage
                                perform_post_trade_verification(t_id, symbol, FX_LIVE_UNITS)

                        elif asset_class == "CRYPTO" and SELECTED_BROKER == "COINBASE":
                            live_crypto_funded_this_cycle += 1
                            ok, broker_msg = attempt_coinbase_crypto_execution(symbol)

                        else:
                            ok, broker_msg = False, "BROKER_ASSET_MISMATCH"

                        if ok:
                            position["broker_order_ok"] = True
                            position["broker_note"] = broker_msg
                            last_trade = f"{symbol} BROKER_EXECUTED {broker_msg}"
                            print(
                                f"[{asset_class} BROKER EXECUTED] {symbol} opened | "
                                f"{broker_msg}"
                            )
                        else:
                            capital_governor.release_trade(position["position_id"])
                            position["broker_tested"] = False
                            position["live_funded"] = False
                            position["broker_order_ok"] = False
                            position["broker_note"] = broker_msg
                            last_trade = f"{symbol} PAPER_OPENED BROKER_BLOCKED {broker_msg}"
                            print(
                                f"[{asset_class} PAPER OPENED] {symbol} opened | "
                                f"BROKER_BLOCKED | {broker_msg}"
                            )

                    else:
                        last_trade = f"{symbol} PAPER_OPENED"
                        _safe_emit_alert("emit_trade_alert", severity=AlertSeverity.INFO, message=f"Paper Trade Opened: {symbol}", metadata={"symbol": symbol, "asset_class": asset_class})
                        print(f"[{asset_class} PAPER OPENED] {symbol}")
        else:
            _safe_emit_alert("emit_risk_alert", severity=AlertSeverity.WARNING, message="Capital Governor restriction: hard open-position cap reached")
            print("[SIGNAL GENERATION PAUSED] hard open-position cap reached")


        session_recovery.save_state(
            cycle=cycle,
            crypto_pnl=crypto_pnl,
            fx_pnl=fx_pnl,
            options_pnl=options_pnl,
            futures_pnl=futures_pnl,
            last_trade=last_trade,
            position_counter=mtm_engine.position_counter,
        )

        
        try:
            new_positions = []
            for pos in mtm_engine.positions:
                if pos["forced_exit"]:
                    continue
                new_positions.append(
                    NewPosition(
                        symbol=pos["symbol"],
                        side="LONG",
                        entry_price=float(pos.get("entry_price", 100.0)),
                        current_price=float(pos.get("current_price", pos.get("entry_price", 100.0))),
                        quantity=1.0,
                        instrument_spec=InstrumentSpec(
                            symbol=pos["symbol"],
                            asset_class=pos["asset_class"],
                            multiplier=1.0,
                        ),
                        entry_cost=ExecutionCost(),
                        estimated_exit_cost=ExecutionCost(),
                    )
                )

            snapshot = compute_portfolio_snapshot(
                new_positions,
                starting_equity=float(pnl_observer.starting_balance) + float(total_realized),
            )

            print("--- NEW ACCOUNTING ENGINE ---")
            print(f"NET UNREALIZED: {snapshot.total_net_unrealized:+.4f}")
            print(f"LIVE EQUITY: {snapshot.live_equity:+.4f}")

            tracker_snapshot = pnl_tracker.equity_snapshot()
            capital_snapshot = getattr(capital_governor, "balance_snapshot", {})
            drawdown_display = canonical_drawdown_display(
                current_equity=tracker_snapshot.get("current_equity"),
                peak_equity=tracker_snapshot.get("peak_equity"),
                max_drawdown_pct=5.0,
                capital_state=capital_snapshot.get("capital_state", "CAPITAL_UNAVAILABLE"),
                drawdown_reason=str(capital_snapshot.get("drawdown_reason", "")),
            )
            print("--- TRACKER PERFORMANCE ---")
            print(f"TRACKER EQUITY: {tracker_snapshot['current_equity']:+.4f}")
            print(f"PEAK EQUITY: {tracker_snapshot['peak_equity']:+.4f}")
            print(f"DRAWDOWN: {drawdown_display['drawdown_display']}")
            if drawdown_display["drawdown_status"] == "NOT_COMPUTABLE":
                print(f"DRAWDOWN REASON: {drawdown_display['drawdown_reason'] or 'Capital state unavailable'}")
                print(f"CAPITAL STATE: {drawdown_display['capital_state']}")

            runtime_supervisor.record_cycle(
                equity=tracker_snapshot['current_equity'],
                broker_mode=str(SELECTED_BROKER_MODE),
                engine_mode=str(ENGINE_MODE)
            )
            
            stats = runtime_supervisor.get_stats()
            print("--- RUNTIME SUPERVISOR ---")
            print(f"UPTIME: {stats.get('uptime_seconds', 0)}s | CYCLES: {stats.get('cycles_completed', 0)}")
            print(f"RECOVERIES: {stats.get('recovery_attempts', 0)} | ALERTS: {stats.get('alerts_generated', 0)}")
            print(f"DISCONNECTS: {stats.get('broker_disconnects', 0)} | ERRORS: {stats.get('runtime_errors', 0)}")

            publish_result = pcnrass_publish_runtime_artifacts(
                cycle,
                supervisor_stats=stats,
                tracker_snapshot=tracker_snapshot,
            )
            if publish_result.get("status") != "OK":
                print(f"[RUNTIME ARTIFACT PUBLISH WARN] {publish_result.get('warnings', [])}")

        except Exception as e:
            runtime_supervisor.record_error(str(e))
            print(f"[NEW PNL ERROR] {e}")

        render_trade_dashboard_summary()

        if not pcnrass_wait_for_next_cycle(cycle):

            close_active_session("operator_quit_after_cycle")

            break

        time.sleep(1)

except KeyboardInterrupt:
    print("[SESSION STOPPED] Keyboard interrupt received.")
    _safe_emit_alert("emit_engine_alert", severity=AlertSeverity.INFO, message="CSS Runtime Engine Stopped Normally (KeyboardInterrupt)", metadata={"cycle": cycle})
    close_active_session(
        "keyboard_interrupt",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "defensive_mode_active": is_session_locked(),
        },
    )

except SystemExit:
    raise

except Exception as e:
    print(f"[FATAL ERROR] {str(e)[:200]}")
    if css_supervisor:
        css_supervisor.record_failure(str(e)[:200])
    _safe_emit_alert("emit_engine_alert", severity=AlertSeverity.CRITICAL, message=f"Runtime Exception: {str(e)[:200]}", metadata={"exception": type(e).__name__, "cycle": cycle})
    close_active_session(
        "runtime_error",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "error": str(e)[:200],
            "defensive_mode_active": is_session_locked(),
        },
    )
    raise

finally:
    if css_supervisor:
        css_supervisor.stop()
    _safe_emit_alert("emit_system_alert", severity=AlertSeverity.INFO, message="CSS Controlled Shutdown Initiated", metadata={"cycle": cycle})
    close_active_session(
        "normal_shutdown",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "defensive_mode_active": is_session_locked(),
        },
    )
# ===== PCNRASS FINAL ACCOUNT SETTLEMENT =====
def finalize_account_session() -> None:
    try:
        if "pcnrass_session_state" not in globals() or "pcnrass_account_state" not in globals():
            return

        new_balance = float(pcnrass_session_state.get("session_equity", 0.0))
        if new_balance <= 0:
            return

        pcnrass_account_state["account_balance"] = round(new_balance, 4)
        pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")

        if "ACCOUNT_STATE_FILE" in globals():
            Path(ACCOUNT_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
            Path(ACCOUNT_STATE_FILE).write_text(
                json.dumps(pcnrass_account_state, indent=2, default=str),
                encoding="utf-8",
            )

        print(f"[ACCOUNT UPDATED] new balance: {new_balance:.2f}")

    except Exception as e:
        print(f"[ACCOUNT SETTLEMENT ERROR] {e}")

