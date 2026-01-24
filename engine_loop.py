"""
engine_loop.py — REA Capital Trading Engine (Prompt-Only)

This version integrates Module 3 VWAP mean-reversion prompt generation via:
  signals.vwap_mean_reversion.build_vwap_prompt_default_eps

Hard constraints:
- NO trade execution
- NO auto-risk escalation
- Prompt/diagnostics only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Deque, Tuple
from collections import deque
import csv
import os
from datetime import datetime, timezone


# -----------------------------
# Optional imports (resilient)
# -----------------------------
try:
    # Your repo likely has this
    from signals.vwap_mean_reversion import build_vwap_prompt_default_eps
except Exception as e:
    raise ImportError(
        "Could not import build_vwap_prompt_default_eps from signals.vwap_mean_reversion. "
        "Confirm signals/vwap_mean_reversion.py defines that function and that you saved it."
    ) from e

# RegimeGate is optional; if unavailable we ALLOW by default
try:
    from regime.gate import RegimeGate  # type: ignore
except Exception:
    RegimeGate = None  # type: ignore


# -----------------------------
# Data model (minimal)
# -----------------------------
@dataclass
class Bar:
    """
    Minimal bar representation for VWAP computation.
    """
    ts_utc: datetime
    symbol: str
    close: float
    volume: float = 1.0


# -----------------------------
# Config
# -----------------------------
@dataclass
class EngineConfig:
    symbol: str = "SPY"
    vwap_window_bars: int = 30        # VWAP computed over last N bars
    min_bars_before_signals: int = 30 # must have at least this many bars
    vwap_eps_pct: float = 0.0005      # 0.05% default eps (passed into helper via pct)
    print_prompts: bool = True


# -----------------------------
# VWAP calculation (local)
# -----------------------------
def compute_vwap_from_window(window: Deque[Bar]) -> Optional[float]:
    if not window:
        return None
    vol_sum = 0.0
    pv_sum = 0.0
    for b in window:
        v = float(b.volume) if b.volume is not None else 1.0
        p = float(b.close)
        vol_sum += v
        pv_sum += p * v
    if vol_sum <= 0:
        return None
    return pv_sum / vol_sum


# -----------------------------
# Engine loop (prompt-only)
# -----------------------------
class EngineLoop:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self._window: Deque[Bar] = deque(maxlen=max(5, cfg.vwap_window_bars))
        self._prompts: List[Dict[str, Any]] = []

        # RegimeGate is optional; if present, instantiate defensively
        self._regime = None
        if RegimeGate is not None:
            try:
                self._regime = RegimeGate()
            except Exception:
                self._regime = None

    @property
    def prompts(self) -> List[Dict[str, Any]]:
        return self._prompts

    def _regime_allows(self) -> bool:
        """
        If RegimeGate exists and exposes an allow/decision method, use it.
        Otherwise, allow by default.
        """
        if self._regime is None:
            return True

        # Try common method names without assuming your exact API
        for method_name in ("allow", "is_allowed", "decision", "evaluate", "check"):
            fn = getattr(self._regime, method_name, None)
            if callable(fn):
                try:
                    out = fn()
                    # Normalize common patterns
                    if isinstance(out, bool):
                        return out
                    if isinstance(out, dict) and "allow" in out:
                        return bool(out["allow"])
                    if hasattr(out, "allow"):
                        return bool(getattr(out, "allow"))
                    # If decision object has .result or .status
                    if hasattr(out, "result"):
                        return str(getattr(out, "result")).upper() == "ALLOW"
                    if hasattr(out, "status"):
                        return str(getattr(out, "status")).upper() == "ALLOW"
                except Exception:
                    # If regime gate fails, stay safe: block signals
                    return False

        # Unknown interface → default safe behavior: allow signals (prompt-only)
        return True

    def on_bar(self, bar: Bar) -> Optional[Dict[str, Any]]:
        """
        Process one bar. Returns the generated prompt dict (if any).
        """
        if bar.symbol != self.cfg.symbol:
            return None

        self._window.append(bar)

        # Minimum bars
        if len(self._window) < self.cfg.min_bars_before_signals:
            return None

        # Regime gate
        if not self._regime_allows():
            return None

        vwap = compute_vwap_from_window(self._window)
        if vwap is None:
            return None

        # Build a prompt-only VWAP mean reversion signal
        prompt = build_vwap_prompt_default_eps(
            price=float(bar.close),
            vwap=float(vwap),
            extra={
                "symbol": bar.symbol,
                "as_of_utc": bar.ts_utc.isoformat(),
                "vwap_window_bars": self.cfg.vwap_window_bars,
            },
            pct=self.cfg.vwap_eps_pct,
        )

        # Store/print prompt (no execution)
        if isinstance(prompt, dict):
            self._prompts.append(prompt)
            if self.cfg.print_prompts:
                print(prompt)

        return prompt


# -----------------------------
# CSV demo runner (optional)
# -----------------------------
def load_bars_from_csv(filepath: str, symbol: str) -> List[Bar]:
    """
    Reads a simple 1m CSV if available.
    Tries common column names:
      - timestamp / datetime / time
      - close
      - volume
    """
    bars: List[Bar] = []
    with open(filepath, "r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # timestamp
            ts_raw = (
                row.get("timestamp")
                or row.get("datetime")
                or row.get("time")
                or row.get("date")
                or ""
            ).strip()

            # parse timestamp best-effort
            ts = None
            if ts_raw:
                # Try ISO first
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    # Try common formats
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S"):
                        try:
                            ts = datetime.strptime(ts_raw, fmt).replace(tzinfo=timezone.utc)
                            break
                        except Exception:
                            continue
            if ts is None:
                # fallback: "now" in UTC (not ideal, but keeps demo running)
                ts = datetime.now(timezone.utc)

            close_raw = (row.get("close") or row.get("Close") or row.get("c") or "").strip()
            vol_raw = (row.get("volume") or row.get("Volume") or row.get("v") or "").strip()

            try:
                close = float(close_raw)
            except Exception:
                continue

            try:
                volume = float(vol_raw) if vol_raw else 1.0
            except Exception:
                volume = 1.0

            bars.append(Bar(ts_utc=ts, symbol=symbol, close=close, volume=volume))
    return bars


def main() -> None:
    cfg = EngineConfig()

    # If you have sample CSVs in repo root, this will run out-of-the-box.
    # Otherwise, it will just start and do nothing.
    repo_root = os.getcwd()
    candidates = [
        os.path.join(repo_root, "sample_spy_1m.csv"),
        os.path.join(repo_root, "sample_spy_1m_long.csv"),
    ]
    csv_path = next((p for p in candidates if os.path.exists(p)), None)

    loop = EngineLoop(cfg)

    if csv_path:
        bars = load_bars_from_csv(csv_path, cfg.symbol)
        for b in bars:
            loop.on_bar(b)

        print(f"\nDone. Prompts generated: {len(loop.prompts)}")
    else:
        print("No sample CSV found. Place sample_spy_1m.csv in repo root to run demo.")
        print("EngineLoop is ready. Call EngineLoop(cfg).on_bar(bar) from your replay pipeline.")


if __name__ == "__main__":
    main()
