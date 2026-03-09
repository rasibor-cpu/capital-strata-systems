from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.opportunity_router import OpportunityRouter


class SignalEngine:
    """
    CSS Signal Engine

    Converts routed opportunities into trade signals.
    """

    def __init__(self) -> None:
        self.router = OpportunityRouter()

    def generate_signal(self, opportunity: Dict[str, Any]) -> str:
        score = float(opportunity["score"])
        regime = str(opportunity["regime"]).upper()

        if regime == "TREND" and score > 0.4:
            return "BUY"

        if regime == "BREAKOUT" and score > 0.4:
            return "BUY"

        if regime == "MEAN_REVERSION" and score > 0.3:
            return "SELL"

        return "HOLD"

    def run(self) -> List[Dict[str, Any]]:
        routes = self.router.route()
        signals: List[Dict[str, Any]] = []

        for r in routes:
            signal = self.generate_signal(r)

            signals.append(
                {
                    "symbol": r["symbol"],
                    "asset_class": r["asset_class"],
                    "score": r["score"],
                    "regime": r["regime"],
                    "confidence": r["confidence"],
                    "strategy": r["strategy"],
                    "trend_pct": r["trend_pct"],
                    "volatility_pct": r["volatility_pct"],
                    "spread_pct": r["spread_pct"],
                    "signal": signal,
                }
            )

        return signals


def print_signals(signals: List[Dict[str, Any]]) -> None:
    print("\n=== CSS SIGNAL ENGINE ===\n")

    for s in signals:
        print(
            f"{s['symbol']} | {s['asset_class']} | "
            f"regime={s['regime']} | "
            f"strategy={s['strategy']} | "
            f"signal={s['signal']}"
        )


if __name__ == "__main__":
    engine = SignalEngine()
    signals = engine.run()
    print_signals(signals)