"""Preflight for the two-track simulation. The 48-hour clock may start only if every REQUIRED check passes.

Each check returns PASS / FAIL (required) or WARN (reported, does not block). Nothing here places
an order; market-data checks contact read-only public endpoints only.
"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from backend.signals.candles import LIVE, CandleError, check_fresh
from backend.signals.market_data import check_clock_skew, measure_clock_skew, series_metrics
from backend.signals.producer import CalibrationApprovals
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.capital_profiles import ENGINEERING_CAPITAL_CAD
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, SIMULATED_DEFAULT_PERSONALITY

# Modules that can place real orders. None may be loaded in the simulation process.
FORBIDDEN_MODULE_PREFIXES = ("coinbase.rest", "backend.app.brokers.oanda_adapter", "engine.brokers", "backend.brokers",
                             "execution_router", "alpaca.trading", "oandapyV20", "broker_oanda")


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS | FAIL | WARN
    detail: str
    required: bool = True


def _check(name: str, ok: bool, detail: str, *, required: bool = True) -> Check:
    return Check(name, "PASS" if ok else ("FAIL" if required else "WARN"), detail, required)


def run_preflight(*, root: Path | str, artifacts: Sequence[Mapping[str, Any]], approvals_root: Path | str,
                  fetch: Callable[[str, int], Any], quote: Callable[[str], Any] | None,
                  server_time: Callable[[], datetime] | None, capital_cad: float,
                  env: Mapping[str, str] | None = None, now: datetime | None = None,
                  local_clock: Callable[[], datetime] | None = None,
                  loaded_modules: Sequence[str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    root = Path(root)
    checks: list[Check] = []

    # --- broker isolation and live safety --------------------------------------------------
    loaded = sorted(m for m in (sys.modules if loaded_modules is None else loaded_modules)
                    if m.startswith(FORBIDDEN_MODULE_PREFIXES))
    checks.append(_check("broker_isolation", not loaded, "no order-capable broker module loaded" if not loaded
                         else f"loaded: {loaded}"))
    try:
        cad146.refuse_if_live_armed(env)
        armed = None
    except cad146.SimulationError as exc:
        armed = str(exc)
    checks.append(_check("no_live_arming", armed is None, armed or "no live-arming variables set"))
    checks.append(_check("live_kill_switch_engaged", cad146.live_kill_switch_engaged(env),
                         f"{cad146.LIVE_KILL_SWITCH_ENV} must stay engaged for the whole trial"))
    checks.append(_check("sim_entries_enabled", not cad146.sim_entry_halted(env),
                         f"{cad146.SIM_ENTRY_HALT_ENV} must be clear to start"))
    global_kill = str(env.get("REA_KILL_SWITCH", "")).strip().lower() in {"1", "true", "yes", "y", "on"} \
        or Path("runtime/kill.switch").exists()
    checks.append(_check("global_emergency_stop_clear", not global_kill, "REA_KILL_SWITCH / runtime/kill.switch"))

    # --- trader configuration ------------------------------------------------------------
    checks.append(_check("designated_trader", AUTONOMOUS_SOURCE_ID == "CSS_AUTONOMOUS_ENGINE",
                         f"{AUTONOMOUS_SOURCE_ID}, Simulated Trading, {SIMULATED_DEFAULT_PERSONALITY.value}, SAFE"))
    checks.append(_check("engineering_capital", float(capital_cad) == float(ENGINEERING_CAPITAL_CAD),
                         f"CAD {float(capital_cad):,.2f} (engineering trial requires CAD {float(ENGINEERING_CAPITAL_CAD):,.2f})"))

    # --- artifacts and approvals ----------------------------------------------------------
    instruments = sorted({(a["instrument"], int(a["granularity_s"])) for a in artifacts})
    checks.append(_check("calibration_artifacts_present", bool(instruments),
                         f"{len(artifacts)} artifacts for {instruments}" if instruments
                         else "no artifacts: neither track can produce a signal"))
    approvals = CalibrationApprovals(approvals_root)
    approved = sum(1 for a in artifacts if approvals.status(a)[0])
    gates = sum(1 for a in artifacts if (a.get("gates") or {}).get("passed"))
    checks.append(_check("track_a_routable_artifacts", approved > 0,
                         f"{approved} dual-approved, {gates} passed gates: Track A will make zero trades"
                         if approved == 0 else f"{approved} dual-approved", required=False))
    missing_costs = sorted({a.get("asset_class") for a in artifacts} - set(DEFAULT_COSTS))
    checks.append(_check("cost_model", not missing_costs and bool(artifacts),
                         "cost model for " + ", ".join(sorted({a.get('asset_class') for a in artifacts}))
                         if not missing_costs else f"missing cost model: {missing_costs}"))

    # --- ledger isolation and persistence ---------------------------------------------------
    operational = cad146._is_operational(root)
    checks.append(_check("ledger_isolation", not operational, f"{root} is outside the operational paper book"
                         if not operational else f"{root} is the operational paper book"))
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=root, delete=False, suffix=".probe") as fh:
            fh.write("probe")
            fh.flush()
            os.fsync(fh.fileno())
            probe = Path(fh.name)
        persisted = probe.read_text() == "probe"
        probe.unlink()
        checks.append(_check("persistence", persisted, f"durable write/read in {root}"))
    except OSError as exc:
        checks.append(_check("persistence", False, f"{type(exc).__name__}: {exc}"))

    # --- market data: real, fresh, complete, quoted ----------------------------------------
    observed: list[dict[str, Any]] = []
    for inst, gran in instruments or [("BTC-USD", 3600)]:
        try:
            series = fetch(inst, gran)
            check_fresh(series, now=now)
            m = series_metrics(series)
            ok = series.classification == LIVE and m.completeness >= 0.98 and series.candles[-1].volume > 0
            detail = (f"{series.source} {inst} {gran}s: {len(series.candles)} bars, last "
                      f"{datetime.fromtimestamp(series.candles[-1].ts, tz=timezone.utc).isoformat()}, "
                      f"class {series.classification}, completeness {m.completeness:.3f}")
            observed.append({"instrument": inst, "granularity_s": gran, "source": series.source,
                             "data_sha256": series.digest, "last_close": series.candles[-1].close})
        except (CandleError, OSError, ValueError) as exc:
            ok, detail = False, f"{inst} {gran}s: {type(exc).__name__}: {exc}"[:300]
        checks.append(_check(f"market_data:{inst}:{gran}", ok, detail))
        if quote is not None:
            try:
                q = quote(inst)
                qok, qdetail = True, f"{inst} spread {q.spread_bps:.3f} bps at {q.exchange_ts.isoformat()}"
            except (CandleError, OSError, ValueError) as exc:
                qok, qdetail = False, f"{inst}: {type(exc).__name__}: {exc}"[:300]
            checks.append(_check(f"quote:{inst}", qok, qdetail))
    if server_time is not None:
        try:
            skew = measure_clock_skew(server_time, **({"clock": local_clock} if local_clock else {}))
            check_clock_skew(skew)
            checks.append(_check("clock_skew", True, f"{skew:.3f} s"))
        except (CandleError, OSError, ValueError, KeyError) as exc:
            checks.append(_check("clock_skew", False, f"{type(exc).__name__}: {exc}"[:300]))

    failed = [c for c in checks if c.status == "FAIL"]
    return {"at_utc": now.isoformat(), "verdict": "PASS" if not failed else "FAIL",
            "checks": [c.__dict__ for c in checks], "blockers": [f"{c.name}: {c.detail}" for c in failed],
            "observations": observed, "real_orders": 0}
