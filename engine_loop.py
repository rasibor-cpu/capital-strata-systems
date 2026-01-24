from __future__ import annotations
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
from datetime import datetime, timezone

# =============================
# REQUIRED: VWAP prompt builder
# =============================
try:
    from signals.vwap_mean_reversion import build_vwap_prompt_default_eps
except Exception as e:
    raise ImportError(
        "Missing signals.vwap_mean_reversion.build_vwap_prompt_default_eps"
    ) from e

# =============================
# OPTIONAL: Regime Gate
# =============================
try:
    from regime.gate import RegimeGate  # type: ignore
except Exception:
    RegimeGate = None  # type: ignore


# =============================
# DATA MODEL
# =============================
@dataclass
class Bar:
    ts_utc: datetime
    symbol: str
    close: float
    volume: float = 1.0


# =============================
# CONFIG
# =============================
@dataclass
class EngineConfig:
    symbol: str = "SPY"
    vwap_window_bars: int = 30
    min_bars_before_signals: int = 30
    vwap_eps_pct: float = 0.0005
    print_prompts: bool = True


# =============================
# HELPERS
# =============================
def parse_ts_utc(raw: str) -> datetime:
    raw = (raw or "").strip()

    if not raw:
        return datetime.now(timezone.utc)

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return datetime.now(timezone.utc)


def compute_vwap(window: Deque[Bar]) -> Optional[float]:
    if not window:
        return None

    pv = 0.0
    vol = 0.0

    for b in window:
        v = float(b.volume) if b.volume else 1.0
        pv += b.close * v
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
                self.regime = RegimeGate()
            except Exception:
                self.regime = None

    def regime_allows(self) -> bool:
        if not self.regime:
            return True

        for name in ("allow", "is_allowed", "decision", "evaluate", "check"):
            fn = getattr(self.regime, name, None)
            if callable(fn):
                try:
                    r = fn()
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

        if len(self.window) < self.cfg.min_bars_before_signals:
            return None

        if not self.regime_allows():
            return None

        vwap = compute_vwap(self.window)
        if vwap is None:
            return None

        prompt = build_vwap_prompt_default_eps(
            price=bar.close,
            vwap=vwap,
            pct=self.cfg.vwap_eps_pct,
            extra={
                "symbol": bar.symbol,
                "as_of_utc": bar.ts_utc.isoformat(),
                "window": self.cfg.vwap_window_bars,
            },
        )

        if isinstance(prompt, dict):
            self.prompts.append(prompt)
            if self.cfg.print_prompts:
                print(prompt)

        return prompt


# =============================
# CSV LOADER (YOUR FORMAT)
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


# =============================
# MAIN (SMOKE TEST)
# =============================
def main() -> None:
    cfg = EngineConfig()
    engine = EngineLoop(cfg)

    csv_path = os.path.join(os.getcwd(), "sample_spy_1m.csv")

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
