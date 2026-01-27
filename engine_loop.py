"""
engine_loop.py — REA Capital Trading Engine (Prompt-Only)

Integrates Module 3 VWAP mean-reversion prompt generation via:
    signals.vwap_mean_reversion.build_vwap_prompt_default_eps

HARD CONSTRAINTS:
- NO trade execution
- NO auto-risk escalation
- Prompt / diagnostics only
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Deque
from collections import deque
import csv
import os

# Optional imports (project may include these)
try:
    from regime.gate import RegimeGate  # type: ignore
except Exception:
    RegimeGate = None  # graceful fallback

try:
    from signals.vwap_mean_reversion import build_vwap_prompt_default_eps  # type: ignore
except Exception:
    build_vwap_prompt_default_eps = None  # graceful fallback


# =============================
# DATA MODEL
# =============================
@dataclass
class EngineConfig:
    symbol: str = "SPY"
    vwap_window_bars: int = 5
    min_bars_before_signals: int = 5
    vwap_eps_pct: float = 0.0001
    print_prompts: bool = True


@dataclass
class Bar:
    ts_utc: Any
    symbol: str
    close: float
    volume: float = 1.0


# =============================
# HELPERS
# =============================
def parse_ts_utc(v: Optional[str]):
    """
    Minimal timestamp parser.
    Accepts ISO strings; if parsing fails, returns raw.
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        # Python ISO handling (works with "+00:00")
        from datetime import datetime

        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return s


def compute_vwap(window: Deque[Bar]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for b in window:
        v = float(b.volume) if b.volume else 0.0
        pv += float(b.close) * v
        vol += v
    return pv / vol if vol > 0 else None


# =============================
# ENGINE LOOP (PROMPT ONLY)
# =============================
class EngineLoop:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.window: Deque[Bar] = deque(maxlen=cfg.vwap_window_bars)
        self.prompts: List[Dict[str, Any]] = []

        self.regime = None
        if RegimeGate:
            try:
                self.regime = RegimeGate()  # may exist in your project
            except Exception:
                self.regime = None

    def regime_allows(self) -> bool:
        """
        Regime gating. Conservative by default.
        If RegimeGate exists and returns a boolean/allow field, use it.
        Otherwise default allow = True.
        """
        if not self.regime:
            return True

        # Common call patterns
        for meth in ("allow", "allows", "evaluate", "check", "on_bar"):
            if hasattr(self.regime, meth):
                try:
                    r = getattr(self.regime, meth)()
                    if isinstance(r, bool):
                        return r
                    if isinstance(r, dict) and "allow" in r:
                        return bool(r["allow"])
                except Exception:
                    return False

        return True

    def on_bar(self, bar: Bar) -> Optional[Dict[str, Any]]:
        if bar.symbol != self.cfg.symbol:
            return None

        self.window.append(bar)

        # --- Diagnostics helper (read-only) ---
        def _diag(*, reason: str, regime_state: str = "UNKNOWN", vwap: Optional[float] = None) -> None:
            print("=" * 60)
            try:
                ts_str = bar.ts_utc.isoformat()
            except Exception:
                ts_str = str(bar.ts_utc)

            print(f"Timestamp (UTC): {ts_str}")
            print("\n[DATA READINESS]")
            print(f"5m Bars: {len(self.window)} / {self.cfg.min_bars_before_signals}")
            print("Status: READY" if len(self.window) >= self.cfg.min_bars_before_signals else "Status: NOT READY")

            print("\n[SESSION]")
            print("Session Name: N/A")
            print("Session Open: True")

            print("\n[REGIME GATE]")
            print(f"Regime State: {regime_state}")

            print("\n[VWAP]")
            print(f"VWAP Deviation: N/A")
            print(f"VWAP Threshold: {self.cfg.vwap_eps_pct:.4f}")

            print("\n[DECISION]")
            print("Outcome: NO SIGNAL")
            print(f"Reason: {reason}")
            print("=" * 60)

        # Readiness
        if len(self.window) < self.cfg.min_bars_before_signals:
            _diag(reason="Insufficient bars for signals", regime_state="BLOCK")
            return None

        # Regime gate
        if not self.regime_allows():
            _diag(reason="Regime gate blocked signals", regime_state="BLOCK")
            return None

        # VWAP compute
        vwap = compute_vwap(self.window)
        if vwap is None or build_vwap_prompt_default_eps is None:
            _diag(reason="VWAP unavailable or prompt builder missing", regime_state="ALLOW", vwap=vwap)
            return None

        # At this point: engine is READY + regime allows + VWAP computed
        _diag(reason="Conditions met; prompt evaluation proceeds", regime_state="ALLOW", vwap=vwap)

        prompt = build_vwap_prompt_default_eps(
            price=bar.close,
            vwap=vwap,
            pct=self.cfg.vwap_eps_pct,
            extra={
                "symbol": bar.symbol,
                "as_of_utc": bar.ts_utc.isoformat() if hasattr(bar.ts_utc, "isoformat") else str(bar.ts_utc),
                "window": self.cfg.vwap_window_bars,
            },
        )

        if isinstance(prompt, dict):
            # Store the raw prompt
            self.prompts.append(prompt)

            # ✅ Step-2 change: expose prompt fields in a consistent way for wrappers/loggers.
            # This is PROMPT-ONLY metadata; it does NOT trigger execution.
            payload = prompt.get("payload", {})
            prompt.setdefault("prompt_payload", payload)
            prompt.setdefault("prompt_text", f"{prompt.get('signal', 'SIGNAL')}: {payload}")
            prompt.setdefault("prompt", prompt["prompt_text"])

            if self.cfg.print_prompts:
                print(prompt)

        return prompt


# =============================
# CSV LOADER (YOUR EXISTING FORMAT)
# =============================
def load_bars_from_csv(path: str, symbol: str) -> List[Bar]:
    bars: List[Bar] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts = parse_ts_utc(row.get("ts_utc") or row.get("timestamp"))
            close = row.get("c") or row.get("close")
            volume = row.get("v") or row.get("volume")

            try:
                bars.append(
                    Bar(
                        ts_utc=ts,
                        symbol=symbol,
                        close=float(close),
                        volume=float(volume) if volume else 1.0,
                    )
                )
            except Exception:
                continue

    return bars


def main():
    cfg = EngineConfig(symbol="SPY", print_prompts=True)
    engine = EngineLoop(cfg)

    csv_path = "sample_spy_1m.csv"
    if not os.path.exists(csv_path):
        print("No sample_spy_1m.csv found.")
        print("Engine ready. Use EngineLoop(cfg).on_bar(bar)")
        return

    bars = load_bars_from_csv(csv_path, cfg.symbol)

    for b in bars:
        engine.on_bar(b)

    print(f"\nDone. Prompts generated: {len(engine.prompts)}")


if __name__ == "__main__":
    main()