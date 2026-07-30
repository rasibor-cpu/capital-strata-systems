"""DIP-003 WP-3 — Decision Analytics Foundation (read-only, evidence-backed)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION, FIELD_UNAVAILABLE
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.evidence_graph import EvidenceGraphNode, build_evidence_graph
from backend.intelligence.trade_dna.schema import TradeDNARecord


def _confidence(sample_size: int) -> float:
    if sample_size <= 0:
        return 0.0
    return round(min(1.0, sample_size / 30.0), 6)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


@dataclass(frozen=True)
class AnalyticalConclusion:
    """Read-only analytical output. No recommendations / capital / execution."""

    kind: str
    title: str
    rows: tuple[dict[str, Any], ...]
    evidence: EvidenceGraphNode
    analysis_version: str = ANALYSIS_VERSION
    recommendations: bool = False
    capital_allocation: bool = False
    execution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rows"] = list(self.rows)
        payload["evidence"] = self.evidence.to_dict()
        return payload


@dataclass
class DecisionAnalyticsEngine:
    """Analytics over stored Trade DNA + derived metrics only (no live market)."""

    dna_records: Sequence[TradeDNARecord]
    derived_metrics: Sequence[DerivedTradeMetrics]
    generated_at: str
    min_sample: int = 1

    def __post_init__(self) -> None:
        self._derived_by_dna = {m.dna_id: m for m in self.derived_metrics}
        self._closed: list[tuple[TradeDNARecord, DerivedTradeMetrics]] = []
        for record in self.dna_records:
            if str(record.outcome.status or "").lower() != "closed":
                continue
            derived = self._derived_by_dna.get(record.identity.dna_id)
            if derived is None or derived.profit is None:
                continue
            self._closed.append((record, derived))
        # Stable order for determinism
        self._closed.sort(key=lambda pair: pair[0].identity.trade_id)

    def _evidence_for(self, trade_ids: Iterable[str], *, notes: str) -> EvidenceGraphNode:
        ids = tuple(sorted({str(t) for t in trade_ids if str(t).strip()}))
        dna_ids = tuple(
            sorted(
                {
                    r.identity.dna_id
                    for r, _ in self._closed
                    if r.identity.trade_id in ids
                }
            )
        )
        return build_evidence_graph(
            trade_ids=ids,
            dna_ids=dna_ids,
            evidence_version=EVIDENCE_VERSION,
            analysis_version=ANALYSIS_VERSION,
            sample_size=len(ids),
            confidence=_confidence(len(ids)),
            generated_at=self.generated_at,
            notes=notes,
        )

    def _conclusion(
        self,
        *,
        kind: str,
        title: str,
        rows: list[dict[str, Any]],
        trade_ids: Sequence[str],
    ) -> AnalyticalConclusion:
        return AnalyticalConclusion(
            kind=kind,
            title=title,
            rows=tuple(rows),
            evidence=self._evidence_for(trade_ids, notes=kind),
        )

    def top_profit_contributors(self, *, limit: int = 10) -> AnalyticalConclusion:
        ranked = sorted(self._closed, key=lambda p: float(p[1].profit or 0.0), reverse=True)
        rows = []
        trade_ids: list[str] = []
        for record, derived in ranked[:limit]:
            if float(derived.profit or 0.0) <= 0:
                continue
            trade_ids.append(record.identity.trade_id)
            rows.append(
                {
                    "trade_id": record.identity.trade_id,
                    "dna_id": record.identity.dna_id,
                    "strategy_id": record.strategy.strategy_id,
                    "symbol": record.identity.instrument or record.market.symbol,
                    "profit": derived.profit,
                }
            )
        return self._conclusion(
            kind="top_profit_contributors",
            title="Top profit contributors",
            rows=rows,
            trade_ids=trade_ids,
        )

    def largest_loss_contributors(self, *, limit: int = 10) -> AnalyticalConclusion:
        ranked = sorted(self._closed, key=lambda p: float(p[1].profit or 0.0))
        rows = []
        trade_ids: list[str] = []
        for record, derived in ranked[:limit]:
            if float(derived.profit or 0.0) >= 0:
                continue
            trade_ids.append(record.identity.trade_id)
            rows.append(
                {
                    "trade_id": record.identity.trade_id,
                    "dna_id": record.identity.dna_id,
                    "strategy_id": record.strategy.strategy_id,
                    "symbol": record.identity.instrument or record.market.symbol,
                    "profit": derived.profit,
                }
            )
        return self._conclusion(
            kind="largest_loss_contributors",
            title="Largest loss contributors",
            rows=rows,
            trade_ids=trade_ids,
        )

    def strategy_profitability(self) -> AnalyticalConclusion:
        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"profit": 0.0, "trade_count": 0, "trade_ids": []}
        )
        for record, derived in self._closed:
            key = record.strategy.strategy_id or FIELD_UNAVAILABLE
            buckets[key]["profit"] += float(derived.profit or 0.0)
            buckets[key]["trade_count"] += 1
            buckets[key]["trade_ids"].append(record.identity.trade_id)
        rows = []
        all_ids: list[str] = []
        for strategy_id in sorted(buckets):
            bucket = buckets[strategy_id]
            if bucket["trade_count"] < self.min_sample:
                continue
            all_ids.extend(bucket["trade_ids"])
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "profit": round(bucket["profit"], 10),
                    "trade_count": bucket["trade_count"],
                    "avg_profit": round(bucket["profit"] / bucket["trade_count"], 10),
                }
            )
        rows.sort(key=lambda r: r["profit"], reverse=True)
        return self._conclusion(
            kind="strategy_profitability",
            title="Strategy profitability",
            rows=rows,
            trade_ids=all_ids,
        )

    def _cohort(
        self,
        *,
        kind: str,
        title: str,
        key_fn,
    ) -> AnalyticalConclusion:
        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"profit": 0.0, "trade_count": 0, "trade_ids": []}
        )
        for record, derived in self._closed:
            key = key_fn(record, derived)
            if key is None:
                continue
            buckets[str(key)]["profit"] += float(derived.profit or 0.0)
            buckets[str(key)]["trade_count"] += 1
            buckets[str(key)]["trade_ids"].append(record.identity.trade_id)
        rows = []
        all_ids: list[str] = []
        for key in sorted(buckets):
            bucket = buckets[key]
            if bucket["trade_count"] < self.min_sample:
                continue
            all_ids.extend(bucket["trade_ids"])
            rows.append(
                {
                    "cohort": key,
                    "profit": round(bucket["profit"], 10),
                    "trade_count": bucket["trade_count"],
                    "avg_profit": round(bucket["profit"] / bucket["trade_count"], 10),
                }
            )
        rows.sort(key=lambda r: r["avg_profit"], reverse=True)
        return self._conclusion(kind=kind, title=title, rows=rows, trade_ids=all_ids)

    def entry_cohorts(self) -> AnalyticalConclusion:
        return self._cohort(
            kind="entry_cohorts",
            title="Entry cohorts",
            key_fn=lambda r, _d: (r.identity.side or FIELD_UNAVAILABLE).upper(),
        )

    def exit_cohorts(self) -> AnalyticalConclusion:
        return self._cohort(
            kind="exit_cohorts",
            title="Exit cohorts",
            key_fn=lambda r, _d: r.outcome.exit_reason or FIELD_UNAVAILABLE,
        )

    def holding_period_analysis(self) -> AnalyticalConclusion:
        def bucket_holding(_r, d: DerivedTradeMetrics) -> Optional[str]:
            seconds = d.holding_period_seconds
            if seconds is None:
                return None
            if seconds < 3600:
                return "<1h"
            if seconds < 14400:
                return "1h-4h"
            if seconds < 86400:
                return "4h-1d"
            return ">=1d"

        return self._cohort(
            kind="holding_period_analysis",
            title="Holding-period analysis",
            key_fn=bucket_holding,
        )

    def market_regime_analysis(self) -> AnalyticalConclusion:
        return self._cohort(
            kind="market_regime_analysis",
            title="Market-regime analysis",
            key_fn=lambda r, _d: r.market.market_regime or FIELD_UNAVAILABLE,
        )

    def time_of_day_analysis(self) -> AnalyticalConclusion:
        def tod(record: TradeDNARecord, _d: DerivedTradeMetrics) -> Optional[str]:
            dt = _parse_dt(record.timing.opened_at)
            if dt is None:
                return None
            return f"{dt.hour:02d}:00"

        return self._cohort(
            kind="time_of_day_analysis",
            title="Time-of-day analysis",
            key_fn=tod,
        )

    def day_of_week_analysis(self) -> AnalyticalConclusion:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        def dow(record: TradeDNARecord, _d: DerivedTradeMetrics) -> Optional[str]:
            dt = _parse_dt(record.timing.opened_at)
            if dt is None:
                return None
            return names[dt.weekday()]

        return self._cohort(
            kind="day_of_week_analysis",
            title="Day-of-week analysis",
            key_fn=dow,
        )

    def full_report(self) -> dict[str, Any]:
        sections = [
            self.top_profit_contributors(),
            self.largest_loss_contributors(),
            self.strategy_profitability(),
            self.entry_cohorts(),
            self.exit_cohorts(),
            self.holding_period_analysis(),
            self.market_regime_analysis(),
            self.time_of_day_analysis(),
            self.day_of_week_analysis(),
        ]
        return {
            "analysis_version": ANALYSIS_VERSION,
            "evidence_version": EVIDENCE_VERSION,
            "generated_at": self.generated_at,
            "recommendations": False,
            "capital_allocation": False,
            "execution_allowed": False,
            "sections": [s.to_dict() for s in sections],
        }
