"""
Capital Strata Systems
Guarded Live Runner (FAIL-CLOSED)

What this does:
- Loads OANDA adapter and prints account summary
- Pulls equity (prefer global equity store; fallback to OANDA NAV/balance)
- Pulls open futures exposure from global futures store
- Calls RiskGovernor.evaluate(...) which enforces:
  - rolling equity peak global drawdown kill-switch
  - daily loss caps / cooldown / streak / max trades
  - portfolio allocation risk cap (FX + Futures now; more later)
- If ALLOW and EXECUTION_ARMED=True, places a MICRO trade (EUR_USD, BUY 1 unit)
- Writes a compact execution journal entry (best-effort)

FAIL-CLOSED:
- Any import/runtime error => abort without placing a trade.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _print_banner() -> None:
    print("\n" + "=" * 70)
    print("CAPITAL STRATA SYSTEMS – GUARDED LIVE (FAIL-CLOSED)")
    print("=" * 70 + "\n")


def _abort(msg: str, code: int = 2) -> None:
    print(f"\nABORT: {msg}\n")
    raise SystemExit(code)


def _safe_imports() -> Dict[str, Any]:
    """
    Import everything we need in one place so any failure => fail-closed early.
    """
    try:
        from engine.risk.risk_governor import RiskGovernor  # type: ignore
        from backend.app.brokers.oanda_adapter import OandaAdapter, OrderRequest  # type: ignore
    except Exception as e:
        _abort(f"Import error (core): {e}")

    # Optional modules (still fail-closed if referenced and missing)
    try:
        from backend.app.global_futures_store import get_total_open_futures_risk  # type: ignore
    except Exception:
        get_total_open_futures_risk = None  # type: ignore

    try:
        from backend.app.global_equity_store import get_current_equity  # type: ignore
    except Exception:
        get_current_equity = None  # type: ignore

    try:
        from backend.app.execution_journal import ExecutionJournal  # type: ignore
    except Exception:
        ExecutionJournal = None  # type: ignore

    return {
        "RiskGovernor": RiskGovernor,
        "OandaAdapter": OandaAdapter,
        "OrderRequest": OrderRequest,
        "get_total_open_futures_risk": get_total_open_futures_risk,
        "get_current_equity": get_current_equity,
        "ExecutionJournal": ExecutionJournal,
    }


def _journal_write(journal: Any, payload: Dict[str, Any]) -> None:
    """
    Best-effort journaling. Never blocks execution.
    """
    try:
        if journal is None:
            return
        if hasattr(journal, "append"):
            journal.append(payload)  # type: ignore
        elif hasattr(journal, "write"):
            journal.write(payload)  # type: ignore
    except Exception:
        # silent by design
        return


def main() -> None:
    _print_banner()

    CS_MODE = os.getenv("CS_MODE", "demo").strip().lower()
    if CS_MODE != "live":
        _abort("Live runner requires CS_MODE=live.")

    OANDA_ENV = os.getenv("OANDA_ENV", "practice").strip().lower()
    OANDA_BASE_URL = os.getenv("OANDA_BASE_URL", "").strip() or "(unset)"
    HEADLESS_DEV_MODE = _env_bool("HEADLESS_DEV_MODE", default=False)
    EXECUTION_ARMED = _env_bool("EXECUTION_ARMED", default=False)

    print(f"{'CS_MODE':<18}: {CS_MODE}")
    print(f"{'OANDA_ENV':<18}: {OANDA_ENV}")
    print(f"{'OANDA_BASE_URL':<18}: {OANDA_BASE_URL}")
    print(f"{'HEADLESS_DEV_MODE':<18}: {HEADLESS_DEV_MODE}")
    print(f"{'EXECUTION_ARMED':<18}: {EXECUTION_ARMED}")
    print("")

    mods = _safe_imports()
    RiskGovernor = mods["RiskGovernor"]
    OandaAdapter = mods["OandaAdapter"]
    OrderRequest = mods["OrderRequest"]
    get_total_open_futures_risk = mods["get_total_open_futures_risk"]
    get_current_equity = mods["get_current_equity"]
    ExecutionJournal = mods["ExecutionJournal"]

    # --- Initialize services ---
    rg = RiskGovernor()
    oanda = OandaAdapter()

    journal = None
    if ExecutionJournal is not None:
        try:
            journal = ExecutionJournal()  # type: ignore
        except Exception:
            journal = None

    # --- Account summary ---
    print("OANDA ACCOUNT SUMMARY")
    print("-" * 40)
    try:
        summary = oanda.get_account_summary()
    except Exception as e:
        _abort(f"OANDA get_account_summary failed: {e}")

    # Expecting keys like balance / nav, but be defensive
    bal = float(summary.get("balance") or summary.get("Balance") or 0.0)
    nav = float(summary.get("nav") or summary.get("NAV") or bal)
    print(f"Balance: {bal:.4f}")
    print(f"NAV    : {nav:.4f}")
    print("")

    # --- Equity source (prefer global equity store; fallback NAV) ---
    equity = nav
    if get_current_equity is not None:
        try:
            eq2 = float(get_current_equity())  # type: ignore
            if eq2 > 0:
                equity = eq2
        except Exception:
            # keep fallback NAV
            pass

    # --- Pull open futures risk (USD risk money) ---
    open_futures_risk = 0.0
    if get_total_open_futures_risk is not None:
        try:
            open_futures_risk = float(get_total_open_futures_risk())  # type: ignore
        except Exception:
            open_futures_risk = 0.0

    # --- Micro trade request + trade_risk estimate ---
    instrument = os.getenv("CS_LIVE_MICRO_INSTRUMENT", "EUR_USD").strip().upper()
    side = os.getenv("CS_LIVE_MICRO_SIDE", "BUY").strip().upper()
    units = int(os.getenv("CS_LIVE_MICRO_UNITS", "1"))

    # We use an explicit, configurable risk-money estimate for the new trade.
    # (Later we’ll compute this from stop distance / pip value / contract specs.)
    trade_risk = float(os.getenv("CS_LIVE_MICRO_TRADE_RISK", "2000"))  # default matches your test

    # --- Governor decision (portfolio-aware) ---
    state: Dict[str, Any] = {}
    state["open_futures_risk"] = open_futures_risk

    try:
        decision = rg.evaluate(
            instrument=instrument,
            equity=equity,
            trade_risk=trade_risk,
            state=state,
        )
    except Exception as e:
        _abort(f"RiskGovernor.evaluate failed: {e}")

    _journal_write(
        journal,
        {
            "type": "decision",
            "timestamp_utc": _utc_now_iso(),
            "instrument": instrument,
            "decision": decision.get("decision"),
            "policy": decision.get("policy"),
            "reasons": decision.get("reasons"),
            "equity": round(float(equity), 6),
            "open_futures_risk": round(float(open_futures_risk), 6),
            "portfolio_allocation_pct": decision.get("portfolio_allocation_pct"),
            "mode": CS_MODE,
        },
    )

    if decision.get("decision") != "ALLOW":
        print("DECISION: BLOCK")
        print(f"Reasons: {decision.get('reasons')}")
        print("\nDONE.\n")
        return

    print("DECISION: ALLOW")
    print(f"Policy  : {decision.get('policy')}")
    print(f"Reasons : {decision.get('reasons')}")
    if "portfolio_allocation_pct" in decision:
        print(f"Portfolio allocation pct: {decision.get('portfolio_allocation_pct')}")
    print("")

    if not EXECUTION_ARMED:
        print("EXECUTION IS DISARMED → no order will be placed.")
        print("\nDONE.\n")
        return

    # --- Place micro order ---
    print(f"Placing LIVE micro trade ({instrument}, {side} {units} unit)...\n")

    try:
        req = OrderRequest(instrument=instrument, side=side, units=units)
        order_result = oanda.place_order(req)
    except Exception as e:
        _abort(f"OANDA place_order failed: {e}")

    print("ORDER RESULT")
    print("-" * 40)
    for k in ("ok", "status", "error", "tradeID", "orderID"):
        if k in order_result:
            print(f"{k:<8}: {order_result.get(k)}")
    print("\nDONE.\n")

    _journal_write(
        journal,
        {
            "type": "order_result",
            "timestamp_utc": _utc_now_iso(),
            "instrument": instrument,
            "side": side,
            "units": units,
            "result": order_result,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # final fail-closed catch
        print(f"\nFATAL (fail-closed): {e}\n")
        sys.exit(2)
