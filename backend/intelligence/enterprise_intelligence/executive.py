"""DIP-005 Executive Intelligence summaries."""

from __future__ import annotations

import statistics
from typing import Any, Sequence

from backend.intelligence.edge_intelligence.models import EdgeRecord
from backend.intelligence.enterprise_intelligence.models import (
    CapitalIntelligenceReport,
    ENTERPRISE_INTELLIGENCE_VERSION,
    EvidenceReference,
    ExecutiveIntelligenceSummary,
    canonical_hash,
)
from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.schema import TradeDNARecord


class ExecutiveIntelligenceEngine:
    """Explainable executive summaries from historical evidence only."""

    def __init__(
        self,
        *,
        dna_records: Sequence[TradeDNARecord],
        derived_metrics: Sequence[DerivedTradeMetrics],
        edge_records: Sequence[EdgeRecord],
        capital_report: CapitalIntelligenceReport,
        generated_at: str,
    ) -> None:
        self.dna_records = sorted(dna_records, key=lambda r: (r.identity.trade_id, r.identity.dna_id))
        self.derived_metrics = sorted(derived_metrics, key=lambda m: (m.trade_id, m.dna_id))
        self.edge_records = sorted(edge_records, key=lambda e: e.edge_id)
        self.capital_report = capital_report
        self.generated_at = generated_at

    def build_summary(self) -> ExecutiveIntelligenceSummary:
        summary = {
            "portfolio_health": self._portfolio_health(),
            "strategy_health": self._strategy_health(),
            "edge_health": self._edge_health(),
            "capital_health": self._capital_health(),
            "execution_quality": self._execution_quality(),
            "evidence_quality": self._evidence_quality(),
            "profitability_trends": self._profitability_trends(),
            "drawdown_trends": self._drawdown_trends(),
        }
        alerts = tuple(self._alerts(summary))
        return ExecutiveIntelligenceSummary(
            generated_at=self.generated_at,
            summary=summary,
            operational_alerts=alerts,
            evidence=self._evidence(),
        ).with_hash()

    def _portfolio_health(self) -> dict[str, Any]:
        profit = float(self.capital_report.metrics.get("realized_profitability", 0.0))
        drawdown = float(self.capital_report.metrics.get("drawdown_utilization", 0.0))
        label = "HEALTHY" if profit > 0 and drawdown <= 0.10 else "WATCH" if profit >= 0 else "STRESSED"
        payload = {
            "status": label,
            "profit": profit,
            "drawdown_utilization": drawdown,
            "explanation": "Derived from realized historical profitability and drawdown utilization.",
        }
        payload["provenance"] = self._metric_provenance(
            "portfolio_health",
            "Portfolio health from realized profitability and drawdown utilization.",
            payload,
        )
        return payload

    def _strategy_health(self) -> dict[str, Any]:
        buckets: dict[str, float] = {}
        by_dna = {metric.dna_id: metric for metric in self.derived_metrics}
        for record in self.dna_records:
            metric = by_dna.get(record.identity.dna_id)
            if metric is None:
                continue
            strategy = record.strategy.strategy_id or "UNAVAILABLE"
            buckets[strategy] = buckets.get(strategy, 0.0) + float(metric.profit or 0.0)
        ranked = [
            {"strategy_id": key, "profit": round(value, 10)}
            for key, value in sorted(buckets.items(), key=lambda item: (-item[1], item[0]))
        ]
        positive = sum(1 for row in ranked if row["profit"] > 0)
        payload = {
            "status": "HEALTHY" if positive == len(ranked) and ranked else "MIXED" if positive else "WEAK",
            "ranked_strategies": ranked,
            "explanation": "Aggregates historical profit by Trade DNA strategy_id.",
        }
        payload["provenance"] = self._metric_provenance(
            "strategy_health",
            "Strategy health from historical profit grouped by strategy_id.",
            payload,
        )
        return payload

    def _edge_health(self) -> dict[str, Any]:
        supported = [edge for edge in self.edge_records if edge.evidence_threshold == "SUPPORTED"]
        drifting = [edge for edge in self.edge_records if edge.current_drift in {"DEGRADING", "DECAYING", "REGIME_SHIFT"}]
        stable = [edge for edge in self.edge_records if edge.current_stability_label == "STABLE"]
        payload = {
            "status": "HEALTHY" if supported and not drifting else "WATCH" if supported else "INSUFFICIENT",
            "supported_edges": [edge.edge_id for edge in supported],
            "stable_edges": [edge.edge_id for edge in stable],
            "drift_alert_edges": [edge.edge_id for edge in drifting],
            "explanation": "Summarizes DIP-004 EdgeRecord threshold, stability, and drift states.",
        }
        payload["provenance"] = self._metric_provenance(
            "edge_health",
            "Edge health from threshold, stability, and drift states.",
            payload,
            edge_ids=tuple(edge.edge_id for edge in self.edge_records),
        )
        return payload

    def _capital_health(self) -> dict[str, Any]:
        efficiency = float(self.capital_report.metrics.get("capital_efficiency", 0.0))
        retention = float(self.capital_report.metrics.get("profit_retention", 0.0))
        payload = {
            "status": "HEALTHY" if efficiency > 0 and retention > 0.5 else "WATCH",
            "capital_efficiency": efficiency,
            "profit_retention": retention,
            "explanation": "Derived from capital efficiency and historical profit retention.",
        }
        payload["provenance"] = self._metric_provenance(
            "capital_health",
            "Capital health from capital efficiency and profit retention.",
            payload,
        )
        return payload

    def _execution_quality(self) -> dict[str, Any]:
        values = [float(metric.execution_quality) for metric in self.derived_metrics if metric.execution_quality is not None]
        average = statistics.fmean(values) if values else 0.0
        payload = {
            "status": "AVAILABLE" if values else "UNAVAILABLE",
            "average_execution_quality": round(average, 10),
            "sample_size": len(values),
            "explanation": "Uses historical derived execution_quality values only.",
        }
        payload["provenance"] = self._metric_provenance(
            "execution_quality",
            "Execution quality from historical derived execution_quality values.",
            payload,
        )
        return payload

    def _evidence_quality(self) -> dict[str, Any]:
        dna_count = len(self.dna_records)
        metric_count = len(self.derived_metrics)
        edge_count = len(self.edge_records)
        complete = min(dna_count, metric_count)
        completeness = complete / dna_count if dna_count else 0.0
        payload = {
            "status": "COMPLETE" if completeness >= 1.0 and edge_count else "PARTIAL",
            "dna_records": dna_count,
            "derived_metrics": metric_count,
            "edge_records": edge_count,
            "completeness": round(completeness, 10),
            "explanation": "Compares historical DNA, derived metrics, and Edge Registry coverage.",
        }
        payload["provenance"] = self._metric_provenance(
            "evidence_quality",
            "Evidence quality from DNA, derived metric, and Edge Registry coverage.",
            payload,
            edge_ids=tuple(edge.edge_id for edge in self.edge_records),
        )
        return payload

    def _profitability_trends(self) -> dict[str, Any]:
        trends = list(self.capital_report.trends)
        direction = "FLAT"
        if len(trends) >= 2:
            direction = "IMPROVING" if trends[-1]["profit"] > trends[0]["profit"] else "DECLINING" if trends[-1]["profit"] < trends[0]["profit"] else "FLAT"
        payload = {
            "direction": direction,
            "periods": trends,
            "explanation": "Compares deterministic historical capital trend periods.",
        }
        payload["provenance"] = self._metric_provenance(
            "profitability_trends",
            "Profitability trend direction from historical capital trend periods.",
            payload,
        )
        return payload

    def _drawdown_trends(self) -> dict[str, Any]:
        payload = {
            "drawdown_utilization": self.capital_report.metrics.get("drawdown_utilization", 0.0),
            "drawdown_recovery": self.capital_report.metrics.get("drawdown_recovery", 0.0),
            "explanation": "Derived from cumulative historical profit path.",
        }
        payload["provenance"] = self._metric_provenance(
            "drawdown_trends",
            "Drawdown trends from historical drawdown utilization and recovery.",
            payload,
        )
        return payload

    def _alerts(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        alerts = []
        for key in ("portfolio_health", "capital_health", "edge_health"):
            section = summary[key]
            if section["status"] not in {"HEALTHY", "COMPLETE", "AVAILABLE"}:
                alerts.append(
                    {
                        "severity": "ADVISORY",
                        "section": key,
                        "status": section["status"],
                        "explanation": section["explanation"],
                    }
                )
        return sorted(alerts, key=lambda row: row["section"])

    def _evidence(self) -> EvidenceReference:
        return EvidenceReference(
            trade_ids=tuple(sorted(record.identity.trade_id for record in self.dna_records)),
            dna_ids=tuple(sorted(record.identity.dna_id for record in self.dna_records)),
            edge_ids=tuple(sorted(edge.edge_id for edge in self.edge_records)),
            calculations=(
                "portfolio_health",
                "strategy_health",
                "edge_health",
                "capital_health",
                "execution_quality",
                "evidence_quality",
                "profitability_trends",
                "drawdown_trends",
                "operational_alerts",
            ),
        )

    def _metric_provenance(
        self,
        metric_name: str,
        metric_definition: str,
        metric_payload: dict[str, Any],
        *,
        edge_ids: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        dna_ids = tuple(sorted(record.identity.dna_id for record in self.dna_records))
        edges = tuple(sorted(edge_ids))
        payload = {
            "metric_name": metric_name,
            "metric_definition": metric_definition,
            "contributing_trade_dna_ids": dna_ids,
            "contributing_edge_ids": edges,
            "calculation_version": ENTERPRISE_INTELLIGENCE_VERSION,
            "evidence_version": EVIDENCE_VERSION,
            "analysis_version": ANALYSIS_VERSION,
            "metric_value": {
                key: value
                for key, value in metric_payload.items()
                if key not in {"explanation", "provenance"}
            },
        }
        payload["metric_hash"] = canonical_hash(payload)
        return {
            "contributing_trade_dna_ids": list(dna_ids),
            "contributing_edge_ids": list(edges),
            "calculation_version": ENTERPRISE_INTELLIGENCE_VERSION,
            "evidence_version": EVIDENCE_VERSION,
            "analysis_version": ANALYSIS_VERSION,
            "metric_definition": metric_definition,
            "metric_hash": payload["metric_hash"],
        }
