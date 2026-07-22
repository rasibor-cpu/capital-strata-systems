from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any


class RuntimePerformanceMonitorError(RuntimeError):
    """Fail-closed exception for runtime performance monitoring."""


class RuntimePerformanceMonitor:
    """Advisory-only runtime performance telemetry summarizer."""

    def evaluate(self, telemetry: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(telemetry, Mapping):
            return self._unavailable("telemetry_unavailable")

        pipeline_latency = self._float(telemetry.get("pipeline_latency_ms"))
        dashboard_latency = self._float(telemetry.get("dashboard_latency_ms"))
        api_latencies = self._latency_values(telemetry.get("api_endpoint_latency_ms", telemetry.get("api_latencies_ms", [])))
        persistence_latencies = self._latency_values(
            telemetry.get("json_persistence_latency_ms", telemetry.get("json_persistence_latencies_ms", []))
        )
        execution_times = self._latency_values(telemetry.get("execution_times_ms", []))
        all_times = [value for value in [pipeline_latency, dashboard_latency] if value > 0.0]
        all_times.extend(api_latencies)
        all_times.extend(persistence_latencies)
        all_times.extend(execution_times)

        api_latency = self._average(api_latencies)
        json_persistence_latency = self._average(persistence_latencies)
        average_execution_time = self._average(all_times)
        peak_execution_time = max(all_times) if all_times else 0.0
        rolling_execution_average = self._average(execution_times[-10:]) if execution_times else average_execution_time

        cache_hits = max(0.0, self._float(telemetry.get("cache_hits")))
        cache_misses = max(0.0, self._float(telemetry.get("cache_misses")))
        cache_total = cache_hits + cache_misses
        cache_hit_rate = self._float(telemetry.get("cache_hit_rate")) if telemetry.get("cache_hit_rate") is not None else (
            (cache_hits / cache_total) * 100.0 if cache_total else 0.0
        )
        cache_miss_rate = 100.0 - cache_hit_rate if cache_total else 0.0

        artifact_reads = int(max(0.0, self._float(telemetry.get("artifact_reads"))))
        artifact_writes = int(max(0.0, self._float(telemetry.get("artifact_writes"))))
        memory_usage = telemetry.get("memory_usage", self._memory_usage())
        cpu_usage = telemetry.get("cpu_usage", self._cpu_usage())

        status = "GREEN"
        recommendation = "Runtime performance is within expected operational thresholds."
        if peak_execution_time >= 5000.0 or dashboard_latency >= 3000.0 or pipeline_latency >= 3000.0:
            status = "RED"
            recommendation = "Investigate runtime latency before relying on operational dashboards."
        elif peak_execution_time >= 1500.0 or dashboard_latency >= 1000.0 or pipeline_latency >= 1000.0 or (cache_total and cache_hit_rate < 50.0):
            status = "AMBER"
            recommendation = "Monitor runtime performance and cache efficiency."

        return {
            "status": "OK",
            "overall_status": status,
            "pipeline_latency_ms": round(pipeline_latency, 6),
            "dashboard_latency_ms": round(dashboard_latency, 6),
            "api_latency_ms": round(api_latency, 6),
            "json_persistence_latency_ms": round(json_persistence_latency, 6),
            "cache_hit_rate": round(cache_hit_rate, 6),
            "cache_miss_rate": round(cache_miss_rate, 6),
            "artifact_reads": artifact_reads,
            "artifact_writes": artifact_writes,
            "average_execution_time_ms": round(average_execution_time, 6),
            "peak_execution_time_ms": round(peak_execution_time, 6),
            "rolling_execution_average_ms": round(rolling_execution_average, 6),
            "memory_usage": memory_usage,
            "cpu_usage": cpu_usage,
            "recommendation": recommendation,
            "observed_samples_present": bool(all_times),
            "synthetic_claim": bool(telemetry.get("synthetic")),
            "production_evidence_eligible": bool(all_times) and not bool(telemetry.get("synthetic")),
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _latency_values(raw: Any) -> list[float]:
        if isinstance(raw, Mapping):
            values = raw.values()
        elif isinstance(raw, list | tuple):
            values = raw
        elif raw is None:
            values = []
        else:
            values = [raw]
        result = []
        for value in values:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric >= 0.0:
                result.append(numeric)
        return result

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _memory_usage() -> dict[str, Any] | None:
        try:
            import resource  # type: ignore

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return {"rss_kb": getattr(usage, "ru_maxrss", None)}
        except Exception:
            return None

    @staticmethod
    def _cpu_usage() -> dict[str, Any] | None:
        try:
            return {"process_time_seconds": round(time.process_time(), 6), "pid": os.getpid()}
        except Exception:
            return None

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "overall_status": "RED",
            "pipeline_latency_ms": None,
            "dashboard_latency_ms": None,
            "api_latency_ms": None,
            "json_persistence_latency_ms": None,
            "cache_hit_rate": 0.0,
            "cache_miss_rate": 0.0,
            "artifact_reads": 0,
            "artifact_writes": 0,
            "average_execution_time_ms": None,
            "peak_execution_time_ms": None,
            "rolling_execution_average_ms": None,
            "memory_usage": None,
            "cpu_usage": None,
            "recommendation": f"Runtime performance telemetry unavailable: {reason}.",
            "observed_samples_present": False,
            "synthetic_claim": False,
            "production_evidence_eligible": False,
            "advisory_only": True,
            "execution_allowed": False,
        }
