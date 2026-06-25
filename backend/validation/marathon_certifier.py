from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .marathon_readiness import MarathonReadinessReport
from .marathon_statistics import MarathonStatistics
from .marathon_snapshot import MarathonSnapshot


@dataclass(frozen=True)
class MarathonCertificationReport:
    start_time: str
    end_time: str
    elapsed_time_seconds: float
    cycles_completed: int
    health_summary: dict[str, Any]
    alert_summary: dict[str, Any]
    recovery_summary: dict[str, Any]
    pnl_summary: dict[str, Any]
    decision_summary: dict[str, Any]
    replay_summary: dict[str, Any]
    certification_status: str
    go_no_go: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarathonCertifier:
    """Builds the final marathon certification report."""

    def certify(
        self,
        *,
        start_time: str,
        end_time: str,
        elapsed_time_seconds: float,
        snapshots: list[MarathonSnapshot],
        statistics: MarathonStatistics,
        readiness_report: MarathonReadinessReport,
        stop_reason: str | None,
        replay_summary: dict[str, Any] | None = None,
    ) -> MarathonCertificationReport:
        health_summary = {
            "readiness_status": readiness_report.go_no_go,
            "checks_failed": list(readiness_report.checks_failed),
            "warnings": list(readiness_report.warnings),
            "stop_reason": stop_reason or "COMPLETED",
        }
        alert_summary = {
            "alert_counts": statistics.alert_counts,
        }
        recovery_summary = {
            "recovery_counts": statistics.recovery_counts,
        }
        pnl_summary = {
            "peak_equity": statistics.peak_equity,
            "maximum_drawdown": statistics.maximum_drawdown,
            "portfolio_exposure": statistics.portfolio_exposure,
        }
        decision_summary = {
            "decision_distribution": dict(statistics.decision_distribution),
            "strategy_distribution": dict(statistics.strategy_distribution),
            "regime_distribution": dict(statistics.regime_distribution),
        }
        replay_summary = dict(replay_summary or {})

        certification_status = self._resolve_status(
            readiness_report=readiness_report,
            stop_reason=stop_reason,
            snapshots=snapshots,
        )

        return MarathonCertificationReport(
            start_time=start_time,
            end_time=end_time,
            elapsed_time_seconds=round(float(elapsed_time_seconds), 8),
            cycles_completed=len(snapshots),
            health_summary=health_summary,
            alert_summary=alert_summary,
            recovery_summary=recovery_summary,
            pnl_summary=pnl_summary,
            decision_summary=decision_summary,
            replay_summary=replay_summary,
            certification_status=certification_status,
            go_no_go=certification_status,
        )

    @staticmethod
    def _resolve_status(
        *,
        readiness_report: MarathonReadinessReport,
        stop_reason: str | None,
        snapshots: list[MarathonSnapshot],
    ) -> str:
        if readiness_report.go_no_go != "GO":
            return "NO_GO"
        if stop_reason:
            return "NO_GO"
        if readiness_report.warnings:
            return "CONDITIONAL_GO"
        if not snapshots:
            return "NO_GO"
        return "GO"
