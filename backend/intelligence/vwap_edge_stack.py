from __future__ import annotations

from typing import Dict, List


def clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class VWAPElasticityEngine:
    """
    Measures how stretched price is relative to VWAP momentum.

    elasticity = abs(vwap deviation) / abs(momentum)

    Higher elasticity = greater probability of mean reversion.
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        for r in rows:

            vwap_dev_abs = abs(_safe_float(r.get("vwap_dev_abs"), 0.0))
            momentum = abs(_safe_float(r.get("momentum"), 0.0)) + 1e-6

            elasticity = vwap_dev_abs / momentum

            elasticity_score = clamp01(elasticity * 0.6)

            row = dict(r)

            row["vwap_elasticity"] = elasticity
            row["elasticity_score"] = elasticity_score

            enriched.append(row)

        return enriched


class ReversalPressureEngine:
    """
    Measures how likely a stretched move is starting to exhaust.

    Components:
    - VWAP stretch
    - momentum decay
    - spread quality
    - elasticity reinforcement
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        for r in rows:

            vwap_dev_abs = abs(_safe_float(r.get("vwap_dev_abs"), 0.0))
            momentum_abs = abs(_safe_float(r.get("momentum"), 0.0))
            spread_pct = abs(_safe_float(r.get("spread_pct"), 0.0))
            elasticity_score = clamp01(_safe_float(r.get("elasticity_score"), 0.0))

            stretch_score = clamp01(vwap_dev_abs * 35.0)

            momentum_decay_score = clamp01(1.0 - (momentum_abs * 22.0))

            spread_score = clamp01(1.0 - (spread_pct * 120.0))

            pressure = (
                0.40 * stretch_score
                + 0.30 * momentum_decay_score
                + 0.15 * spread_score
                + 0.15 * elasticity_score
            )

            row = dict(r)

            row["stretch_score"] = stretch_score
            row["momentum_decay_score"] = momentum_decay_score
            row["spread_quality_score"] = spread_score
            row["reversal_pressure_score"] = clamp01(pressure)

            enriched.append(row)

        return enriched


class EliteSignalClassifier:
    """
    Converts enriched signal state into execution class.

    Classes:
    - ELITE
    - STRONG
    - WATCH
    - IGNORE
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        for r in rows:

            ai_score = clamp01(_safe_float(r.get("ai_score"), 0.0))
            elasticity_score = clamp01(_safe_float(r.get("elasticity_score"), 0.0))
            reversal_pressure_score = clamp01(_safe_float(r.get("reversal_pressure_score"), 0.0))
            spread_quality_score = clamp01(_safe_float(r.get("spread_quality_score"), 0.0))
            signal_strength = clamp01(_safe_float(r.get("signal_strength"), 0.0))

            elite_signal_score = clamp01(
                0.28 * ai_score
                + 0.22 * elasticity_score
                + 0.24 * reversal_pressure_score
                + 0.12 * spread_quality_score
                + 0.14 * signal_strength
            )

            if (
                elite_signal_score >= 0.78
                and reversal_pressure_score >= 0.68
                and elasticity_score >= 0.55
                and spread_quality_score >= 0.50
            ):
                elite_class = "ELITE"

            elif (
                elite_signal_score >= 0.66
                and reversal_pressure_score >= 0.56
                and spread_quality_score >= 0.45
            ):
                elite_class = "STRONG"

            elif elite_signal_score >= 0.52:
                elite_class = "WATCH"

            else:
                elite_class = "IGNORE"

            row = dict(r)

            row["elite_signal_score"] = elite_signal_score
            row["elite_class"] = elite_class

            enriched.append(row)

        return enriched


class EntryReadinessEngine:
    """
    Final trade gating layer.

    Produces:
    - entry_readiness_score
    - entry_ready
    - dashboard_decision
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        for r in rows:

            ai_score = clamp01(_safe_float(r.get("ai_score"), 0.0))
            elite_signal_score = clamp01(_safe_float(r.get("elite_signal_score"), 0.0))
            reversal_pressure_score = clamp01(_safe_float(r.get("reversal_pressure_score"), 0.0))
            elasticity_score = clamp01(_safe_float(r.get("elasticity_score"), 0.0))
            spread_quality_score = clamp01(_safe_float(r.get("spread_quality_score"), 0.0))

            readiness = clamp01(
                0.26 * ai_score
                + 0.28 * elite_signal_score
                + 0.22 * reversal_pressure_score
                + 0.14 * elasticity_score
                + 0.10 * spread_quality_score
            )

            elite_class = str(r.get("elite_class", "IGNORE")).upper()

            entry_ready = (
                readiness >= 0.72
                and elite_class in {"ELITE", "STRONG"}
                and reversal_pressure_score >= 0.58
                and spread_quality_score >= 0.45
            )

            if entry_ready and elite_class == "ELITE":
                dashboard_decision = "TRADE"

            elif elite_class in {"ELITE", "STRONG"} and readiness >= 0.62:
                dashboard_decision = "WATCH"

            elif readiness >= 0.50:
                dashboard_decision = "WATCH"

            else:
                dashboard_decision = "IGNORE"

            row = dict(r)

            row["entry_readiness_score"] = readiness
            row["entry_ready"] = entry_ready
            row["dashboard_decision"] = dashboard_decision

            enriched.append(row)

        return enriched


class VWAPEdgeStack:
    """
    Runs the full VWAP edge stack sequentially.
    """

    def __init__(self) -> None:

        self.elasticity_engine = VWAPElasticityEngine()
        self.reversal_pressure_engine = ReversalPressureEngine()
        self.elite_signal_classifier = EliteSignalClassifier()
        self.entry_readiness_engine = EntryReadinessEngine()

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        rows = self.elasticity_engine.enrich_rows(rows)
        rows = self.reversal_pressure_engine.enrich_rows(rows)
        rows = self.elite_signal_classifier.enrich_rows(rows)
        rows = self.entry_readiness_engine.enrich_rows(rows)

        return rows