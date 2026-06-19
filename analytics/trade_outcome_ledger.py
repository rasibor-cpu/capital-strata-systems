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
        
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.realized_pnl > 0)
        losing_trades = sum(1 for t in trades if t.realized_pnl < 0)
        
        net_realized_pnl = sum(t.realized_pnl for t in trades)
        
        gross_profit = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        average_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        average_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf') if gross_profit > 0 else 0.0
            
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 4),
            "net_realized_pnl": round(net_realized_pnl, 4),
            "average_win": round(average_win, 4),
            "average_loss": round(average_loss, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float('inf') else "inf",
        }
