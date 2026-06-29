from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


class ContinuousPaperValidationError(RuntimeError):
    """Fail-closed exception for continuous paper validation summaries."""


class ContinuousPaperValidation:
    """Summarize controlled long-duration paper-trading validation sessions."""

    def summarize(self, checkpoints: Iterable[Mapping[str, Any]] | None, *, session_id: str | None = None) -> dict[str, Any]:
        rows = self._rows(checkpoints, session_id=session_id)
        if not rows:
            return self._response(
                session_id=session_id or "DATA UNAVAILABLE",
                start_time=None,
                end_time=None,
                duration=0.0,
                cycle_count=0,
                restart_count=0,
                recovery_count=0,
                alert_count=0,
                error_count=0,
                stale_artifact_count=0,
                runtime_health_status="DATA UNAVAILABLE",
                portfolio_decision_status="DATA UNAVAILABLE",
                recommendation_stability=None,
                average_pipeline_latency=0.0,
                peak_pipeline_latency=0.0,
                average_dashboard_latency=0.0,
                memory_usage_summary={},
                cpu_usage_summary={},
                final_validation_status="RED",
                reasons=["no_validation_checkpoints"],
            )

        start_time = rows[0].get("timestamp") or rows[0].get("start_time")
        end_time = rows[-1].get("timestamp") or rows[-1].get("end_time") or start_time
        duration = self._duration(rows, start_time, end_time)
        cycle_count = max(len(rows), int(max(self._number(row.get("cycle_count"), 0.0) for row in rows)))
        restart_count = int(max(self._number(row.get("restart_count"), 0.0) for row in rows))
        recovery_count = int(max(self._number(row.get("recovery_count"), 0.0) for row in rows))
        alert_count = int(max(self._number(row.get("alert_count"), 0.0) for row in rows))
        error_count = int(max(self._number(row.get("error_count"), 0.0) for row in rows))
        stale_artifact_count = int(max(self._number(row.get("stale_artifact_count"), 0.0) for row in rows))
        runtime_health_status = self._latest_status(rows, "runtime_health_status", "runtime_health", "GREEN")
        portfolio_decision_status = self._latest_status(rows, "portfolio_decision_status", "portfolio_status", "GREEN")
        stability_values = [self._number(row.get("recommendation_stability"), -1.0) for row in rows]
        stability_values = [value for value in stability_values if value >= 0.0]
        recommendation_stability = round(sum(stability_values) / len(stability_values), 6) if stability_values else None
        pipeline_latencies = [
            self._number(row.get("pipeline_latency_ms", row.get("average_pipeline_latency")), 0.0) for row in rows
        ]
        dashboard_latencies = [
            self._number(row.get("dashboard_latency_ms", row.get("average_dashboard_latency")), 0.0) for row in rows
        ]
        memory_values = [self._metric(row.get("memory_usage")) for row in rows]
        cpu_values = [self._metric(row.get("cpu_usage")) for row in rows]
        reasons = self._reasons(
            runtime_health_status=runtime_health_status,
            portfolio_decision_status=portfolio_decision_status,
            recommendation_stability=recommendation_stability,
            restart_count=restart_count,
            recovery_count=recovery_count,
            alert_count=alert_count,
            error_count=error_count,
            stale_artifact_count=stale_artifact_count,
            peak_pipeline_latency=max(pipeline_latencies) if pipeline_latencies else 0.0,
        )
        final_status = self._status(reasons)

        return self._response(
            session_id=str(rows[-1].get("session_id") or session_id or "paper-validation"),
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            cycle_count=cycle_count,
            restart_count=restart_count,
            recovery_count=recovery_count,
            alert_count=alert_count,
            error_count=error_count,
            stale_artifact_count=stale_artifact_count,
            runtime_health_status=runtime_health_status,
            portfolio_decision_status=portfolio_decision_status,
            recommendation_stability=recommendation_stability,
            average_pipeline_latency=self._average(pipeline_latencies),
            peak_pipeline_latency=round(max(pipeline_latencies), 6) if pipeline_latencies else 0.0,
            average_dashboard_latency=self._average(dashboard_latencies),
            memory_usage_summary=self._summary(memory_values),
            cpu_usage_summary=self._summary(cpu_values),
            final_validation_status=final_status,
            reasons=reasons or ["paper_validation_healthy"],
        )

    @staticmethod
    def _rows(checkpoints: Iterable[Mapping[str, Any]] | None, *, session_id: str | None) -> list[dict[str, Any]]:
        if checkpoints is None or isinstance(checkpoints, (str, bytes)):
            return []
        rows: list[dict[str, Any]] = []
        try:
            iterator = iter(checkpoints)
        except TypeError:
            return []
        for item in iterator:
            if not isinstance(item, Mapping):
                continue
            if session_id and str(item.get("session_id") or "") != str(session_id):
                continue
            rows.append(dict(item))
        return sorted(rows, key=lambda row: str(row.get("timestamp") or row.get("start_time") or ""))

    @staticmethod
    def _duration(rows: list[dict[str, Any]], start_time: Any, end_time: Any) -> float:
        explicit = sum(ContinuousPaperValidation._number(row.get("duration_seconds"), 0.0) for row in rows)
        if explicit > 0.0:
            return round(explicit, 6)
        start = ContinuousPaperValidation._parse_time(start_time)
        end = ContinuousPaperValidation._parse_time(end_time)
        if start and end:
            return round(max(0.0, (end - start).total_seconds()), 6)
        return 0.0

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _latest_status(rows: list[dict[str, Any]], primary: str, secondary: str, default: str) -> str:
        for row in reversed(rows):
            value = row.get(primary, row.get(secondary))
            if value:
                return str(value).strip().upper()
        return default

    @staticmethod
    def _reasons(
        *,
        runtime_health_status: str,
        portfolio_decision_status: str,
        recommendation_stability: float | None,
        restart_count: int,
        recovery_count: int,
        alert_count: int,
        error_count: int,
        stale_artifact_count: int,
        peak_pipeline_latency: float,
    ) -> list[str]:
        reasons: list[str] = []
        if runtime_health_status in {"RED", "FAILED", "FAIL", "STOPPED", "DATA UNAVAILABLE"}:
            reasons.append("runtime_health_not_green")
        elif runtime_health_status in {"AMBER", "WARNING", "DEGRADED"}:
            reasons.append("runtime_health_degraded")
        if portfolio_decision_status in {"RED", "FAILED", "FAIL", "DATA UNAVAILABLE"}:
            reasons.append("portfolio_decision_not_green")
        elif portfolio_decision_status in {"AMBER", "WARNING", "DEGRADED"}:
            reasons.append("portfolio_decision_degraded")
        if error_count >= 3:
            reasons.append("error_count_exceeds_limit")
        elif error_count > 0:
            reasons.append("errors_observed")
        if stale_artifact_count >= 3:
            reasons.append("stale_artifacts_exceed_limit")
        elif stale_artifact_count > 0:
            reasons.append("stale_artifacts_observed")
        if restart_count >= 3:
            reasons.append("restart_count_exceeds_limit")
        elif restart_count > 0:
            reasons.append("restarts_observed")
        if recovery_count > 0:
            reasons.append("recoveries_observed")
        if alert_count >= 5:
            reasons.append("alert_count_exceeds_limit")
        elif alert_count > 0:
            reasons.append("alerts_observed")
        if recommendation_stability is not None and recommendation_stability < 50.0:
            reasons.append("recommendation_stability_low")
        elif recommendation_stability is not None and recommendation_stability < 75.0:
            reasons.append("recommendation_stability_degraded")
        if peak_pipeline_latency >= 5000.0:
            reasons.append("pipeline_latency_exceeds_limit")
        elif peak_pipeline_latency >= 1500.0:
            reasons.append("pipeline_latency_degraded")
        return reasons

    @staticmethod
    def _status(reasons: list[str]) -> str:
        red_reasons = {
            "runtime_health_not_green",
            "portfolio_decision_not_green",
            "error_count_exceeds_limit",
            "stale_artifacts_exceed_limit",
            "restart_count_exceeds_limit",
            "recommendation_stability_low",
            "pipeline_latency_exceeds_limit",
        }
        if any(reason in red_reasons for reason in reasons):
            return "RED"
        return "AMBER" if reasons else "GREEN"

    @staticmethod
    def _summary(values: list[float]) -> dict[str, float]:
        if not values:
            return {"average": 0.0, "peak": 0.0}
        return {"average": ContinuousPaperValidation._average(values), "peak": round(max(values), 6)}

    @staticmethod
    def _average(values: list[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    @staticmethod
    def _metric(value: Any) -> float:
        if isinstance(value, Mapping):
            for key in ("percent", "usage_percent", "rss_mb", "value"):
                if key in value:
                    return ContinuousPaperValidation._number(value.get(key), 0.0)
            return 0.0
        return ContinuousPaperValidation._number(value, 0.0)

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _response(**payload: Any) -> dict[str, Any]:
        return {
            "status": "OK" if payload.get("final_validation_status") != "RED" else "DATA UNAVAILABLE"
            if payload.get("cycle_count") == 0
            else "OK",
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
            **payload,
        }
