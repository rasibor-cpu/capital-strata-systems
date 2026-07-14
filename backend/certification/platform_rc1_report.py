from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping

from backend.certification.platform_live_disable_verification import SAFE_FLAGS


PAYLOAD_VERSION = "css.rc1_final.report.v1"


class PlatformRC1ReportBuilder:
    def build(self, certification: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(certification)
        report = {
            "payload_version": PAYLOAD_VERSION,
            "report_id": _stable_id(payload),
            "platform": "Capital Strata Systems",
            "release": "RC1",
            "timestamp": payload.get("timestamp"),
            "platform_overview": "Integrated institutional paper-trading platform certification.",
            "subsystem_certification": payload.get("subsystems", []),
            "architecture_summary": payload.get("architecture_summary", {}),
            "runtime_summary": payload.get("runtime_summary", {}),
            "dashboard_summary": payload.get("dashboard_summary", {}),
            "risk_summary": payload.get("risk_summary", {}),
            "operational_readiness": payload.get("operational_readiness", {}),
            "paper_safety": payload.get("live_disable_verification", {}),
            "known_limitations": payload.get("known_limitations", []),
            "remaining_prerequisites": payload.get("remaining_prerequisites", []),
            "production_blockers": payload.get("production_blockers", []),
            "release_recommendation": payload.get("release_recommendation"),
            "overall_score": payload.get("overall_score"),
            "overall_verdict": payload.get("overall_verdict"),
            "markdown": self.to_markdown(payload),
            **SAFE_FLAGS,
        }
        return report

    def to_markdown(self, payload: Mapping[str, Any]) -> str:
        lines = [
            "# RC1 Final Enterprise Certification Report",
            "",
            f"**Overall Verdict:** {payload.get('overall_verdict')}",
            f"**Overall Score:** {payload.get('overall_score')}",
            f"**Release Recommendation:** {payload.get('release_recommendation')}",
            "",
            "## Subsystem Certification",
        ]
        for row in payload.get("subsystems", []):
            lines.append(f"- **{row.get('subsystem')}**: {row.get('status')} - {row.get('evidence')}")
        lines.extend(["", "## Safety", "Live trading remains blocked. This report does not authorize live execution."])
        return "\n".join(lines)


def build_platform_rc1_report(certification: Mapping[str, Any]) -> dict[str, Any]:
    return PlatformRC1ReportBuilder().build(certification)


def _stable_id(payload: Mapping[str, Any]) -> str:
    raw = json.dumps({key: value for key, value in payload.items() if key != "report"}, sort_keys=True, default=str)
    return "rc1-final-" + sha256(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["PAYLOAD_VERSION", "PlatformRC1ReportBuilder", "build_platform_rc1_report"]
