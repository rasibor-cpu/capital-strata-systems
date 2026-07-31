"""DIP-005 deterministic enterprise reporting."""

from __future__ import annotations

from typing import Any, Sequence

from backend.intelligence.edge_intelligence.models import EdgeRecord
from backend.intelligence.enterprise_intelligence.models import (
    CapitalIntelligenceReport,
    ENTERPRISE_REPORT_SCHEMA_VERSION,
    EnterpriseIntelligenceReport,
    EvidenceReference,
    ExecutiveIntelligenceSummary,
    canonical_hash,
)
from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.schema import TradeDNARecord


class EnterpriseReportBuilder:
    """Build read-only deterministic enterprise reports."""

    def __init__(
        self,
        *,
        dna_records: Sequence[TradeDNARecord],
        derived_metrics: Sequence[DerivedTradeMetrics],
        edge_records: Sequence[EdgeRecord],
        capital_report: CapitalIntelligenceReport,
        executive_summary: ExecutiveIntelligenceSummary,
        generated_at: str,
        generation_parameters: dict[str, Any] | None = None,
        report_type: str = "ENTERPRISE_INTELLIGENCE",
    ) -> None:
        self.dna_records = sorted(dna_records, key=lambda r: (r.identity.trade_id, r.identity.dna_id))
        self.derived_metrics = sorted(derived_metrics, key=lambda m: (m.trade_id, m.dna_id))
        self.edge_records = sorted(edge_records, key=lambda e: e.edge_id)
        self.capital_report = capital_report
        self.executive_summary = executive_summary
        self.generated_at = generated_at
        self.generation_parameters = dict(generation_parameters or {"period_days": capital_report.period_days})
        self.report_type = report_type

    def build_report(self) -> EnterpriseIntelligenceReport:
        sections = {
            "executive_summary": self.executive_summary.to_dict(include_caller_metadata=False),
            "strategy_performance": self._strategy_performance(),
            "edge_performance": self._edge_performance(),
            "capital_performance": self.capital_report.to_dict(include_caller_metadata=False),
            "drawdown_analysis": self._drawdown_analysis(),
            "exposure_analysis": list(self.capital_report.exposure_history),
            "profitability_run_rate": self._profitability_run_rate(),
            "historical_trend_analysis": list(self.capital_report.trends),
            "decision_intelligence_summary": self._decision_intelligence_summary(),
        }
        return EnterpriseIntelligenceReport(
            generated_at=self.generated_at,
            sections=sections,
            evidence=self._evidence(),
            generation_parameters=self.generation_parameters,
            canonical_report_id=canonical_hash(
                {
                    "report_type": self.report_type,
                    "report_schema_version": ENTERPRISE_REPORT_SCHEMA_VERSION,
                    "analysis_version": ANALYSIS_VERSION,
                    "evidence_version": EVIDENCE_VERSION,
                    "generation_parameters": self.generation_parameters,
                    "trade_dna_ids": tuple(sorted(record.identity.dna_id for record in self.dna_records)),
                    "edge_ids": tuple(sorted(edge.edge_id for edge in self.edge_records)),
                }
            ),
            report_type=self.report_type,
        ).with_hash()

    def _strategy_performance(self) -> list[dict[str, Any]]:
        by_dna = {metric.dna_id: metric for metric in self.derived_metrics}
        buckets: dict[str, dict[str, Any]] = {}
        for record in self.dna_records:
            metric = by_dna.get(record.identity.dna_id)
            if metric is None:
                continue
            strategy = record.strategy.strategy_id or "UNAVAILABLE"
            bucket = buckets.setdefault(strategy, {"profit": 0.0, "trades": []})
            bucket["profit"] += float(metric.profit or 0.0)
            bucket["trades"].append(record.identity.trade_id)
        rows = [
            {
                "strategy_id": strategy,
                "profit": round(bucket["profit"], 10),
                "trade_count": len(bucket["trades"]),
                "trade_ids": sorted(bucket["trades"]),
                "explanation": "Historical profit grouped by Trade DNA strategy_id.",
            }
            for strategy, bucket in sorted(buckets.items())
        ]
        rows.sort(key=lambda row: (-row["profit"], row["strategy_id"]))
        return rows

    def _edge_performance(self) -> list[dict[str, Any]]:
        return [
            {
                "edge_id": edge.edge_id,
                "name": edge.name,
                "confidence": edge.current_confidence,
                "stability": edge.current_stability,
                "drift": edge.current_drift,
                "sample_size": edge.sample_size,
                "trade_references": list(edge.trade_references),
                "evidence_references": list(edge.evidence_references),
                "explanation": edge.explanation.get("summary", ""),
            }
            for edge in self.edge_records
        ]

    def _drawdown_analysis(self) -> dict[str, Any]:
        return {
            "drawdown_utilization": self.capital_report.metrics.get("drawdown_utilization", 0.0),
            "drawdown_recovery": self.capital_report.metrics.get("drawdown_recovery", 0.0),
            "explanation": "Read-only projection from historical capital intelligence.",
        }

    def _profitability_run_rate(self) -> dict[str, Any]:
        return {
            "per_day": self.capital_report.metrics.get("historical_run_rate_per_day", 0.0),
            "per_period": self.capital_report.metrics.get("historical_run_rate_per_period", 0.0),
            "period_days": self.capital_report.period_days,
            "explanation": "Historical run rate from closed Trade DNA outcomes.",
        }

    def _decision_intelligence_summary(self) -> dict[str, Any]:
        return {
            "trade_count": len(self.dna_records),
            "edge_count": len(self.edge_records),
            "capital_report_hash": self.capital_report.report_hash,
            "executive_summary_hash": self.executive_summary.summary_hash,
            "explanation": "Combines DIP-002 Trade DNA, DIP-003 derived metrics, DIP-004 Edge Registry, and DIP-005 enterprise intelligence.",
        }

    def _evidence(self) -> EvidenceReference:
        return EvidenceReference(
            trade_ids=tuple(sorted(record.identity.trade_id for record in self.dna_records)),
            dna_ids=tuple(sorted(record.identity.dna_id for record in self.dna_records)),
            edge_ids=tuple(sorted(edge.edge_id for edge in self.edge_records)),
            calculations=(
                "executive_summary",
                "strategy_performance",
                "edge_performance",
                "capital_performance",
                "drawdown_analysis",
                "exposure_analysis",
                "profitability_run_rate",
                "historical_trend_analysis",
                "decision_intelligence_summary",
            ),
        )
