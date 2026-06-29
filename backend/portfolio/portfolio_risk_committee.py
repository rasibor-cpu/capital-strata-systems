from __future__ import annotations

from typing import Any, Mapping


class PortfolioRiskCommitteeError(RuntimeError):
    """Fail-closed exception for portfolio risk committee review."""


class PortfolioRiskCommittee:
    """Advisory-only committee synthesis for portfolio-level risk posture."""

    def review(
        self,
        portfolio_intelligence: Mapping[str, Any] | None,
        capital_rotation: Mapping[str, Any] | None,
        adaptive_portfolio: Mapping[str, Any] | None,
        attribution: Mapping[str, Any] | None,
        regime_allocation: Mapping[str, Any] | None,
        supervisor_flags: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        inputs = {
            "portfolio_intelligence": portfolio_intelligence,
            "capital_rotation": capital_rotation,
            "adaptive_portfolio": adaptive_portfolio,
            "attribution": attribution,
            "regime_allocation": regime_allocation,
        }
        for name, payload in inputs.items():
            if not isinstance(payload, Mapping):
                return self._pause(f"{name}_unavailable")

        concerns: list[str] = []
        approvals: list[str] = []
        required_actions: list[str] = []

        critical = self._critical_supervisor(supervisor_flags)
        if critical:
            concerns.extend(critical)

        adaptive_recommendation = str(adaptive_portfolio.get("adaptive_recommendation", "")).upper()
        adaptive_status = str(adaptive_portfolio.get("risk_committee_status", "")).upper()
        pi_status = str(portfolio_intelligence.get("portfolio_status", "")).upper()
        attribution_recommendation = str(attribution.get("recommendation", "")).upper()
        allocation_bias = str(regime_allocation.get("allocation_bias", "")).upper()

        for name, payload in inputs.items():
            if str(payload.get("status", "OK")).upper() == "DATA UNAVAILABLE":
                concerns.append(f"{name}_data_unavailable")

        if adaptive_recommendation == "PAUSE_NEW_TRADES" or adaptive_status == "RED" or concerns:
            required_actions.append("Pause new trade initiation until committee concerns clear.")
            return {
                "status": "OK",
                "committee_decision": "PAUSE_NEW_TRADES",
                "committee_status": "RED",
                "confidence": min(30, int(adaptive_portfolio.get("confidence", 25) or 25)),
                "summary": "Risk committee is red; advisory posture is pause new trades.",
                "approvals": approvals,
                "concerns": sorted(set(concerns or ["adaptive_portfolio_red"])),
                "required_actions": required_actions,
                "advisory_only": True,
            }

        confidence = int(adaptive_portfolio.get("confidence", 50) or 50)
        if pi_status == "HEALTHY":
            approvals.append("Portfolio intelligence is healthy.")
        elif pi_status == "WATCH":
            concerns.append("portfolio_health_watch")
            confidence -= 10
        else:
            concerns.append("portfolio_health_defensive")
            confidence -= 20

        if attribution_recommendation in {"REVIEW_DETRACTORS", "PAUSE_UNDERPERFORMERS"}:
            concerns.append("weak_attribution")
            confidence -= 15
        else:
            approvals.append("Attribution does not require pausing underperformers.")

        if allocation_bias == "DEFENSIVE" and adaptive_recommendation == "INCREASE_RISK":
            concerns.append("regime_allocation_conflicts_with_risk_increase")
            confidence -= 20

        if adaptive_recommendation == "INCREASE_RISK" and concerns:
            decision = "REJECT_RISK_INCREASE"
            status = "AMBER"
            required_actions.append("Review concerns before increasing portfolio risk.")
        elif concerns:
            decision = "APPROVE_WITH_CAUTION"
            status = "AMBER"
            required_actions.append("Proceed advisory-only with caution and monitor concerns.")
        else:
            decision = "APPROVE_ADVISORY"
            status = "GREEN"
            required_actions.append("Continue advisory monitoring under existing governance gates.")

        confidence = max(0, min(100, confidence))
        return {
            "status": "OK",
            "committee_decision": decision,
            "committee_status": status,
            "confidence": confidence,
            "summary": f"Risk committee status {status}; decision {decision}.",
            "approvals": approvals,
            "concerns": sorted(set(concerns)),
            "required_actions": required_actions,
            "advisory_only": True,
        }

    @staticmethod
    def _critical_supervisor(supervisor_flags: Mapping[str, Any] | None) -> list[str]:
        if not isinstance(supervisor_flags, Mapping):
            return []
        status = str(supervisor_flags.get("status", "")).upper()
        if status in {"RED", "HALTED", "PAUSED", "FAILED", "ERROR"}:
            return [f"supervisor_{status.lower()}"]
        flags = supervisor_flags.get("critical_flags", [])
        if isinstance(flags, str):
            flags = [flags]
        if isinstance(flags, list):
            return [str(flag).strip() for flag in flags if str(flag).strip()]
        return []

    @staticmethod
    def _pause(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "committee_decision": "PAUSE_NEW_TRADES",
            "committee_status": "RED",
            "confidence": 25,
            "summary": "Risk committee input is unavailable; advisory posture is pause new trades.",
            "approvals": [],
            "concerns": [reason],
            "required_actions": ["Do not increase risk until committee evidence is available and valid."],
            "advisory_only": True,
        }
