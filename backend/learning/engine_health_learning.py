from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.portfolio.utils import advisory_response


class EngineHealthLearningEngine:
    """Summarize health of read-only learning and attribution engines."""

    def evaluate(self, learning_packages: Mapping[str, Any] | None = None) -> dict[str, Any]:
        packages = learning_packages if isinstance(learning_packages, Mapping) else {}
        if not packages:
            return advisory_response(
                "DATA UNAVAILABLE",
                learning_health_status="RED",
                package_statuses={},
                blockers=["learning_packages_unavailable"],
                warnings=[],
                recommended_actions=["Collect learning packages before relying on adaptive advisory recommendations."],
            )

        package_statuses = {
            name: str(payload.get("status", "DATA UNAVAILABLE")).upper() if isinstance(payload, Mapping) else "DATA UNAVAILABLE"
            for name, payload in packages.items()
        }
        blockers = [f"{name}_unavailable" for name, status in package_statuses.items() if status == "DATA UNAVAILABLE"]
        warnings = [f"{name}_partial" for name, status in package_statuses.items() if status == "PARTIAL"]
        if blockers:
            health = "RED" if len(blockers) >= max(2, len(package_statuses) // 2) else "AMBER"
        elif warnings:
            health = "AMBER"
        else:
            health = "GREEN"
        return advisory_response(
            "OK" if health != "RED" else "PARTIAL",
            learning_health_status=health,
            package_statuses=package_statuses,
            blockers=blockers,
            warnings=warnings,
            recommended_actions=self._actions(health),
        )

    @staticmethod
    def _actions(health: str) -> list[str]:
        if health == "GREEN":
            return ["Learning engines are producing advisory evidence."]
        if health == "AMBER":
            return ["Review partial learning packages before changing advisory weights."]
        return ["Treat adaptive learning recommendations as unavailable until evidence coverage improves."]
