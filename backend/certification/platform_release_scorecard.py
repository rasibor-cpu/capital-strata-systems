from __future__ import annotations

from typing import Any, Mapping

from backend.certification.platform_live_disable_verification import SAFE_FLAGS


PAYLOAD_VERSION = "css.rc1_final.release_scorecard.v1"
SCORE_DIMENSIONS = (
    "architecture",
    "integration",
    "operational_readiness",
    "paper_safety",
    "runtime_stability",
    "dashboard_readiness",
    "risk_governance",
    "broker_abstraction",
    "observability",
    "documentation",
    "release_quality",
    "maintainability",
    "overall_rc1_readiness",
)


class PlatformReleaseScorecard:
    def score(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(evidence or {})
        scores = {}
        for name in SCORE_DIMENSIONS:
            scores[name] = _bounded(payload.get(name, 100.0))
        overall = round(sum(scores.values()) / max(1, len(scores)), 8)
        status = "FAIL" if overall < 60 else ("WARNING" if overall < 90 else "PASS")
        return {
            "payload_version": PAYLOAD_VERSION,
            "status": status,
            "scores": scores,
            "overall_score": overall,
            "maximum_positive_verdict": "READY_FOR_CONTROLLED_RC1_RELEASE",
            **SAFE_FLAGS,
        }


def build_platform_release_scorecard(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return PlatformReleaseScorecard().score(evidence)


def _bounded(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(100.0, numeric)), 8)


__all__ = ["PAYLOAD_VERSION", "SCORE_DIMENSIONS", "PlatformReleaseScorecard", "build_platform_release_scorecard"]
