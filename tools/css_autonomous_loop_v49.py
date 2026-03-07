"""
CSS Autonomous Loop v53
Capital Strata Systems

What this version does:
- Scans a defined Coinbase asset universe
- Ranks assets by short momentum
- Selects the best candidate automatically
- Opens a PAPER position when entry conditions are met
- Holds winning positions while momentum remains supportive
- Exits when reversal / weakness conditions appear
- Writes state for the dashboard:
    - backend/state/spot_position.json
    - backend/state/top_assets.json
- Writes trade log:
    - audit_logs/trades.jsonl

Important:
- This is PAPER / SIMULATION logic only
- No live broker orders are sent
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Deque, Dict, List, Optional

import requests


API = "https://api.exchange.coinbase.com"

ASSETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "LINK-USD",
    "AVAX-USD",
    "MATIC-USD",
    "ATOM-USD",
    "DOT-USD",
    "LTC-USD",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

POSITION_FILE = STATE_DIR / "spot_position.json"
TOP_ASSETS_FILE = STATE_DIR / "top_assets.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

REQUEST_TIMEOUT = 4
SCAN_INTERVAL_SECONDS = 15
LOOKBACK_POINTS = 8
TOP_N = 5

STARTING_CASH_USD = 500.00
RISK_ALLOCATION_PCT = 0.20          # 20% of available cash per new position
MIN_ENTRY_SCORE = 0.0010            # 0.10% short momentum threshold
EXIT_REVERSAL_SCORE = -0.0008       # exit if score weakens below this
TRAIL_STOP_PCT = 0.012              # 1.2% trailing stop
TAKE_PROFIT_PCT = 0.050             # optional hard cap 5%


@dataclass
class Position:
    asset: str
    entry_price: float
    size_usd: float
    units: float
    opened_at: str
    highest_price: float
    last_price: float
    score_at_entry: float


class CSSAutonomousLoopV53:
    def __init__(self) -> None:
        self.price_history: Dict[str, Deque[float]] = {
            asset: deque(maxlen=LOOKBACK_POINTS) for asset in ASSETS
        }
        self.cash_usd: float = STARTING_CASH_USD
        self.position: Optional[Position] = self._load_position()
        self.realized_pnl: float = 0.0
        self.trade_count: int = 0

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)

        if self.position:
            print(f"Recovered position: {self.position.asset} @ {self.position.entry_price}")
        else:
            print("No prior open position recovered.")

    # -----------------------------
    # Persistence
    # -----------------------------
    def _load_position(self) -> Optional[Position]:
        try:
            if POSITION_FILE.exists():
                data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
                if "asset" in data and "entry_price" in data and "units" in data:
                    return Position(
                        asset=str(data["asset"]),
                        entry_price=float(data["entry_price"]),
                        size_usd=float(data["size_usd"]),
                        units=float(data["units"]),
                        opened_at=str(data["opened_at"]),
                        highest_price=float(data.get("highest_price", data["entry_price"])),
                        last_price=float(data.get("last_price", data["entry_price"])),
                        score_at_entry=float(data.get("score_at_entry", 0.0)),
                    )
        except Exception:
            pass
        return None

    def _save_position(self) -> None:
        if self.position is None:
            if POSITION_FILE.exists():
                POSITION_FILE.unlink()
            return

        payload = asdict(self.position)
        payload["timestamp"] = datetime.now(UTC).isoformat()
        POSITION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_top_assets(self, ranked: List[dict]) -> None:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "top_assets": ranked[:TOP_N],
        }
        TOP_ASSETS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_trade_log(self, record: dict) -> None:
        with TRADES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # -----------------------------
    # Market Data
    # -----------------------------
    def get_price(self, asset: str) -> Optional[float]:
        url = f"{API}/products/{asset}/ticker"
        try:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "CSS-Autonomous-Loop/53"},
            )
            response.raise_for_status()
            data = response.json()
            price = data.get("price")
            return float(price) if price is not None else None
        except Exception:
            return None

    def update_price_history(self) -> Dict[str, float]:
        latest: Dict[str, float] = {}
        for asset in ASSETS:
            price = self.get_price(asset)
            if price is not None:
                self.price_history[asset].append(price)
                latest[asset] = price
        return latest

    @staticmethod
    def compute_score(prices: Deque[float]) -> float:
        if len(prices) < 3:
            return 0.0
        first = prices[0]
        last = prices[-1]
        if first == 0:
            return 0.0
        return (last - first) / first

    def rank_assets(self) -> List[dict]:
        ranked: List[dict] = []
        for asset, prices in self.price_history.items():
            if not prices:
                continue
            score = self.compute_score(prices)
            ranked.append(
                {
                    "asset": asset,
                    "score": score,
                    "last_price": prices[-1],
                    "samples": len(prices),
                }
            )
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    # -----------------------------
    # Trading Logic
    # -----------------------------
    def should_enter(self, asset_info: dict) -> bool:
        return float(asset_info["score"]) >= MIN_ENTRY_SCORE

    def should_exit(self, price: float, score: float) -> bool:
        if self.position is None:
            return False

        entry = self.position.entry_price
        highest = max(self.position.highest_price, price)

        if price > self.position.highest_price:
            self.position.highest_price = price

        trail_level = highest * (1 - TRAIL_STOP_PCT)
        pnl_pct = (price - entry) / entry

        if score <= EXIT_REVERSAL_SCORE:
            return True

        if price <= trail_level:
            return True

        if pnl_pct >= TAKE_PROFIT_PCT and score < self.position.score_at_entry:
            return True

        return False

    def open_position(self, asset: str, price: float, score: float) -> None:
        allocation = round(self.cash_usd * RISK_ALLOCATION_PCT, 2)
        if allocation <= 0:
            return

        units = allocation / price
        now = datetime.now(UTC).isoformat()

        self.position = Position(
            asset=asset,
            entry_price=price,
            size_usd=allocation,
            units=units,
            opened_at=now,
            highest_price=price,
            last_price=price,
            score_at_entry=score,
        )
        self.cash_usd -= allocation
        self._save_position()

        self._append_trade_log(
            {
                "timestamp": now,
                "event": "BUY",
                "asset": asset,
                "price": price,
                "size_usd": allocation,
                "units": units,
                "score": score,
                "pnl": 0.0,
                "mode": "paper",
            }
        )

        print(f"BUY  {asset}  price={price:.4f}  size=${allocation:.2f}  score={score:+.6f}")

    def close_position(self, price: float, score: float, reason: str) -> None:
        if self.position is None:
            return

        now = datetime.now(UTC).isoformat()
        proceeds = self.position.units * price
        pnl = proceeds - self.position.size_usd

        self.cash_usd += proceeds
        self.realized_pnl += pnl
        self.trade_count += 1

        self._append_trade_log(
            {
                "timestamp": now,
                "event": "SELL",
                "asset": self.position.asset,
                "entry_price": self.position.entry_price,
                "exit_price": price,
                "size_usd": self.position.size_usd,
                "units": self.position.units,
                "score": score,
                "pnl": round(pnl, 6),
                "reason": reason,
                "mode": "paper",
            }
        )

        print(
            f"SELL {self.position.asset}  exit={price:.4f}  pnl=${pnl:.2f}  "
            f"reason={reason}  score={score:+.6f}"
        )

        self.position = None
        self._save_position()

    # -----------------------------
    # Reporting
    # -----------------------------
    def print_header(self) -> None:
        print("\n" + "=" * 78)
        print(" CAPITAL STRATA SYSTEMS — AUTONOMOUS LOOP v53 ".center(78))
        print("=" * 78)

    def print_rankings(self, ranked: List[dict]) -> None:
        print("\nTOP RANKED ASSETS\n")
        for i, item in enumerate(ranked[:TOP_N], start=1):
            print(
                f"{i}. {item['asset']:<9} "
                f"score={item['score']:+.6f}  "
                f"price={item['last_price']:.4f}  "
                f"samples={item['samples']}"
            )

    def print_position_status(self, ranked: List[dict]) -> None:
        print("\nPORTFOLIO\n")
        print(f"Cash USD      : ${self.cash_usd:.2f}")
        print(f"Realized PnL  : ${self.realized_pnl:.2f}")
        print(f"Closed Trades : {self.trade_count}")

        if self.position is None:
            print("Open Position : None")
            return

        current_score = 0.0
        current_price = self.position.last_price

        for item in ranked:
            if item["asset"] == self.position.asset:
                current_score = float(item["score"])
                current_price = float(item["last_price"])
                break

        unrealized = (current_price - self.position.entry_price) * self.position.units

        print(f"Open Position : {self.position.asset}")
        print(f"Entry Price   : {self.position.entry_price:.4f}")
        print(f"Current Price : {current_price:.4f}")
        print(f"Size USD      : ${self.position.size_usd:.2f}")
        print(f"Units         : {self.position.units:.8f}")
        print(f"Unrealized    : ${unrealized:.2f}")
        print(f"Score         : {current_score:+.6f}")

    # -----------------------------
    # Main Loop
    # -----------------------------
    def run_once(self) -> None:
        latest = self.update_price_history()
        ranked = self.rank_assets()
        self._save_top_assets(ranked)

        self.print_header()

        if not ranked:
            print("\nNo market data returned.")
            print(f"\nLast Update: {datetime.now(UTC).isoformat()}")
            print(f"\nRefreshing in {SCAN_INTERVAL_SECONDS} seconds...")
            return

        self.print_rankings(ranked)

        if self.position is None:
            best = ranked[0]
            best_asset = str(best["asset"])
            best_price = float(best["last_price"])
            best_score = float(best["score"])

            if self.should_enter(best):
                self.open_position(best_asset, best_price, best_score)
            else:
                print(
                    f"\nNo entry. Best asset {best_asset} score={best_score:+.6f} "
                    f"is below threshold {MIN_ENTRY_SCORE:+.6f}"
                )
        else:
            asset = self.position.asset
            if asset in latest:
                current_price = latest[asset]
                self.position.last_price = current_price
                current_score = self.compute_score(self.price_history[asset])

                if self.should_exit(current_price, current_score):
                    self.close_position(
                        price=current_price,
                        score=current_score,
                        reason="reversal_or_trailing_stop",
                    )
                else:
                    self._save_position()
                    print(
                        f"\nHOLD {asset}  price={current_price:.4f}  "
                        f"score={current_score:+.6f}  "
                        f"high={self.position.highest_price:.4f}"
                    )
            else:
                print(f"\nNo fresh price for open position asset: {asset}")

        ranked = self.rank_assets()
        self.print_position_status(ranked)

        print(f"\nLast Update: {datetime.now(UTC).isoformat()}")
        print(f"\nRefreshing in {SCAN_INTERVAL_SECONDS} seconds...")

    def run(self) -> None:
        print("Starting CSS Autonomous Loop v53 in PAPER mode...")
        while True:
            try:
                self.run_once()
                time.sleep(SCAN_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                print("\nStopped by user.")
                break
            except Exception as exc:
                print(f"\nLoop error: {exc}")
                time.sleep(SCAN_INTERVAL_SECONDS)


def main() -> None:
    engine = CSSAutonomousLoopV53()
    engine.run()


if __name__ == "__main__":
    main()