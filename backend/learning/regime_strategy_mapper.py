from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import regime, rows
from backend.learning.strategy_effectiveness_tracker import (
    accepted,
    asset_class,
    confidence_bucket,
    outcome,
    recommendation_for_metrics,
    strategy_id,
)
from backend.portfolio.utils import advisory_response, safe_float


REGIME_ALIASES = {
    "TREND": "TRENDING",
    "TRENDING_UP": "TRENDING",
    "TRENDING_DOWN": "TRENDING",
    "MOMENTUM": "TRENDING",
    "RANGE": "RANGING",
    "RANGE_BOUND": "RANGING",
    "RANGING": "RANGING",
    "VOLATILE": "HIGH_VOLATILITY",
    "HIGH_VOL": "HIGH_VOLATILITY",
    "HIGH_VOLATILITY": "HIGH_VOLATILITY",
    "LOW_VOL": "LOW_VOLATILITY",
    "LOW_VOLATILITY": "LOW_VOLATILITY",
    "RISK_OFF": "RISK_OFF",
    "DEFENSIVE": "RISK_OFF",
    "RISK_ON": "RISK_ON",
    "GROWTH": "RISK_ON",
}

TRACKED_REGIMES = ("TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "RISK_OFF", "RISK_ON")


class RegimeStrategyMapper:
    """Map advisory strategy performance across market regimes and asset classes."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None, *, min_evidence: int = 3) -> dict[str, Any]:
        grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
        for row in rows(history):
            strategy = strategy_id(row)
            if not strategy:
                continue
            grouped.setdefault(normalize_regime(regime(row)), {}).setdefault(strategy, []).append(row)

        if not grouped:
            return advisory_response(
                "DATA UNAVAILABLE",
                regime_strategy_map={},
                strongest_pairs=[],
                weakest_pairs=[],
                reasons=["regime_strategy_history_unavailable"],
                recommended_actions=["Collect regime-labelled strategy outcomes before changing advisory emphasis."],
                **_safety_flags(),
            )

        regime_map: dict[str, dict[str, Any]] = {}
        pairs: list[dict[str, Any]] = []
        safe_min = max(1, int(min_evidence or 3))
        for regime_name, strategies in grouped.items():
            strategy_payload: dict[str, Any] = {}
            for name, items in strategies.items():
                returns = [float(value) for row in items if accepted(row) and (value := outcome(row)) is not None]
                wins = [value for value in returns if value > 0.0]
                losses = [value for value in returns if value < 0.0]
                win_rate = (len(wins) / len(returns)) * 100.0 if returns else 0.0
                gross_loss = abs(sum(losses))
                profit_factor = 999.0 if gross_loss == 0.0 and wins else (sum(wins) / gross_loss if gross_loss else 0.0)
                avg_return = sum(returns) / len(returns) if returns else 0.0
                evidence_state = "SUFFICIENT" if len(returns) >= safe_min else "INSUFFICIENT"
                metrics = {
                    "sample_size": len(returns),
                    "average_return": round(avg_return, 6),
                    "win_rate": round(win_rate, 6),
                    "profit_factor": round(profit_factor, 6),
                    "asset_classes": sorted({asset_class(row) for row in items}),
                    "confidence_buckets": _bucket_counts(confidence_bucket(row) for row in items),
                    "evidence_state": evidence_state,
                    "recommendation": recommendation_for_metrics(
                        {
                            "sample_size": len(returns),
                            "average_return": avg_return,
                            "win_rate": win_rate,
                            "profit_factor": profit_factor,
                            "sharpe": avg_return,
                            "maximum_drawdown": min(0.0, sum(returns)),
                            "evidence_state": evidence_state,
                        }
                    ),
                }
                strategy_payload[name] = metrics
                pairs.append(
                    {
                        "regime": regime_name,
                        "strategy": name,
                        "score": _score(metrics),
                        "recommendation": metrics["recommendation"],
                        "sample_size": metrics["sample_size"],
                    }
                )
            regime_map[regime_name] = {
                "strategies": strategy_payload,
                "strategy_count": len(strategy_payload),
                "tracked_regime": regime_name in TRACKED_REGIMES,
            }

        strongest = sorted(pairs, key=lambda item: item["score"], reverse=True)[:3]
        weakest = sorted(pairs, key=lambda item: item["score"])[:3]
        return advisory_response(
            "OK" if any(item["sample_size"] >= safe_min for item in pairs) else "PARTIAL",
            regime_strategy_map=regime_map,
            strongest_pairs=strongest,
            weakest_pairs=weakest,
            tracked_regimes=list(TRACKED_REGIMES),
            reasons=["regime_strategy_mapping_computed"],
            recommended_actions=_actions(strongest, weakest),
            **_safety_flags(),
        )


def normalize_regime(value: str) -> str:
    normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    return REGIME_ALIASES.get(normalized, normalized or "UNKNOWN")


def _score(metrics: Mapping[str, Any]) -> float:
    evidence = 0.5 if metrics.get("evidence_state") == "INSUFFICIENT" else 1.0
    return evidence * (
        safe_float(metrics.get("average_return")) * 3.0
        + safe_float(metrics.get("win_rate")) * 0.05
        + safe_float(metrics.get("profit_factor")) * 0.5
    )


def _actions(strongest: list[Mapping[str, Any]], weakest: list[Mapping[str, Any]]) -> list[str]:
    actions = []
    if strongest:
        actions.append(f"Increase monitoring of {strongest[0]['strategy']} during {strongest[0]['regime']} before changing advisory weights.")
    if weakest:
        actions.append(f"Review {weakest[0]['strategy']} during {weakest[0]['regime']} for possible advisory suppression.")
    actions.append("Do not convert regime recommendations into execution authority.")
    return actions


def _bucket_counts(values: Iterable[str]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for value in values:
        buckets[value] = buckets.get(value, 0) + 1
    return buckets


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
    }
