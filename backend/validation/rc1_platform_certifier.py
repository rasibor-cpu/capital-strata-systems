from __future__ import annotations

import json
from typing import Any, Mapping

from backend.validation.rc1_consistency_checker import RC1ConsistencyChecker
from backend.validation.rc1_runtime_auditor import RC1RuntimeAuditor
from backend.validation.rc1_release_recommender import RC1ReleaseRecommender


class RC1PlatformCertifier:
    """Orchestrates comprehensive checks, audits, and scorecard reviews for the RC1 release candidate."""

    def __init__(
        self,
        *,
        checker: RC1ConsistencyChecker | None = None,
        auditor: RC1RuntimeAuditor | None = None,
        recommender: RC1ReleaseRecommender | None = None,
    ) -> None:
        self.checker = checker or RC1ConsistencyChecker()
        self.auditor = auditor or RC1RuntimeAuditor()
        self.recommender = recommender or RC1ReleaseRecommender()

    def certify(
        self,
        *,
        portfolio_construction: Mapping[str, Any] | None = None,
        optimizer: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
        brief: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 1. Run consistency checks
        consistency_res = self.checker.run_all_checks(
            portfolio_construction=portfolio_construction,
            optimizer=optimizer,
            committee=committee,
            brief=brief,
            decision_confidence=decision_confidence,
            broker_health=broker_health,
            runtime_health=runtime_health,
        )

        # 2. Run auditor
        audit_res = self.auditor.perform_audit(
            portfolio_construction=portfolio_construction,
            committee=committee,
            brief=brief,
            decision_confidence=decision_confidence,
        )

        # 3. Perform release evaluation
        eval_res = self.recommender.evaluate_release(
            consistency_results=consistency_res,
            audit_results=audit_res,
        )

        # 4. Strictly assert safety gates (advisory only)
        # Verify that if any parameters allow execution, we override and force fail-closed status.
        safe = True
        for payload in [portfolio_construction, committee, brief]:
            if payload:
                advisory = payload.get("advisory_only")
                exec_allowed = payload.get("execution_allowed")
                if advisory is False or exec_allowed is True:
                    safe = False

        if not safe:
            eval_res["status"] = "FAIL"
            eval_res["release_recommendation"] = "Return to Engineering"
            eval_res["overall_score"] = 0.0
            eval_res["blockers"].append("Safety Gate Violated: Advisory boundary bypass detected in constituent payloads.")

        # Format reports
        report_json = self._to_json(eval_res, consistency_res, audit_res)
        report_md = self._to_markdown(eval_res, consistency_res, audit_res)
        report_console = self._to_console(eval_res, consistency_res, audit_res)

        return {
            "status": eval_res["status"],
            "overall_score": eval_res["overall_score"],
            "release_recommendation": eval_res["release_recommendation"],
            "scorecard": eval_res["scorecard"],
            "blockers": eval_res["blockers"],
            "warnings": eval_res["warnings"],
            "consistency": consistency_res,
            "audit": audit_res,
            "json_report": report_json,
            "markdown_report": report_md,
            "console_report": report_console,
        }

    def _to_json(self, ev: dict[str, Any], cn: dict[str, Any], au: dict[str, Any]) -> str:
        return json.dumps({
            "evaluation": ev,
            "consistency": cn,
            "audit": au,
        }, indent=2)

    def _to_markdown(self, ev: dict[str, Any], cn: dict[str, Any], au: dict[str, Any]) -> str:
        md = []
        md.append("# RC1 Platform Certification Report\n")
        md.append(f"**Final Status**: {ev['status']}")
        md.append(f"**Overall Score**: {ev['overall_score']:.1f}/100")
        md.append(f"**Release Recommendation**: {ev['release_recommendation']}\n")

        md.append("## Production Readiness Scorecard")
        for key, val in ev["scorecard"].items():
            md.append(f"- **{key}**: {val}")
        md.append("")

        md.append("## Consistency Check Summary")
        md.append(f"- Status: {cn['status']}")
        for detail in cn["details"]:
            md.append(f"- {detail}")
        md.append("")

        md.append("## Runtime Audit Summary")
        md.append(f"- Status: {au['status']}")
        if au["errors"]:
            md.append("### Audit Errors")
            for err in au["errors"]:
                md.append(f"- [!] {err}")
        if au["warnings"]:
            md.append("### Audit Warnings")
            for warn in au["warnings"]:
                md.append(f"- [w] {warn}")
        md.append("")

        if ev["blockers"]:
            md.append("## Critical Staging Blockers")
            for b in ev["blockers"]:
                md.append(f"- {b}")
            md.append("")

        return "\n".join(md)

    def _to_console(self, ev: dict[str, Any], cn: dict[str, Any], au: dict[str, Any]) -> str:
        lines = []
        lines.append("==================================================")
        lines.append("RC1 PLATFORM CERTIFICATION SUMMARY")
        lines.append("==================================================")
        lines.append(f"Status        : {ev['status']}")
        lines.append(f"Score         : {ev['overall_score']:.1f}")
        lines.append(f"Recommendation: {ev['release_recommendation']}")
        lines.append("")
        lines.append("Scorecard Dimensions:")
        for key, val in ev["scorecard"].items():
            lines.append(f"  - {key:<22}: {val}")
        lines.append("")
        lines.append(f"Consistency Status: {cn['status']}")
        lines.append(f"Runtime Audit Status: {au['status']}")
        if ev["blockers"]:
            lines.append("")
            lines.append("Critical Blockers:")
            for b in ev["blockers"]:
                lines.append(f"  [!] {b}")
        if ev["warnings"]:
            lines.append("")
            lines.append("Warnings & Notices:")
            for w in ev["warnings"]:
                lines.append(f"  [w] {w}")
        lines.append("==================================================")
        return "\n".join(lines)
