import logging
from typing import Dict, Any, List
from analytics.trade_outcome_ledger import TradeOutcomeLedger, TradeOutcome

logger = logging.getLogger(__name__)

MIN_STRATEGY_SAMPLE_SIZE = 5

class StrategyRankingEngine:
    def __init__(self, ledger: TradeOutcomeLedger = None):
        if ledger is None:
            self.ledger = TradeOutcomeLedger()
        else:
            self.ledger = ledger

    def _calculate_metrics(self, trades: List[TradeOutcome]) -> Dict[str, Any]:
        total = len(trades)
        if total == 0:
            return {}

        wins = sum(1 for t in trades if t.realized_pnl > 0)
        losses = sum(1 for t in trades if t.realized_pnl < 0)
        net_pnl = sum(t.realized_pnl for t in trades)
        
        gross_prof = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))
        
        w_rate = wins / total if total > 0 else 0.0
        avg_pnl = net_pnl / total if total > 0 else 0.0
        avg_win = gross_prof / wins if wins > 0 else 0.0
        avg_loss = gross_loss / losses if losses > 0 else 0.0
        
        if gross_loss > 0:
            pf = gross_prof / gross_loss
        else:
            pf = float('inf') if gross_prof > 0 else 0.0

        if total < MIN_STRATEGY_SAMPLE_SIZE:
            rank = "INSUFFICIENT_SAMPLE"
        elif net_pnl > 0:
            rank = "PROMOTE_CANDIDATE"
        elif net_pnl < 0:
            rank = "DEMOTE_CANDIDATE"
        else:
            rank = "WATCHLIST"

        return {
            "trade_count": total,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": round(w_rate, 4),
            "net_realized_pnl": round(net_pnl, 4),
            "average_pnl": round(avg_pnl, 4),
            "average_win": round(avg_win, 4),
            "average_loss": round(avg_loss, 4),
            "profit_factor": round(pf, 4) if pf != float('inf') else "inf",
            "rank": rank
        }

    def _group_by_key(self, key_func) -> Dict[str, Any]:
        try:
            trades = self.ledger.list_trades()
            groups = {}
            for t in trades:
                key = key_func(t)
                if key not in groups:
                    groups[key] = []
                groups[key].append(t)
            
            results = {}
            for key, group_trades in groups.items():
                results[key] = self._calculate_metrics(group_trades)
            return results
        except Exception as e:
            logger.error(f"StrategyRankingEngine failed to group: {e}")
            return {}

    def rank_by_entry_reason(self) -> Dict[str, Any]:
        return self._group_by_key(lambda t: t.entry_reason)
        
    def rank_by_asset_class(self) -> Dict[str, Any]:
        return self._group_by_key(lambda t: t.asset_class)
        
    def rank_by_symbol(self) -> Dict[str, Any]:
        return self._group_by_key(lambda t: t.symbol)
        
    def summarize_rankings(self) -> Dict[str, Any]:
        return {
            "by_entry_reason": self.rank_by_entry_reason(),
            "by_asset_class": self.rank_by_asset_class(),
            "by_symbol": self.rank_by_symbol(),
        }

def print_strategy_ranking_dashboard() -> None:
    try:
        engine = StrategyRankingEngine()
        rankings = engine.summarize_rankings()

        print("\n=== STRATEGY RANKINGS ===")

        def print_section(title: str, groups: Dict[str, Any]):
            print(f"\n{title}:")
            if not groups:
                print("  * None")
                return
                
            # sort by net_realized_pnl descending
            sorted_groups = sorted(groups.items(), key=lambda x: x[1].get('net_realized_pnl', 0), reverse=True)
            
            # top 5 only
            for group_name, stats in sorted_groups[:5]:
                print(f"  * {group_name} [{stats.get('rank', 'UNKNOWN')}]")
                print(f"      Trades:    {stats.get('trade_count', 0)}")
                print(f"      Win Rate:  {stats.get('win_rate', 0) * 100:.2f}%")
                print(f"      Net PnL:   {stats.get('net_realized_pnl', 0):+.4f}")
                print(f"      Profit F:  {stats.get('profit_factor', 0)}")

        print_section("Entry Reason Rankings", rankings.get("by_entry_reason", {}))
        print_section("Asset Class Rankings", rankings.get("by_asset_class", {}))
        print_section("Symbol Rankings", rankings.get("by_symbol", {}))

    except Exception as e:
        print(f"[STRATEGY RANKING WARN] {e}")
