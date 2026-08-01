"""DIP-005 Capital Intelligence analytics."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from backend.intelligence.enterprise_intelligence.models import CapitalIntelligenceReport, EvidenceReference
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.schema import TradeDNARecord


class CapitalIntelligenceEngine:
    """Historical capital analytics over Trade DNA and derived metrics only."""

    def __init__(
        self,
        *,
        dna_records: Sequence[TradeDNARecord],
        derived_metrics: Sequence[DerivedTradeMetrics],
        generated_at: str,
        period_days: int = 30,
    ) -> None:
        self.generated_at = generated_at
        self.period_days = int(period_days)
        self._derived_by_dna = {metric.dna_id: metric for metric in derived_metrics}
        self._rows: list[tuple[TradeDNARecord, DerivedTradeMetrics]] = []
        for record in dna_records:
            if str(record.outcome.status or "").lower() != "closed":
                continue
            metric = self._derived_by_dna.get(record.identity.dna_id)
            if metric is None:
                continue
            self._rows.append((record, metric))
        self._rows.sort(key=lambda row: (row[0].timing.closed_at or "", row[0].identity.trade_id))

    def build_report(self) -> CapitalIntelligenceReport:
        profits = [float(metric.profit or 0.0) for _record, metric in self._rows]
        notionals = [self._notional(record) for record, _metric in self._rows]
        deployed = sum(notionals)
        realized_profit = sum(profits)
        positive_profit = sum(value for value in profits if value > 0.0)
        losses = [value for value in profits if value < 0.0]
        max_drawdown = _max_drawdown(profits)
        drawdown_recovery = _drawdown_recovery(profits)
        exposure = self._exposure_history()
        concentration = max((row["exposure_share"] for row in exposure), default=0.0)
        run_rate = self._run_rate(realized_profit)
        metrics = {
            "trade_count": len(self._rows),
            "capital_deployment": round(deployed, 10),
            "capital_utilization": round(deployed / max(deployed, 1.0), 10) if self._rows else 0.0,
            "capital_efficiency": round(realized_profit / deployed, 10) if deployed else 0.0,
            "realized_profitability": round(realized_profit, 10),
            "drawdown_utilization": round(max_drawdown / deployed, 10) if deployed else 0.0,
            "drawdown_recovery": round(drawdown_recovery, 10),
            "exposure_concentration": round(concentration, 10),
            "risk_adjusted_performance": round(realized_profit / max(max_drawdown, abs(sum(losses)), 1.0), 10),
            "profit_retention": round(realized_profit / positive_profit, 10) if positive_profit else 0.0,
            "cumulative_banked_profits": round(positive_profit, 10),
            "historical_run_rate_per_day": round(run_rate["per_day"], 10),
            "historical_run_rate_per_period": round(run_rate["per_period"], 10),
            "average_return": round(statistics.fmean([float(m.return_pct or 0.0) for _r, m in self._rows]), 10) if self._rows else 0.0,
            "median_return": round(statistics.median([float(m.return_pct or 0.0) for _r, m in self._rows]), 10) if self._rows else 0.0,
        }
        return CapitalIntelligenceReport(
            generated_at=self.generated_at,
            period_days=self.period_days,
            metrics=metrics,
            trends=tuple(self._trends()),
            exposure_history=tuple(exposure),
            evidence=self._evidence(),
        ).with_hash()

    def _evidence(self) -> EvidenceReference:
        return EvidenceReference(
            trade_ids=tuple(sorted(record.identity.trade_id for record, _metric in self._rows)),
            dna_ids=tuple(sorted(record.identity.dna_id for record, _metric in self._rows)),
            calculations=(
                "capital_deployment",
                "capital_utilization",
                "capital_efficiency",
                "realized_profitability",
                "drawdown_utilization",
                "drawdown_recovery",
                "exposure_history",
                "exposure_concentration",
                "risk_adjusted_performance",
                "profit_retention",
                "cumulative_banked_profits",
                "historical_run_rate",
            ),
        )

    def _notional(self, record: TradeDNARecord) -> float:
        value = record.execution.scaled_notional or record.execution.requested_notional or 0.0
        return abs(float(value))

    def _exposure_history(self) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"notional": 0.0, "trade_ids": []})
        for record, _metric in self._rows:
            symbol = record.identity.instrument or record.market.symbol or "UNAVAILABLE"
            buckets[str(symbol)]["notional"] += self._notional(record)
            buckets[str(symbol)]["trade_ids"].append(record.identity.trade_id)
        total = sum(bucket["notional"] for bucket in buckets.values())
        rows = []
        for symbol in sorted(buckets):
            bucket = buckets[symbol]
            rows.append(
                {
                    "symbol": symbol,
                    "notional": round(bucket["notional"], 10),
                    "exposure_share": round(bucket["notional"] / total, 10) if total else 0.0,
                    "trade_ids": sorted(bucket["trade_ids"]),
                }
            )
        rows.sort(key=lambda row: (-row["notional"], row["symbol"]))
        return rows

    def _trends(self) -> list[dict[str, Any]]:
        if not self._rows:
            return []
        closed_dates = [_parse_dt(record.timing.closed_at) for record, _metric in self._rows if record.timing.closed_at]
        closed_dates = [date for date in closed_dates if date is not None]
        if not closed_dates:
            return []
        end = max(closed_dates)
        start = end - timedelta(days=self.period_days)
        buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"profit": 0.0, "notional": 0.0, "trade_ids": []})
        for record, metric in self._rows:
            closed = _parse_dt(record.timing.closed_at)
            if closed is None or closed < start:
                continue
            key = closed.date().isoformat()
            buckets[key]["profit"] += float(metric.profit or 0.0)
            buckets[key]["notional"] += self._notional(record)
            buckets[key]["trade_ids"].append(record.identity.trade_id)
        return [
            {
                "period": key,
                "profit": round(bucket["profit"], 10),
                "notional": round(bucket["notional"], 10),
                "capital_efficiency": round(bucket["profit"] / bucket["notional"], 10) if bucket["notional"] else 0.0,
                "trade_ids": sorted(bucket["trade_ids"]),
            }
            for key, bucket in sorted(buckets.items())
        ]

    def _run_rate(self, realized_profit: float) -> dict[str, float]:
        dates = [_parse_dt(record.timing.closed_at) for record, _metric in self._rows if record.timing.closed_at]
        dates = [date for date in dates if date is not None]
        if not dates:
            return {"per_day": 0.0, "per_period": 0.0}
        span_days = max(1.0, (max(dates) - min(dates)).total_seconds() / 86400.0 + 1.0)
        per_day = realized_profit / span_days
        return {"per_day": per_day, "per_period": per_day * self.period_days}


def _max_drawdown(profits: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for profit in profits:
        equity += float(profit)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return abs(max_dd)


def _drawdown_recovery(profits: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    trough_at_max_dd = 0.0
    final_equity = 0.0
    for profit in profits:
        equity += float(profit)
        final_equity = equity
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_dd:
            max_dd = drawdown
            trough_at_max_dd = equity
    if max_dd <= 0:
        return 1.0 if profits else 0.0
    return max(0.0, min(1.0, (final_equity - trough_at_max_dd) / max_dd))


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
