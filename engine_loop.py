"""
engine_loop.py
==============

Canonical EngineLoop implementation for Capital Strata Systems (CSS) / REA.

Purpose:
- Provide a stable EngineLoop class (importable by runners)
- Run a safe, fail-closed "step" that exercises wiring without enabling live trading
- Prefer the canonical guarded entrypoint:
      backend.app.headless_guarded_entry.run_headless(req, cfg)

Safety defaults:
- allow_live = False
- execution_armed = False
- mode defaults to TEST/SIMULATION behavior

Usage:
  python -u engine_loop.py
"""

from __future__ import annotations

import os
import sys
import json
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_best_effort() -> bool:
    """
    Best-effort .env load from repo root.
    Returns True if load attempted successfully, else False.
    """
    env_path = Path(".env")
    if not env_path.exists():
        return False

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return False

    load_dotenv(dotenv_path=str(env_path), override=False)
    return True


@dataclass(frozen=True)
class LoopConfig:
    """
    EngineLoop local config.
    """
    allow_live: bool = False
    execution_armed: bool = False
    mode: str = "TEST"
    fx_provider: str = "oanda"
    fx_instrument: str = "EUR_USD"
    fx_timeframe: str = "1m"
    oanda_env: str = "practice"

    # optional diagnostic inputs
    bars_5m: int = 60
    vol_norm_0_1: float = 0.35
    spread_bps: float = 1.2
    high_risk_news: bool = False
    volatility_ratio: float = 1.0

    # optional sizing / capital context
    equity: Optional[float] = None
    equity_peak: Optional[float] = None
    equity_risk: Optional[float] = 500.0  # safe default if caller wants it


class EngineLoop:
    """
    Canonical EngineLoop.

    step():
      - calls guarded headless entrypoint if available
      - returns a dict diagnostics payload
    """

    def __init__(self, cfg: Optional[LoopConfig] = None) -> None:
        self.engine_run_id = f"css-{uuid4()}"
        self.repo_root = str(Path(__file__).resolve().parent)
        self.cfg = cfg or self._cfg_from_env()

        # ensure repo root importable (backend.*, engine.*)
        if self.repo_root not in sys.path:
            sys.path.insert(0, self.repo_root)

        self.env_loaded = _load_env_best_effort()

    def _cfg_from_env(self) -> LoopConfig:
        def _f(name: str, default: str) -> str:
            v = os.environ.get(name)
            return v if v is not None and str(v).strip() != "" else default

        def _fb(name: str, default: bool) -> bool:
            v = os.environ.get(name)
            if v is None:
                return default
            s = str(v).strip().lower()
            return s in ("1", "true", "yes", "y", "on")

        def _fi(name: str, default: int) -> int:
            v = os.environ.get(name)
            try:
                return int(v) if v is not None else default
            except Exception:
                return default

        def _ff(name: str, default: float) -> float:
            v = os.environ.get(name)
            try:
                return float(v) if v is not None else default
            except Exception:
                return default

        return LoopConfig(
            allow_live=_fb("ALLOW_LIVE", False),
            execution_armed=_fb("EXECUTION_ARMED", False),
            mode=_f("MODE", "TEST"),
            fx_provider=_f("FX_PROVIDER", _f("FX_PROVIDER", "oanda")),
            fx_instrument=_f("FX_INSTRUMENT", "EUR_USD"),
            fx_timeframe=_f("FX_TIMEFRAME", "1m"),
            oanda_env=_f("OANDA_ENV", "practice"),
            bars_5m=_fi("BARS_5M", 60),
            vol_norm_0_1=_ff("VOL_NORM_0_1", 0.35),
            spread_bps=_ff("SPREAD_BPS", 1.2),
            high_risk_news=_fb("HIGH_RISK_NEWS", False),
            volatility_ratio=_ff("VOLATILITY_RATIO", 1.0),
            equity=None,
            equity_peak=None,
            equity_risk=_ff("EQUITY_RISK", 500.0),
        )

    def _build_req(self) -> Dict[str, Any]:
        """
        Minimal request payload.
        Keep it safe + deterministic.
        """
        return {
            "engine_run_id": self.engine_run_id,
            "ts_utc": _utc_now(),
            "mode": "SIMULATION" if str(self.cfg.mode).upper() == "TEST" else str(self.cfg.mode),
            "symbol": str(self.cfg.fx_instrument).replace("_", ""),  # EUR_USD -> EURUSD (headless uses EURUSD in prints)
            "fx_provider": self.cfg.fx_provider,
            "fx_instrument": self.cfg.fx_instrument,
            "fx_timeframe": self.cfg.fx_timeframe,
            "oanda_env": self.cfg.oanda_env,
            # safety:
            "allow_live": bool(self.cfg.allow_live),
            "execution_armed": bool(self.cfg.execution_armed),
            # diagnostics:
            "bars_5m": int(self.cfg.bars_5m),
            "vol_norm_0_1": float(self.cfg.vol_norm_0_1),
            "spread_bps": float(self.cfg.spread_bps),
            "high_risk_news": bool(self.cfg.high_risk_news),
            "volatility_ratio": float(self.cfg.volatility_ratio),
            # capital context (optional)
            "equity": self.cfg.equity,
            "equity_peak": self.cfg.equity_peak,
            "equity_risk": self.cfg.equity_risk,
            "note": "EngineLoop.step() probe (fail-closed)",
        }

    def step(self) -> Dict[str, Any]:
        """
        Execute one safe loop step.

        Returns a diagnostics dict, always.
        """
        req = self._build_req()

        # try canonical guarded headless entrypoint
        try:
            from backend.app.headless_guarded_entry import run_headless, HeadlessConfig  # type: ignore
        except Exception as e:
            return {
                "ok": False,
                "where": "engine_loop.step",
                "reason": "guarded_entry_import_failed",
                "error": repr(e),
                "req": req,
            }

        # construct cfg (fail-closed)
        try:
            cfg = HeadlessConfig(allow_live=False)  # type: ignore[call-arg]
        except Exception as e:
            return {
                "ok": False,
                "where": "engine_loop.step",
                "reason": "headless_config_construct_failed",
                "error": repr(e),
                "req": req,
            }

        try:
            result = run_headless(req, cfg)  # type: ignore[misc]
        except Exception as e:
            return {
                "ok": False,
                "where": "engine_loop.step",
                "reason": "run_headless_exception",
                "error": repr(e),
                "traceback": traceback.format_exc(),
                "req": req,
            }

        # ensure json-safe / printable
        return {
            "ok": True,
            "engine_run_id": self.engine_run_id,
            "env_loaded": bool(self.env_loaded),
            "result": result,
        }


def main() -> int:
    print("=" * 70)
    print("REA Capital / CSS — EngineLoop (canonical)")
    print(f"cwd: {Path.cwd()}")
    print(f"python: {sys.version.split()[0]}")
    print(f"venv: {os.environ.get('VIRTUAL_ENV', '')}")
    print("=" * 70)

    loop = EngineLoop()
    out = loop.step()

    try:
        print(json.dumps(out, indent=2, default=str))
    except Exception:
        print(out)

    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
