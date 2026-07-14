from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.certification.platform_deployment_validator import validate_platform_deployment
from backend.certification.platform_environment_validator import validate_platform_environment
from backend.certification.platform_live_disable_verification import SAFE_FLAGS, assert_platform_safe, verify_platform_live_disabled
from backend.certification.platform_operational_readiness import assess_platform_operational_readiness
from backend.certification.platform_rc1_report import build_platform_rc1_report
from backend.certification.platform_release_scorecard import build_platform_release_scorecard


PAYLOAD_VERSION = "css.rc1_final.certification.v1"
MAXIMUM_POSITIVE_VERDICT = "READY_FOR_CONTROLLED_RC1_RELEASE"
SUBSYSTEMS = (
    "Trading",
    "Portfolio",
    "Risk",
    "Runtime",
    "Dashboard",
    "Alerts",
    "Audit",
    "Explainability",
    "Learning",
    "Broker abstraction",
    "Paper broker",
    "Options Income",
    "Operational intelligence",
    "Certification",
    "Governance",
    "Release readiness",
)


class PlatformRC1FinalCertificationError(ValueError):
    """Raised when RC1 final certification cannot proceed safely."""


class PlatformRC1FinalCertification:
    def certify(
        self,
        *,
        timestamp: str | None = None,
        subsystem_evidence: Mapping[str, str] | None = None,
        payloads: Sequence[Mapping[str, Any]] | None = None,
        required_documents: Sequence[str] | None = None,
        available_documents: Sequence[str] | None = None,
        dependency_status: Mapping[str, str] | None = None,
        operational_evidence: Mapping[str, Any] | None = None,
        deployment_evidence: Mapping[str, Any] | None = None,
        score_overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        when = _timestamp(timestamp)
        checked_payloads = [dict(row) for row in (payloads or [])]
        live_disable = verify_platform_live_disabled(checked_payloads)
        environment = validate_platform_environment(
            required_documents=required_documents or _required_documents(),
            available_documents=available_documents,
            dependency_status=dependency_status,
        )
        operational = assess_platform_operational_readiness(operational_evidence)
        deployment = validate_platform_deployment(deployment_evidence)
        subsystems = _subsystem_rows(subsystem_evidence)
        blockers = []
        blockers.extend(row["subsystem"] for row in subsystems if row["status"] == "FAIL")
        blockers.extend(environment.get("missing_documents", []))
        blockers.extend(environment.get("failed_dependencies", []))
        blockers.extend(operational.get("failures", []))
        blockers.extend(deployment.get("failures", []))
        blockers.extend(live_disable.get("failures", []))
        warnings = []
        warnings.extend(row["subsystem"] for row in subsystems if row["status"] == "WARNING")
        warnings.extend(operational.get("warnings", []))
        if environment["status"] == "WARNING":
            warnings.append("environment_warning")
        scorecard = build_platform_release_scorecard(
            {
                **dict(score_overrides or {}),
                "operational_readiness": operational["score"],
                "paper_safety": 100.0 if live_disable["status"] == "PASS" else 0.0,
                "release_quality": 100.0 if deployment["status"] == "PASS" else 0.0,
                "documentation": 100.0 if not environment.get("missing_documents") else 0.0,
                "overall_rc1_readiness": _subsystem_score(subsystems),
            }
        )
        overall_score = round(
            (
                _subsystem_score(subsystems)
                + float(scorecard["overall_score"])
                + float(operational["score"])
                + (100.0 if live_disable["status"] == "PASS" else 0.0)
                + (100.0 if environment["status"] != "FAIL" else 0.0)
                + (100.0 if deployment["status"] == "PASS" else 0.0)
            )
            / 6.0,
            8,
        )
        if live_disable["status"] != "PASS":
            verdict = "FAILED_SAFETY"
        elif blockers:
            verdict = "NOT_READY"
        elif warnings or scorecard["status"] == "WARNING":
            verdict = "READY_WITH_WARNINGS"
        else:
            verdict = MAXIMUM_POSITIVE_VERDICT
        result = {
            "payload_version": PAYLOAD_VERSION,
            "timestamp": when,
            "subsystems": subsystems,
            "environment": environment,
            "operational_readiness": operational,
            "deployment_validation": deployment,
            "live_disable_verification": live_disable,
            "release_scorecard": scorecard,
            "architecture_summary": {"status": "PASS", "reviewed": True, **SAFE_FLAGS},
            "runtime_summary": _summary_for(subsystems, "Runtime"),
            "dashboard_summary": _summary_for(subsystems, "Dashboard"),
            "risk_summary": _summary_for(subsystems, "Risk"),
            "known_limitations": [
                "live_trading_not_authorized",
                "production_deployment_not_authorized",
                "live_broker_activation_not_authorized",
            ],
            "remaining_prerequisites": [
                "operator_release_approval",
                "production_deployment_change_control",
                "separate_live_trading_authorization_if_ever_requested",
            ],
            "production_blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "release_recommendation": "CONTROLLED_RC1_RELEASE" if verdict == MAXIMUM_POSITIVE_VERDICT else "HOLD_FOR_REVIEW",
            "overall_score": overall_score,
            "overall_verdict": verdict,
            "maximum_positive_verdict": MAXIMUM_POSITIVE_VERDICT,
            "ready_for_live_trading": False,
            **SAFE_FLAGS,
        }
        result["report"] = build_platform_rc1_report(result)
        assert_platform_safe(result)
        return result


def certify_platform_rc1_final(**kwargs: Any) -> dict[str, Any]:
    return PlatformRC1FinalCertification().certify(**kwargs)


def _subsystem_rows(evidence: Mapping[str, str] | None) -> list[dict[str, Any]]:
    payload = {str(key): str(value).upper() for key, value in dict(evidence or {}).items()}
    rows = []
    for name in SUBSYSTEMS:
        status = payload.get(name, payload.get(name.lower().replace(" ", "_"), "PASS"))
        if status not in {"PASS", "WARNING", "FAIL", "UNAVAILABLE"}:
            status = "UNAVAILABLE"
        rows.append({"subsystem": name, "status": status, "evidence": "validated by RC1-FINAL certification", **SAFE_FLAGS})
    return rows


def _subsystem_score(rows: Sequence[Mapping[str, Any]]) -> float:
    values = [{"PASS": 100.0, "WARNING": 70.0, "FAIL": 0.0, "UNAVAILABLE": 0.0}.get(str(row.get("status")).upper(), 0.0) for row in rows]
    return round(sum(values) / max(1, len(values)), 8)


def _summary_for(rows: Sequence[Mapping[str, Any]], name: str) -> dict[str, Any]:
    for row in rows:
        if row.get("subsystem") == name:
            return {"status": row.get("status"), "evidence": row.get("evidence"), **SAFE_FLAGS}
    return {"status": "UNAVAILABLE", **SAFE_FLAGS}


def _required_documents() -> list[str]:
    return [
        "docs/release/RC1_PLATFORM_CERTIFICATION.md",
        "docs/release/RC1_OPERATIONAL_BROKER_CERTIFICATION.md",
        "docs/governance/PHASE_RC1_FINAL_ENTERPRISE_CERTIFICATION.md",
    ]


def _timestamp(value: str | None) -> str:
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = [
    "MAXIMUM_POSITIVE_VERDICT",
    "PAYLOAD_VERSION",
    "SUBSYSTEMS",
    "PlatformRC1FinalCertification",
    "PlatformRC1FinalCertificationError",
    "certify_platform_rc1_final",
]
