"""DIP-004 deterministic edge discovery."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Sequence

from backend.intelligence.edge_intelligence.models import EdgeCandidate, EdgeDefinition
from backend.intelligence.trade_dna.constants import FIELD_UNAVAILABLE
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.schema import TradeDNARecord


class EdgeDiscoveryEngine:
    """Discover observational candidate edges from historical DNA only."""

    def __init__(
        self,
        *,
        dna_records: Sequence[TradeDNARecord],
        derived_metrics: Sequence[DerivedTradeMetrics],
    ) -> None:
        self._derived_by_dna = {metric.dna_id: metric for metric in derived_metrics}
        self._pairs: list[tuple[TradeDNARecord, DerivedTradeMetrics]] = []
        for record in sorted(dna_records, key=lambda r: (r.identity.trade_id, r.identity.dna_id)):
            if str(record.outcome.status or "").lower() != "closed":
                continue
            derived = self._derived_by_dna.get(record.identity.dna_id)
            if derived is not None:
                self._pairs.append((record, derived))

    def discover(self) -> tuple[EdgeCandidate, ...]:
        candidates: list[EdgeCandidate] = []
        candidates.extend(self._bucket("strategy", "Strategy", lambda r, _m: r.strategy.strategy_id))
        candidates.extend(self._bucket("regime", "Regime", lambda r, _m: r.market.market_regime))
        candidates.extend(self._bucket("signal", "Signal", lambda r, _m: r.strategy.signal_id))
        candidates.extend(self._bucket("holding_period", "Holding Period", lambda _r, m: _holding_bucket(m.holding_period_seconds)))
        candidates.extend(self._bucket("volatility", "Volatility", lambda r, _m: r.volatility.vol_regime))
        candidates.extend(self._bucket("session", "Session", lambda r, _m: r.market.session))
        candidates.extend(self._bucket("weekday", "Weekday", lambda r, _m: _weekday(r.timing.opened_at)))
        candidates.extend(self._bucket("entry_quality", "Entry Quality", lambda r, _m: _entry_quality(r.strategy.confluence_score)))
        candidates.extend(self._bucket("exit_quality", "Exit Quality", lambda r, _m: r.outcome.exit_reason))
        candidates.extend(self._bucket("risk_reward", "Risk/Reward", lambda r, _m: _risk_reward_bucket(r)))
        candidates.extend(self._bucket("return_distribution", "Return Distribution", lambda _r, m: _return_bucket(m.return_pct, m.profit)))
        by_signature = {candidate.signature: candidate for candidate in candidates}
        return tuple(by_signature[key] for key in sorted(by_signature))

    def _bucket(
        self,
        category: str,
        title: str,
        key_fn: Callable[[TradeDNARecord, DerivedTradeMetrics], Any],
    ) -> list[EdgeCandidate]:
        buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"trade_ids": [], "dna_ids": []})
        for record, metric in self._pairs:
            raw = key_fn(record, metric)
            key = _clean_key(raw)
            if key == FIELD_UNAVAILABLE:
                continue
            buckets[key]["trade_ids"].append(record.identity.trade_id)
            buckets[key]["dna_ids"].append(record.identity.dna_id)
        candidates = []
        for key in sorted(buckets):
            bucket = buckets[key]
            candidates.append(
                EdgeCandidate(
                    definition=EdgeDefinition(
                        category=category,
                        name=f"{title}: {key}",
                        description=f"Historical {title.lower()} edge candidate for {key}.",
                        cohort_key=key,
                        cohort_definition={"category": category, "value": key},
                        normalized_predicates={
                            "source": "trade_dna",
                            "field_family": category,
                            "operator": "equals",
                            "value": key,
                        },
                    ),
                    trade_ids=tuple(sorted(bucket["trade_ids"])),
                    dna_ids=tuple(sorted(bucket["dna_ids"])),
                )
            )
        return candidates


def _clean_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.upper() in {"UNKNOWN", "UNAVAILABLE", "NONE", "NULL"}:
        return FIELD_UNAVAILABLE
    return text.upper()


def _holding_bucket(seconds: float | None) -> str:
    if seconds is None:
        return FIELD_UNAVAILABLE
    value = float(seconds)
    if value < 3600:
        return "<1H"
    if value < 14400:
        return "1H-4H"
    if value < 86400:
        return "4H-1D"
    return ">=1D"


def _weekday(value: str | None) -> str:
    if not value:
        return FIELD_UNAVAILABLE
    try:
        names = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
        return names[datetime.fromisoformat(value.replace("Z", "+00:00")).weekday()]
    except Exception:
        return FIELD_UNAVAILABLE


def _entry_quality(score: float | None) -> str:
    if score is None:
        return FIELD_UNAVAILABLE
    value = float(score)
    if value >= 0.75:
        return "HIGH_CONFLUENCE"
    if value >= 0.45:
        return "MEDIUM_CONFLUENCE"
    return "LOW_CONFLUENCE"


def _risk_reward_bucket(record: TradeDNARecord) -> str:
    stop = record.risk.stop_distance
    entry = record.execution.entry_price
    exit_ = record.execution.exit_price
    if not stop or not entry or not exit_:
        return FIELD_UNAVAILABLE
    realized_move = abs(float(exit_) - float(entry))
    ratio = realized_move / abs(float(stop)) if stop else 0.0
    if ratio >= 2.0:
        return "RR>=2"
    if ratio >= 1.0:
        return "RR1-2"
    return "RR<1"


def _return_bucket(return_pct: float | None, profit: float | None) -> str:
    value = float(return_pct if return_pct is not None else profit if profit is not None else 0.0)
    if value > 0:
        return "POSITIVE_RETURN"
    if value < 0:
        return "NEGATIVE_RETURN"
    return "FLAT_RETURN"
