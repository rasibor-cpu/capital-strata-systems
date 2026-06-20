import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class TradeOutcome:
    trade_id: str
    asset_class: str
    symbol: str
    entry_timestamp: str
    exit_timestamp: str
    holding_seconds: float
    entry_reason: str
    exit_reason: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    win_loss: str


class TradeOutcomeLedger:
    def __init__(self, file_path: Optional[Path] = None):
        if file_path is None:
            # Resolve relative to project root
            # Assume this file is in analytics/, so root is parent.parent
            root_dir = Path(__file__).resolve().parent.parent
            self.file_path = root_dir / "artifacts" / "trade_outcomes.json"
        else:
            self.file_path = Path(file_path)

        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.file_path.exists():
                self.file_path.write_text("[]", encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to ensure trade outcome ledger file exists: {e}")

    def append_trade(self, outcome: TradeOutcome) -> None:
        try:
            trades = self.list_trades()
            trades.append(outcome)
            
            data = [asdict(t) for t in trades]
            self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to append trade to ledger: {e}")

    def list_trades(self) -> List[TradeOutcome]:
        try:
            if not self.file_path.exists():
                return []
                
            content = self.file_path.read_text(encoding="utf-8").strip()
            if not content:
                return []
                
            data = json.loads(content)
            if not isinstance(data, list):
                logger.error("Trade ledger file does not contain a JSON array. Starting empty.")
                return []
                
            trades = []
            for item in data:
                try:
                    trades.append(TradeOutcome(**item))
                except TypeError as e:
                    logger.warning(f"Skipping malformed trade record: {e}")
            return trades
            
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt trade ledger JSON: {e}. Returning empty list.")
            return []
        except Exception as e:
            logger.error(f"Failed to read trade ledger: {e}. Returning empty list.")
            return []

    def summarize(self) -> Dict[str, Any]:
        trades = self.list_trades()
        
        def compute_stats(trade_subset):
            total = len(trade_subset)
            wins = sum(1 for t in trade_subset if t.realized_pnl > 0)
            losses = sum(1 for t in trade_subset if t.realized_pnl < 0)
            net_pnl = sum(t.realized_pnl for t in trade_subset)
            gross_prof = sum(t.realized_pnl for t in trade_subset if t.realized_pnl > 0)
            gross_loss = abs(sum(t.realized_pnl for t in trade_subset if t.realized_pnl < 0))
            
            w_rate = wins / total if total > 0 else 0.0
            avg_win = gross_prof / wins if wins > 0 else 0.0
            avg_loss = gross_loss / losses if losses > 0 else 0.0
            
            if gross_loss > 0:
                pf = gross_prof / gross_loss
            else:
                pf = float('inf') if gross_prof > 0 else 0.0
                
            return {
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate": round(w_rate, 4),
                "net_realized_pnl": round(net_pnl, 4),
                "average_win": round(avg_win, 4),
                "average_loss": round(avg_loss, 4),
                "profit_factor": round(pf, 4) if pf != float('inf') else "inf",
            }

        overall_stats = compute_stats(trades)
        
        # By Asset Class
        asset_classes = ["FX", "CRYPTO", "FUTURES", "OPTIONS"]
        by_asset_class = {}
        for ac in asset_classes:
            subset = [t for t in trades if t.asset_class == ac]
            by_asset_class[ac] = compute_stats(subset)
            
        # Top 5 Winning/Losing Symbols
        symbol_pnl = {}
        for t in trades:
            symbol_pnl[t.symbol] = symbol_pnl.get(t.symbol, 0.0) + t.realized_pnl
            
        sorted_symbols = sorted(symbol_pnl.items(), key=lambda x: x[1])
        top_losing = [{"symbol": k, "pnl": round(v, 4)} for k, v in sorted_symbols[:5] if v < 0]
        top_winning = [{"symbol": k, "pnl": round(v, 4)} for k, v in reversed(sorted_symbols) if v > 0][:5]

        return {
            "overall": overall_stats,
            "by_asset_class": by_asset_class,
            "top_winning_symbols": top_winning,
            "top_losing_symbols": top_losing
        }


def print_profitability_dashboard() -> None:
    try:
        ledger = TradeOutcomeLedger()
        summary = ledger.summarize()
        overall = summary.get("overall", {})
        by_asset = summary.get("by_asset_class", {})
        top_winning = summary.get("top_winning_symbols", [])
        top_losing = summary.get("top_losing_symbols", [])

        print("\n=== PROFITABILITY ANALYTICS ===")
        print("Overall:")
        print(f"  * Total Trades:   {overall.get('total_trades', 0)}")
        print(f"  * Winning Trades: {overall.get('winning_trades', 0)}")
        print(f"  * Losing Trades:  {overall.get('losing_trades', 0)}")
        print(f"  * Win Rate %:     {overall.get('win_rate', 0) * 100:.2f}%")
        print(f"  * Net Realized PnL: {overall.get('net_realized_pnl', 0):+.4f}")
        print(f"  * Average Win:    {overall.get('average_win', 0):.4f}")
        print(f"  * Average Loss:   {overall.get('average_loss', 0):.4f}")
        print(f"  * Profit Factor:  {overall.get('profit_factor', 0)}")

        print("\nBy Asset Class:")
        for ac in ["FX", "CRYPTO", "FUTURES", "OPTIONS"]:
            ac_stat = by_asset.get(ac, {})
            print(f"  * {ac}:")
            print(f"      Trades:   {ac_stat.get('total_trades', 0)}")
            print(f"      Win Rate: {ac_stat.get('win_rate', 0) * 100:.2f}%")
            print(f"      Net PnL:  {ac_stat.get('net_realized_pnl', 0):+.4f}")

        print("\nTop 5 Winning Symbols:")
        if top_winning:
            for item in top_winning:
                print(f"  * {item['symbol']}: {item['pnl']:+.4f}")
        else:
            print("  * None")

        print("\nTop 5 Losing Symbols:")
        if top_losing:
            for item in top_losing:
                print(f"  * {item['symbol']}: {item['pnl']:+.4f}")
        else:
            print("  * None")
            
    except Exception as analytics_exc:
        print(f"[PROFITABILITY ANALYTICS WARN] {analytics_exc}")

