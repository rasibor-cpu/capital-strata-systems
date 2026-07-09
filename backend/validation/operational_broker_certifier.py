from __future__ import annotations

import json
import time
from typing import Any, Mapping

from backend.validation.broker_operational_scorecard import BrokerOperationalScorecard
from backend.validation.broker_operational_recommendations import BrokerOperationalRecommendations


class OperationalBrokerCertifier:
    """The authoritative broker certification orchestrator. Consolidates diagnostic readiness evidence."""

    def __init__(
        self,
        *,
        scorecard: BrokerOperationalScorecard | None = None,
        recommender: BrokerOperationalRecommendations | None = None,
    ) -> None:
        self.scorecard = scorecard or BrokerOperationalScorecard()
        self.recommender = recommender or BrokerOperationalRecommendations()

    def certify_broker(
        self,
        broker_name: str,
        *,
        mode: str = "live",
        phase156b_connectivity: Mapping[str, Any] | None = None,
        previous_history: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        history = previous_history or {}

        # 1. Harvest evidence inputs from Phase 156B connectivity or defaults
        conn = phase156b_connectivity or {}
        
        credentials = "PASS" if conn.get("phase156a") == "GREEN" else "FAIL"
        bootstrap = "PASS" if conn.get("authentication") == "PASS" or conn.get("latency", {}).get("authentication_ms") is not None else "FAIL"
        authentication = conn.get("authentication", "FAIL")
        account_access = conn.get("account", "FAIL")
        market_data = conn.get("market_data", "FAIL")
        latency = conn.get("latency_status", "RED")
        health = "GREEN" if conn.get("latency_status") != "RED" else "AMBER"
        availability_reliability = "GREEN" if conn.get("latency_status") in {"GREEN", "AMBER"} else "FAIL"
        
        # Safety / Firewall
        sf = conn.get("stage_results", {}).get("execution_firewall", {})
        firewall = sf.get("status", "PASS")
        execution_boundary = "PASS" if sf.get("details", {}).get("execution_boundary_active") is True else "FAIL"
        safety = "GREEN" if firewall == "PASS" and execution_boundary == "PASS" else "RED"

        evidence = {
            "credentials": credentials,
            "bootstrap": bootstrap,
            "authentication": authentication,
            "account_access": account_access,
            "market_data": market_data,
            "latency": latency,
            "health": health,
            "availability_reliability": availability_reliability,
            "safety": safety,
        }

        # 2. Compute scorecard and derived ratings
        score_res = self.scorecard.compute_score(evidence)
        overall_score = score_res["overall_score"]
        
        # Determine overall_state rating based on the worst dimensional readiness rating (excluding safety)
        ratings = [score_res["technical_readiness"], score_res["operational_readiness"], score_res["health_readiness"]]
        if "RED" in ratings:
            overall_state = "RED"
        elif "AMBER" in ratings:
            overall_state = "AMBER"
        else:
            overall_state = "GREEN"

        # Determine blockers list
        blockers = []
        for key, val in evidence.items():
            if val in {"FAIL", "RED"}:
                blockers.append(f"{key}_readiness_failed")

        # 3. Compute recommendations
        rec_res = self.recommender.evaluate_recommendations(
            overall_state=overall_state,
            safety_rating=score_res["safety_readiness"],
            scorecard=score_res,
            blockers=blockers,
        )

        # 4. Strict Advisory Boundary Checks
        advisory_only = True
        execution_allowed = False
        live_trading_blocked = True
        broker_execution_armed = False

        # Override recommendations if safety violation is detected
        if (
            conn.get("execution_allowed") is True
            or conn.get("advisory_only") is False
            or conn.get("live_trading_blocked") is False
            or conn.get("broker_execution_armed") is True
        ):
            rec_res["overall_recommendation"] = "NO_GO"
            overall_state = "RED"
            score_res["safety_readiness"] = "RED"
            score_res["production_readiness"] = "NOT_READY"
            blockers.append("Safety Gate Violated: Advisory boundary bypass detected in inputs.")

        # Harvest historical updates
        prev_score = history.get("overall_score")
        prev_state = history.get("overall_state")
        score_delta = None
        if prev_score is not None:
            score_delta = round(overall_score - float(prev_score), 1)
        state_changed = False
        if prev_state is not None and prev_state != overall_state:
            state_changed = True

        # Render evidence block list
        evidence_block = []
        evidence_block.append("✓ Credentials validated" if credentials == "PASS" else "✗ Credentials failed")
        evidence_block.append("✓ Bootstrap successful" if bootstrap == "PASS" else "✗ Bootstrap failed")
        evidence_block.append("✓ Authentication passed" if authentication == "PASS" else "✗ Authentication failed")
        evidence_block.append("✓ Account access passed" if account_access == "PASS" else "✗ Account access failed")
        evidence_block.append("✓ Market data passed" if market_data == "PASS" else "✗ Market data failed")
        evidence_block.append("✓ Firewall passed" if firewall == "PASS" else "✗ Firewall failed")
        evidence_block.append("✓ Execution boundary verified" if execution_boundary == "PASS" else "✗ Execution boundary failed")
        evidence_block.append("✓ Advisory mode enforced" if advisory_only else "✗ Advisory mode bypassed")
        if latency == "AMBER":
            evidence_block.append("⚠ Elevated latency")
        if health == "AMBER":
            evidence_block.append("⚠ Health degradation")

        report = {
            "schema_version": "rc1b.broker_certification.v1",
            "certification_timestamp": timestamp,
            "broker_name": broker_name.upper(),
            "broker_mode": mode,
            "technical_readiness": score_res["technical_readiness"],
            "operational_readiness": score_res["operational_readiness"],
            "health_readiness": score_res["health_readiness"],
            "safety_readiness": score_res["safety_readiness"],
            "production_readiness": score_res["production_readiness"],
            "overall_score": overall_score,
            "overall_state": overall_state,
            "overall_recommendation": rec_res["overall_recommendation"],
            "credentials": credentials,
            "bootstrap": bootstrap,
            "authentication": authentication,
            "account_access": account_access,
            "market_data": market_data,
            "latency": latency,
            "health": health,
            "availability": "PASS" if availability_reliability == "GREEN" else "FAIL",
            "reliability": "PASS" if availability_reliability == "GREEN" else "FAIL",
            "firewall": firewall,
            "execution_boundary": execution_boundary,
            "evidence": evidence_block,
            "remaining_blockers": blockers,
            "recommendations": rec_res["recommendations"],
            "next_recommended_action": rec_res["next_recommended_action"],
            "previous_score": prev_score if prev_score is not None else "UNKNOWN",
            "score_delta": score_delta if score_delta is not None else "UNKNOWN",
            "previous_state": prev_state if prev_state is not None else "UNKNOWN",
            "state_changed": state_changed,
            "advisory_only": advisory_only,
            "execution_allowed": execution_allowed,
            "live_trading_blocked": live_trading_blocked,
            "broker_execution_armed": broker_execution_armed,
        }

        # Build presentation structures
        report_json = json.dumps(report, indent=2, sort_keys=True)
        report_md = self._to_markdown(report)
        report_console = self._to_console(report)

        return {
            "report": report,
            "json": report_json,
            "markdown": report_md,
            "console": report_console,
        }

    def _to_markdown(self, r: dict[str, Any]) -> str:
        md = []
        md.append(f"# Operational Broker Certification Report - {r['broker_name']}\n")
        md.append(f"**Overall Recommendation**: **{r['overall_recommendation']}**")
        md.append(f"**Score**: {r['overall_score']:.1f}/100 | State: {r['overall_state']}")
        md.append(f"**Production Readiness**: {r['production_readiness']}\n")
        
        md.append("## Readiness Dimensions")
        md.append(f"- **Technical Readiness**: {r['technical_readiness']}")
        md.append(f"- **Operational Readiness**: {r['operational_readiness']}")
        md.append(f"- **Health Readiness**: {r['health_readiness']}")
        md.append(f"- **Safety Readiness**: {r['safety_readiness']}\n")

        md.append("## Evidence Summary")
        for ev in r["evidence"]:
            md.append(f"- {ev}")
        md.append("")

        if r["remaining_blockers"]:
            md.append("## Remaining Blockers")
            for b in r["remaining_blockers"]:
                md.append(f"- [!] {b}")
            md.append("")

        md.append("## Recommended Actions")
        for rec in r["recommendations"]:
            md.append(f"- {rec}")
        md.append(f"\n**Next Recommended Action**: {r['next_recommended_action']}")

        return "\n".join(md)

    def _to_console(self, r: dict[str, Any]) -> str:
        lines = []
        lines.append("==================================================")
        lines.append(f"OPERATIONAL BROKER CERTIFICATION: {r['broker_name']}")
        lines.append("==================================================")
        lines.append(f"Overall Score    : {r['overall_score']:.1f}")
        lines.append(f"Recommendation   : {r['overall_recommendation']}")
        lines.append(f"State            : {r['overall_state']}")
        lines.append(f"Prod Readiness   : {r['production_readiness']}")
        lines.append("")
        lines.append("Evidence Logs:")
        for ev in r["evidence"]:
            lines.append(f"  {ev}")
        if r["remaining_blockers"]:
            lines.append("")
            lines.append("Remaining Blockers:")
            for b in r["remaining_blockers"]:
                lines.append(f"  [!] {b}")
        lines.append("")
        lines.append(f"Next Action: {r['next_recommended_action']}")
        lines.append("==================================================")
        return "\n".join(lines)
