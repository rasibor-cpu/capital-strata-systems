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

    @staticmethod
    def _safe_label(value: Any, *, fallback: str) -> str:
        text = str(value or "").strip()
        lowered = text.lower()
        if not text or lowered in {"unknown", "none", "null", "n/a", "na"}:
            return fallback
        return text

    @staticmethod
    def _recommendation(
        *,
        total: int,
        expectancy: float,
        profit_factor: float,
        recent_avg: float,
        baseline_avg: float,
    ) -> str:
        if total < MIN_STRATEGY_SAMPLE_SIZE:
            return "WATCH"
        if expectancy > 0.0 and profit_factor >= 1.20 and recent_avg >= baseline_avg:
            return "PROMOTE"
        if expectancy < 0.0 or profit_factor < 0.80:
            return "DEMOTE"
        if abs(expectancy) <= 0.01 and abs(recent_avg - baseline_avg) <= 0.01:
            return "NEUTRAL"
        return "WATCH"

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
        avg_duration = sum(float(t.holding_seconds or 0.0) for t in trades) / total if total > 0 else 0.0

        if gross_loss > 0:
            pf = gross_prof / gross_loss
        else:
            pf = float("inf") if gross_prof > 0 else 0.0

        expectancy = avg_pnl
        rolling_window = max(3, min(10, total))
        recent_trades = trades[-rolling_window:]
        recent_avg = sum(float(t.realized_pnl or 0.0) for t in recent_trades) / len(recent_trades)
        baseline_avg = avg_pnl
        if total > rolling_window:
            prior_trades = trades[:-rolling_window]
            if prior_trades:
                baseline_avg = sum(float(t.realized_pnl or 0.0) for t in prior_trades) / len(prior_trades)

        if recent_avg > baseline_avg + 0.01:
            confidence_trend = "UP"
        elif recent_avg < baseline_avg - 0.01:
            confidence_trend = "DOWN"
        else:
            confidence_trend = "FLAT"

        absolute_total = sum(abs(float(t.realized_pnl or 0.0)) for t in trades)
        drawdown_contribution = 0.0
        if absolute_total > 0:
            drawdown_contribution = gross_loss / absolute_total

        recommendation = self._recommendation(
            total=total,
            expectancy=expectancy,
            profit_factor=(pf if pf != float("inf") else 99.0),
            recent_avg=recent_avg,
            baseline_avg=baseline_avg,
        )

        legacy_rank = {
            "PROMOTE": "PROMOTE_CANDIDATE",
            "DEMOTE": "DEMOTE_CANDIDATE",
            "WATCH": "WATCHLIST",
            "NEUTRAL": "WATCHLIST",
        }[recommendation]

        return {
            "trades": total,
            "trade_count": total,
            "wins": wins,
            "winning_trades": wins,
            "losses": losses,
            "losing_trades": losses,
            "win_rate": round(w_rate, 4),
            "net_realized_pnl": round(net_pnl, 4),
            "expectancy": round(expectancy, 6),
            "average_pnl": round(avg_pnl, 4),
            "average_return": round(avg_pnl, 6),
            "average_duration": round(avg_duration, 4),
            "average_win": round(avg_win, 4),
            "average_loss": round(avg_loss, 4),
            "rolling_performance": {
                "window": rolling_window,
                "recent_average_return": round(recent_avg, 6),
                "baseline_average_return": round(baseline_avg, 6),
            },
            "confidence_trend": confidence_trend,
            "drawdown_contribution": round(drawdown_contribution, 6),
            "profit_factor": round(pf, 4) if pf != float("inf") else "inf",
            "lifecycle_recommendation": recommendation,
            "rank": legacy_rank,
        }

    def _group_by_key(self, key_func, *, fallback: str) -> Dict[str, Any]:
        try:
            trades = self.ledger.list_trades()
            groups = {}
            for t in trades:
                key = self._safe_label(key_func(t), fallback=fallback)
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
        return self._group_by_key(lambda t: t.entry_reason, fallback="ENTRY_REASON_UNSPECIFIED")

    def rank_by_asset_class(self) -> Dict[str, Any]:
        return self._group_by_key(lambda t: t.asset_class, fallback="ASSET_CLASS_UNSPECIFIED")

    def rank_by_symbol(self) -> Dict[str, Any]:
        return self._group_by_key(lambda t: t.symbol, fallback="SYMBOL_UNSPECIFIED")

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

        print("\n=== STRATEGY INTELLIGENCE ===")

        def print_section(title: str, groups: Dict[str, Any]):
            print(f"\n{title}:")
            if not groups:
                print("  * None")
                return

            sorted_groups = sorted(
                groups.items(),
                key=lambda x: float(x[1].get("net_realized_pnl", 0.0) or 0.0),
                reverse=True,
            )

            for group_name, stats in sorted_groups[:5]:
                print(f"  * {group_name} [{stats.get('lifecycle_recommendation', 'WATCH')}]")
                print(f"      Trades:    {stats.get('trades', 0)}")
                print(f"      Wins/Loss: {stats.get('wins', 0)} / {stats.get('losses', 0)}")
                print(f"      Win Rate:  {stats.get('win_rate', 0) * 100:.2f}%")
                print(f"      Net PnL:   {stats.get('net_realized_pnl', 0):+.4f}")
                print(f"      Expectancy:{stats.get('expectancy', 0):+.4f}")
                print(f"      Profit F:  {stats.get('profit_factor', 0)}")
                print(f"      Avg Hold:  {stats.get('average_duration', 0):.2f}s")
                rolling = stats.get("rolling_performance", {})
                print(
                    "      Perf Trend:"
                    f" {stats.get('confidence_trend', 'FLAT')}"
                    f" ({rolling.get('recent_average_return', 0):+.4f} vs {rolling.get('baseline_average_return', 0):+.4f})"
                )

        print_section("Entry Reason Rankings", rankings.get("by_entry_reason", {}))
        print_section("Asset Class Rankings", rankings.get("by_asset_class", {}))
        print_section("Symbol Rankings", rankings.get("by_symbol", {}))

        merged_rows = []
        for label, stats in rankings.get("by_entry_reason", {}).items():
            row = dict(stats)
            row["label"] = label
            merged_rows.append(row)

        merged_rows.sort(key=lambda row: float(row.get("net_realized_pnl", 0.0) or 0.0), reverse=True)

        print("\nTop Performing Strategies:")
        if merged_rows:
            for row in merged_rows[:3]:
                print(f"  * {row.get('label')} ({row.get('lifecycle_recommendation', 'WATCH')}) {row.get('net_realized_pnl', 0):+.4f}")
        else:
            print("  * None")

        print("\nWeakest Strategies:")
        if merged_rows:
            weakest = sorted(merged_rows, key=lambda row: float(row.get("net_realized_pnl", 0.0) or 0.0))[:3]
            for row in weakest:
                print(f"  * {row.get('label')} ({row.get('lifecycle_recommendation', 'WATCH')}) {row.get('net_realized_pnl', 0):+.4f}")
        else:
            print("  * None")

    except Exception as e:
        print(f"[STRATEGY RANKING WARN] {e}")
