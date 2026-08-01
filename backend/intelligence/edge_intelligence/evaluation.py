"""DIP-004 deterministic edge evaluation."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from backend.intelligence.edge_intelligence.models import (
    EdgeCandidate,
    EdgeEvaluation,
    EdgeExplanation,
    LIFECYCLE_DECAYING,
    LIFECYCLE_DISCOVERED,
    LIFECYCLE_DRIFTING,
    LIFECYCLE_EVIDENCE_THRESHOLD_MET,
    LIFECYCLE_STABLE,
    LIFECYCLE_UNDER_OBSERVATION,
    canonical_hash,
)
from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION, FIELD_UNAVAILABLE
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.schema import TradeDNARecord


@dataclass(frozen=True)
class EvidenceThresholdPolicy:
    observational_min_trades: int = 20
    supported_min_trades: int = 50
    observational_min_independent: int = 10
    supported_min_independent: int = 30
    min_data_completeness: float = 0.80
    supported_data_completeness: float = 0.95
    observational_min_confidence: float = 0.40
    supported_min_confidence: float = 0.65
    max_supported_outlier_impact: float = 0.30


class EdgeEvaluator:
    """Evaluate edge candidates using historical DNA and derived metrics only."""

    def __init__(
        self,
        *,
        dna_records: Sequence[TradeDNARecord],
        derived_metrics: Sequence[DerivedTradeMetrics],
        threshold_policy: EvidenceThresholdPolicy | None = None,
        analysis_version: str = ANALYSIS_VERSION,
        evidence_version: str = EVIDENCE_VERSION,
    ) -> None:
        self.threshold_policy = threshold_policy or EvidenceThresholdPolicy()
        self.analysis_version = analysis_version
        self.evidence_version = evidence_version
        self._records_by_trade = {record.identity.trade_id: record for record in dna_records}
        self._derived_by_dna = {metric.dna_id: metric for metric in derived_metrics}
        self._pairs: dict[str, tuple[TradeDNARecord, DerivedTradeMetrics]] = {}
        for record in sorted(dna_records, key=lambda r: (r.identity.trade_id, r.identity.dna_id)):
            if str(record.outcome.status or "").lower() != "closed":
                continue
            derived = self._derived_by_dna.get(record.identity.dna_id)
            if derived is not None:
                self._pairs[record.identity.trade_id] = (record, derived)

    def evaluate(self, candidate: EdgeCandidate) -> EdgeEvaluation:
        pairs = [
            self._pairs[trade_id]
            for trade_id in sorted(candidate.trade_ids)
            if trade_id in self._pairs
        ]
        profits = [float(metric.profit or 0.0) for _record, metric in pairs]
        returns = [self._return_value(record, metric) for record, metric in pairs]
        holdings = [float(metric.holding_period_seconds or 0.0) for _record, metric in pairs]
        sample_size = len(pairs)
        wins = [value for value in profits if value > 0.0]
        losses = [value for value in profits if value < 0.0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
        expectancy = statistics.fmean(profits) if profits else 0.0
        average_return = statistics.fmean(returns) if returns else 0.0
        median_return = statistics.median(returns) if returns else 0.0
        maximum_drawdown = _max_drawdown(profits)
        independent = _independent_observations(pairs)
        confidence_breakdown = self._confidence_components(pairs, profits, returns, expectancy)
        confidence_score = _weighted_confidence(confidence_breakdown)
        confidence_label = _confidence_label(confidence_score)
        threshold = self._threshold_status(
            sample_size=sample_size,
            independent_observations=independent,
            confidence_score=confidence_score,
            completeness=confidence_breakdown["data_completeness"],
            outlier_resistance=confidence_breakdown["outlier_resistance"],
        )
        stability_score, stability_label, stability_breakdown = self._stability(pairs, profits)
        persistence_score = stability_breakdown["same_sign_window_fraction"]
        drift_score, drift_state, drift_breakdown = self._drift(pairs, profits)
        lifecycle = _lifecycle_from(
            threshold=threshold,
            stability_label=stability_label,
            drift_state=drift_state,
        )
        limitations = _limitations(threshold, confidence_breakdown, stability_label, drift_state)
        counter_evidence = _counter_evidence(pairs)
        metric_drivers = _metric_drivers(
            sample_size=sample_size,
            expectancy=expectancy,
            profit_factor=profit_factor,
            win_rate=(len(wins) / sample_size if sample_size else 0.0),
            maximum_drawdown=maximum_drawdown,
            confidence_score=confidence_score,
            stability_score=stability_score,
        )
        threshold_results = {
            "policy": self.threshold_policy.__dict__,
            "status": threshold,
            "sample_size": sample_size,
            "independent_observations": independent,
            "data_completeness": confidence_breakdown["data_completeness"],
            "outlier_resistance": confidence_breakdown["outlier_resistance"],
            "confidence_score": confidence_score,
        }
        explanation = EdgeExplanation(
            summary=f"{candidate.name} is classified as {threshold} with {confidence_label} confidence.",
            why_detected=f"Historical Trade DNA matched cohort {candidate.cohort_key}.",
            metric_drivers=tuple(metric_drivers),
            confidence_breakdown=confidence_breakdown,
            stability_breakdown=stability_breakdown,
            drift_breakdown=drift_breakdown,
            threshold_results=threshold_results,
            supporting_trade_ids=tuple(sorted(candidate.trade_ids)),
            supporting_dna_ids=tuple(sorted(candidate.dna_ids)),
            counter_evidence=tuple(counter_evidence),
            limitations=tuple(limitations),
        )
        metrics_payload = {
            "definition_hash": candidate.definition_hash,
            "trade_references": tuple(sorted(candidate.trade_ids)),
            "evidence_references": tuple(sorted(candidate.dna_ids)),
            "sample_size": sample_size,
            "independent_observations": independent,
            "win_rate": round(len(wins) / sample_size, 10) if sample_size else 0.0,
            "loss_rate": round(len(losses) / sample_size, 10) if sample_size else 0.0,
            "profit_factor": round(profit_factor, 10),
            "expectancy": round(expectancy, 10),
            "median_return": round(median_return, 10),
            "average_return": round(average_return, 10),
            "maximum_drawdown": round(maximum_drawdown, 10),
            "average_holding_seconds": round(statistics.fmean(holdings), 10) if holdings else 0.0,
            "median_holding_seconds": round(statistics.median(holdings), 10) if holdings else 0.0,
            "confidence_score": confidence_score,
            "stability_score": stability_score,
            "persistence_score": persistence_score,
            "drift_score": drift_score,
            "drift_state": drift_state,
            "analysis_version": self.analysis_version,
            "evidence_version": self.evidence_version,
        }
        edge_fingerprint = canonical_hash(metrics_payload)
        return EdgeEvaluation(
            sample_size=sample_size,
            independent_observations=independent,
            win_rate=metrics_payload["win_rate"],
            loss_rate=metrics_payload["loss_rate"],
            profit_factor=metrics_payload["profit_factor"],
            expectancy=metrics_payload["expectancy"],
            median_return=metrics_payload["median_return"],
            average_return=metrics_payload["average_return"],
            maximum_drawdown=metrics_payload["maximum_drawdown"],
            average_holding_seconds=metrics_payload["average_holding_seconds"],
            median_holding_seconds=metrics_payload["median_holding_seconds"],
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            stability_score=stability_score,
            stability_label=stability_label,
            persistence_score=persistence_score,
            drift_score=drift_score,
            drift_state=drift_state,
            evidence_threshold=threshold,
            lifecycle_state=lifecycle,
            metrics_hash=edge_fingerprint,
            edge_fingerprint=edge_fingerprint,
            analysis_version=self.analysis_version,
            evidence_version=self.evidence_version,
            explanation=explanation,
        )

    def _threshold_status(
        self,
        *,
        sample_size: int,
        independent_observations: int,
        confidence_score: float,
        completeness: float,
        outlier_resistance: float,
    ) -> str:
        policy = self.threshold_policy
        outlier_impact = 1.0 - outlier_resistance
        if (
            sample_size >= policy.supported_min_trades
            and independent_observations >= policy.supported_min_independent
            and confidence_score >= policy.supported_min_confidence
            and completeness >= policy.supported_data_completeness
            and outlier_impact <= policy.max_supported_outlier_impact
        ):
            return "SUPPORTED"
        if (
            sample_size >= policy.observational_min_trades
            and independent_observations >= policy.observational_min_independent
            and confidence_score >= policy.observational_min_confidence
            and completeness >= policy.min_data_completeness
        ):
            return "OBSERVATIONAL_ONLY"
        return "BELOW_THRESHOLD"

    def _confidence_components(
        self,
        pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
        profits: Sequence[float],
        returns: Sequence[float],
        expectancy: float,
    ) -> dict[str, float]:
        sample_size = len(pairs)
        independent = _independent_observations(pairs)
        consistency = _same_sign_fraction(profits)
        if len(returns) > 1 and abs(expectancy) > 0:
            dispersion = statistics.pstdev(returns)
            variance_score = 1.0 / (1.0 + abs(dispersion / expectancy))
        elif returns:
            variance_score = 1.0
        else:
            variance_score = 0.0
        total_abs = sum(abs(value) for value in profits)
        top_abs = max((abs(value) for value in profits), default=0.0)
        outlier_resistance = 1.0 - (top_abs / total_abs if total_abs else 1.0)
        completeness = _data_completeness(pairs)
        diversity = _diversity_score(pairs)
        recency = _recency_score(pairs, profits)
        return {
            "sample_size": round(min(1.0, sample_size / max(1, self.threshold_policy.supported_min_trades)), 6),
            "independent_observations": round(min(1.0, independent / max(1, self.threshold_policy.supported_min_independent)), 6),
            "consistency": round(consistency, 6),
            "variance": round(max(0.0, min(1.0, variance_score)), 6),
            "outlier_resistance": round(max(0.0, min(1.0, outlier_resistance)), 6),
            "recency": round(recency, 6),
            "data_completeness": round(completeness, 6),
            "diversity": round(diversity, 6),
        }

    def _stability(
        self,
        pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
        profits: Sequence[float],
    ) -> tuple[float, str, dict[str, Any]]:
        windows = _chronological_windows(pairs, profits)
        window_expectancies = [statistics.fmean(window) for window in windows if window]
        same_sign_fraction = _positive_fraction(window_expectancies)
        if len(window_expectancies) < 2:
            label = "INSUFFICIENT_HISTORY"
            score = 0.0
        else:
            variance_penalty = 0.0
            if len(window_expectancies) > 1:
                mean_abs = abs(statistics.fmean(window_expectancies)) or 1.0
                variance_penalty = min(1.0, statistics.pstdev(window_expectancies) / mean_abs)
            score = max(0.0, min(1.0, (same_sign_fraction * 0.7) + ((1.0 - variance_penalty) * 0.3)))
            if score >= 0.70:
                label = "STABLE"
            elif score >= 0.40:
                label = "MIXED"
            else:
                label = "UNSTABLE"
        return (
            round(score, 6),
            label,
            {
                "window_count": len(window_expectancies),
                "window_expectancies": [round(value, 10) for value in window_expectancies],
                "same_sign_window_fraction": round(same_sign_fraction, 6),
            },
        )

    def _drift(
        self,
        pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
        profits: Sequence[float],
    ) -> tuple[float, str, dict[str, Any]]:
        if len(profits) < 4:
            return 0.0, "INSUFFICIENT_RECENT_EVIDENCE", {"reason": "sample_size_lt_4"}
        ordered = _ordered_profit_series(pairs, profits)
        mid = len(ordered) // 2
        first = [value for _key, value in ordered[:mid]]
        second = [value for _key, value in ordered[mid:]]
        first_exp = statistics.fmean(first) if first else 0.0
        second_exp = statistics.fmean(second) if second else 0.0
        delta = second_exp - first_exp
        scale = max(abs(first_exp), abs(second_exp), 1.0)
        score = max(-1.0, min(1.0, delta / scale))
        if score <= -0.50:
            state = "DECAYING"
        elif score <= -0.20:
            state = "DEGRADING"
        elif abs(score) >= 0.50:
            state = "REGIME_SHIFT"
        else:
            state = "NO_DRIFT"
        return (
            round(score, 6),
            state,
            {
                "first_window_expectancy": round(first_exp, 10),
                "recent_window_expectancy": round(second_exp, 10),
                "expectancy_delta": round(delta, 10),
            },
        )

    def _return_value(self, record: TradeDNARecord, metric: DerivedTradeMetrics) -> float:
        if metric.return_pct is not None:
            return float(metric.return_pct)
        notional = record.execution.scaled_notional or record.execution.requested_notional or 0.0
        if notional:
            return float(metric.profit or 0.0) / abs(float(notional))
        return float(metric.profit or 0.0)


def _max_drawdown(profits: Sequence[float]) -> float:
    peak = 0.0
    equity = 0.0
    drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
    return abs(drawdown)


def _independent_observations(pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]]) -> int:
    buckets = set()
    for record, _metric in pairs:
        opened = _date_bucket(record.timing.opened_at)
        strategy = record.strategy.strategy_id or FIELD_UNAVAILABLE
        symbol = record.identity.instrument or record.market.symbol or FIELD_UNAVAILABLE
        buckets.add((opened, strategy, symbol))
    return len(buckets)


def _date_bucket(value: str | None) -> str:
    if not value:
        return FIELD_UNAVAILABLE
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return FIELD_UNAVAILABLE


def _hour_bucket(value: str | None) -> str:
    if not value:
        return FIELD_UNAVAILABLE
    try:
        return f"{datetime.fromisoformat(value.replace('Z', '+00:00')).hour:02d}:00"
    except Exception:
        return FIELD_UNAVAILABLE


def _same_sign_fraction(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    positive = sum(1 for value in values if value > 0)
    negative = sum(1 for value in values if value < 0)
    return max(positive, negative) / len(values)


def _positive_fraction(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value > 0) / len(values)


def _data_completeness(pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]]) -> float:
    if not pairs:
        return 0.0
    checks = 0
    present = 0
    for record, metric in pairs:
        values = (
            record.identity.trade_id,
            record.identity.dna_id,
            record.identity.instrument or record.market.symbol,
            record.strategy.strategy_id,
            record.market.market_regime,
            record.timing.opened_at,
            record.timing.closed_at,
            record.outcome.win_loss,
            metric.profit,
            metric.holding_period_seconds,
        )
        for value in values:
            checks += 1
            if value not in (None, "", FIELD_UNAVAILABLE):
                present += 1
    return present / checks if checks else 0.0


def _diversity_score(pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]]) -> float:
    if not pairs:
        return 0.0
    symbols = {r.identity.instrument or r.market.symbol or FIELD_UNAVAILABLE for r, _m in pairs}
    regimes = {r.market.market_regime or FIELD_UNAVAILABLE for r, _m in pairs}
    hours = {_hour_bucket(r.timing.opened_at) for r, _m in pairs}
    holding = {_holding_bucket(m.holding_period_seconds) for _r, m in pairs}
    scores = [
        min(1.0, len(symbols) / 2.0),
        min(1.0, len(regimes) / 2.0),
        min(1.0, len(hours) / 3.0),
        min(1.0, len(holding) / 3.0),
    ]
    return statistics.fmean(scores)


def _holding_bucket(seconds: float | None) -> str:
    if seconds is None:
        return FIELD_UNAVAILABLE
    value = float(seconds)
    if value < 3600:
        return "<1h"
    if value < 14400:
        return "1h-4h"
    if value < 86400:
        return "4h-1d"
    return ">=1d"


def _recency_score(
    pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
    profits: Sequence[float],
) -> float:
    if not pairs:
        return 0.0
    ordered = _ordered_profit_series(pairs, profits)
    recent = [value for _key, value in ordered[max(0, len(ordered) - max(1, len(ordered) // 3)):]]
    if not recent:
        return 0.0
    return 1.0 if statistics.fmean(recent) > 0 else 0.5 if statistics.fmean(recent) == 0 else 0.0


def _chronological_windows(
    pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
    profits: Sequence[float],
) -> list[list[float]]:
    ordered = [value for _key, value in _ordered_profit_series(pairs, profits)]
    if len(ordered) < 2:
        return [ordered] if ordered else []
    window_count = min(4, len(ordered))
    windows: list[list[float]] = [[] for _ in range(window_count)]
    for index, value in enumerate(ordered):
        bucket = min(window_count - 1, int(index * window_count / len(ordered)))
        windows[bucket].append(value)
    return windows


def _ordered_profit_series(
    pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
    profits: Sequence[float],
) -> list[tuple[str, float]]:
    rows = []
    for (record, _metric), profit in zip(pairs, profits):
        rows.append((record.timing.opened_at or record.identity.trade_id, float(profit)))
    return sorted(rows, key=lambda row: row[0])


def _weighted_confidence(parts: Mapping[str, float]) -> float:
    weights = {
        "sample_size": 0.20,
        "independent_observations": 0.15,
        "consistency": 0.20,
        "variance": 0.15,
        "outlier_resistance": 0.10,
        "recency": 0.10,
        "data_completeness": 0.05,
        "diversity": 0.05,
    }
    return round(sum(float(parts[key]) * weight for key, weight in weights.items()), 6)


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "VERY_HIGH"
    if score >= 0.65:
        return "HIGH"
    if score >= 0.40:
        return "MEDIUM"
    return "LOW"


def _lifecycle_from(*, threshold: str, stability_label: str, drift_state: str) -> str:
    if drift_state == "DECAYING":
        return LIFECYCLE_DECAYING
    if drift_state in {"DEGRADING", "REGIME_SHIFT"}:
        return LIFECYCLE_DRIFTING
    if threshold == "SUPPORTED" and stability_label == "STABLE":
        return LIFECYCLE_STABLE
    if threshold == "SUPPORTED":
        return LIFECYCLE_EVIDENCE_THRESHOLD_MET
    if threshold == "OBSERVATIONAL_ONLY":
        return LIFECYCLE_UNDER_OBSERVATION
    return LIFECYCLE_DISCOVERED


def _limitations(
    threshold: str,
    confidence_breakdown: Mapping[str, float],
    stability_label: str,
    drift_state: str,
) -> list[str]:
    notes: list[str] = []
    if threshold != "SUPPORTED":
        notes.append("edge_below_supported_threshold")
    for key, value in confidence_breakdown.items():
        if value < 0.40:
            notes.append(f"low_{key}")
    if stability_label != "STABLE":
        notes.append(f"stability_{stability_label.lower()}")
    if drift_state != "NO_DRIFT":
        notes.append(f"drift_{drift_state.lower()}")
    return sorted(set(notes))


def _counter_evidence(
    pairs: Sequence[tuple[TradeDNARecord, DerivedTradeMetrics]],
) -> list[dict[str, Any]]:
    rows = []
    for record, metric in pairs:
        profit = float(metric.profit or 0.0)
        if profit < 0:
            rows.append(
                {
                    "trade_id": record.identity.trade_id,
                    "dna_id": record.identity.dna_id,
                    "profit": profit,
                    "reason": "negative_outcome_in_population",
                }
            )
    rows.sort(key=lambda row: (row["profit"], row["trade_id"]))
    return rows[:10]


def _metric_drivers(**values: Any) -> list[dict[str, Any]]:
    rows = [{"metric": key, "value": value} for key, value in values.items()]
    rows.sort(key=lambda row: row["metric"])
    return rows
