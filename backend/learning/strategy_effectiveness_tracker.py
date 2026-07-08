from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

from backend.learning.common import confidence, outcome, rows
from backend.portfolio.utils import advisory_response, safe_float


MIN_EVIDENCE = 5


class StrategyEffectivenessTracker:
    """Track advisory strategy effectiveness from historical opportunity outcomes."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None, *, min_evidence: int = MIN_EVIDENCE) -> dict[str, Any]:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows(history):
            strategy = strategy_id(row)
            if strategy:
                grouped.setdefault(strategy, []).append(row)

        if not grouped:
            return advisory_response(
                "DATA UNAVAILABLE",
                strategy_metrics={},
                strongest_strategy="DATA UNAVAILABLE",
                weakest_strategy="DATA UNAVAILABLE",
                reasons=["strategy_effectiveness_history_unavailable"],
                recommended_actions=["Collect evaluated strategy opportunity history before changing advisory weights."],
                **_safety_flags(),
            )

        metrics = {name: _metrics_for_strategy(items, min_evidence=max(1, int(min_evidence or MIN_EVIDENCE))) for name, items in grouped.items()}
        ranked = sorted(metrics.items(), key=lambda item: _ranking_score(item[1]), reverse=True)
        status = "OK" if any(item["evidence_state"] == "SUFFICIENT" for item in metrics.values()) else "PARTIAL"
        return advisory_response(
            status,
            strategy_metrics=metrics,
            strongest_strategy=ranked[0][0],
            weakest_strategy=ranked[-1][0],
            reasons=["strategy_effectiveness_metrics_computed"],
            recommended_actions=_portfolio_actions(metrics),
            **_safety_flags(),
        )


def strategy_id(row: Mapping[str, Any]) -> str:
    for key in ("strategy_id", "strategy", "strategy_name", "model", "engine"):
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    payload = row.get("opportunity")
    if isinstance(payload, Mapping):
        return strategy_id(payload)
    return ""


def accepted(row: Mapping[str, Any]) -> bool:
    for key in ("accepted", "is_accepted", "selected", "allocated", "executed"):
        if key in row:
            return bool(row.get(key))
    decision = str(row.get("decision", row.get("status", row.get("recommendation", ""))) or "").strip().upper()
    if decision in {"ACCEPT", "ACCEPTED", "APPROVED", "SELECTED", "TRADE", "EXECUTED"}:
        return True
    if decision in {"REJECT", "REJECTED", "DECLINED", "SKIPPED", "SUPPRESSED"}:
        return False
    return outcome(row) is not None


def asset_class(row: Mapping[str, Any]) -> str:
    for key in ("asset_class", "asset_type", "class"):
        value = str(row.get(key, "") or "").strip().upper()
        if value:
            return value
    return "UNKNOWN"


def holding_period(row: Mapping[str, Any]) -> float | None:
    for key in ("holding_period", "holding_period_minutes", "holding_minutes", "duration_minutes"):
        if row.get(key) is not None:
            value = safe_float(row.get(key), math.nan)
            return value if math.isfinite(value) else None
    return None


def confidence_bucket(row: Mapping[str, Any]) -> str:
    conf = confidence(row)
    if conf is None:
        return "UNKNOWN"
    if conf >= 0.8:
        return "HIGH"
    if conf >= 0.55:
        return "MEDIUM"
    return "LOW"


def _metrics_for_strategy(items: list[Mapping[str, Any]], *, min_evidence: int) -> dict[str, Any]:
    accepted_rows = [row for row in items if accepted(row)]
    rejected_rows = [row for row in items if not accepted(row)]
    returns = [float(value) for row in accepted_rows if (value := outcome(row)) is not None]
    profitable = [value for value in returns if value > 0.0]
    losing = [value for value in returns if value < 0.0]
    periods = [value for row in accepted_rows if (value := holding_period(row)) is not None]
    total = len(items)
    accepted_count = len(accepted_rows)
    evidence_state = "SUFFICIENT" if len(returns) >= min_evidence else "INSUFFICIENT"
    return {
        "total_opportunities": total,
        "accepted_opportunities": accepted_count,
        "rejected_opportunities": len(rejected_rows),
        "profitable_trades": len(profitable),
        "losing_trades": len(losing),
        "average_return": _round(_mean(returns)),
        "median_return": _round(median(returns) if returns else 0.0),
        "win_rate": _round((len(profitable) / len(returns)) * 100.0 if returns else 0.0),
        "profit_factor": _profit_factor(profitable, losing),
        "expectancy": _round(_mean(returns)),
        "sharpe": _round(_sharpe(returns)),
        "sortino": _round(_sortino(returns)),
        "maximum_drawdown": _round(_max_drawdown(returns)),
        "average_holding_period": _round(_mean(periods)),
        "evidence_state": evidence_state,
        "asset_classes": sorted({asset_class(row) for row in items}),
        "confidence_buckets": _bucket_counts(confidence_bucket(row) for row in items),
        "recommendation": recommendation_for_metrics(
            {
                "sample_size": len(returns),
                "win_rate": (len(profitable) / len(returns)) * 100.0 if returns else 0.0,
                "average_return": _mean(returns),
                "profit_factor": _profit_factor(profitable, losing),
                "sharpe": _sharpe(returns),
                "maximum_drawdown": _max_drawdown(returns),
                "evidence_state": evidence_state,
            }
        ),
    }


def recommendation_for_metrics(metrics: Mapping[str, Any]) -> str:
    if str(metrics.get("evidence_state", "")).upper() != "SUFFICIENT":
        return "Needs additional evidence"
    win_rate = safe_float(metrics.get("win_rate"))
    avg_return = safe_float(metrics.get("average_return"))
    profit_factor = safe_float(metrics.get("profit_factor"))
    sharpe = safe_float(metrics.get("sharpe"))
    max_drawdown = safe_float(metrics.get("maximum_drawdown"))
    if avg_return > 0.0 and win_rate >= 60.0 and profit_factor >= 1.5 and sharpe > 0.5:
        return "Increase confidence weighting"
    if avg_return < 0.0 and (win_rate < 45.0 or profit_factor < 0.8):
        return "Temporarily suppress" if max_drawdown < -5.0 else "Reduce confidence weighting"
    if (avg_return > 0.0 and win_rate < 50.0) or (avg_return < 0.0 and win_rate >= 55.0):
        return "Increase monitoring"
    return "No advisory weighting change"


def _portfolio_actions(metrics: Mapping[str, Mapping[str, Any]]) -> list[str]:
    actions = sorted({str(payload.get("recommendation", "No advisory weighting change")) for payload in metrics.values()})
    actions.append("Do not apply adaptive recommendations to execution authority.")
    return actions


def _ranking_score(metrics: Mapping[str, Any]) -> float:
    evidence_penalty = 0.5 if metrics.get("evidence_state") == "INSUFFICIENT" else 1.0
    return evidence_penalty * (
        safe_float(metrics.get("average_return")) * 3.0
        + safe_float(metrics.get("win_rate")) * 0.05
        + safe_float(metrics.get("profit_factor")) * 0.5
        + safe_float(metrics.get("sharpe")) * 0.25
        + safe_float(metrics.get("maximum_drawdown")) * 0.1
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _profit_factor(profitable: list[float], losing: list[float]) -> float:
    gross_profit = sum(profitable)
    gross_loss = abs(sum(losing))
    if gross_loss == 0.0:
        return _round(999.0 if gross_profit > 0.0 else 0.0)
    return _round(gross_profit / gross_loss)


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    deviation = math.sqrt(variance)
    return 0.0 if deviation == 0.0 else (avg / deviation) * math.sqrt(len(values))


def _sortino(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    downside = [min(0.0, value) for value in values]
    downside_variance = sum(value**2 for value in downside) / len(values)
    downside_deviation = math.sqrt(downside_variance)
    return 0.0 if downside_deviation == 0.0 else (_mean(values) / downside_deviation) * math.sqrt(len(values))


def _max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    return max_drawdown


def _bucket_counts(values: Iterable[str]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for value in values:
        buckets[value] = buckets.get(value, 0) + 1
    return buckets


def _round(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(value, 6)


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
    }
