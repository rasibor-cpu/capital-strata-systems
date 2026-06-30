from __future__ import annotations

from typing import Any, Mapping


class AdaptivePortfolioManagerError(RuntimeError):
    """Fail-closed exception for adaptive portfolio recommendations."""


class AdaptivePortfolioManager:
    """
    Advisory-only portfolio recommendation aggregator.

    This class synthesizes existing portfolio intelligence, capital rotation,
    runtime supervisor, and risk context evidence. It never executes trades or
    mutates portfolio/risk state.
    """

    def evaluate(
        self,
        portfolio_intelligence: Mapping[str, Any] | None,
        capital_rotation: Mapping[str, Any] | None,
        supervisor_state: Mapping[str, Any] | None,
        risk_context: Mapping[str, Any] | None = None,
        governance_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(portfolio_intelligence, Mapping):
            return self._fail_closed("portfolio_intelligence_unavailable")
        if not isinstance(capital_rotation, Mapping):
            return self._fail_closed("capital_rotation_unavailable")
        if not isinstance(supervisor_state, Mapping):
            return self._fail_closed("supervisor_state_unavailable")

        primary_drivers: list[str] = []
        risk_flags: list[str] = []
        recommended_actions: list[str] = []

        pi_status = str(portfolio_intelligence.get("status", "")).upper()
        cr_status = str(capital_rotation.get("status", "")).upper()
        supervisor_status = str(supervisor_state.get("status", "")).upper()
        if supervisor_status in {"", "OFFLINE", "ERROR", "FAILED", "RED", "HALTED", "PAUSED"}:
            return self._fail_closed(f"supervisor_status_{supervisor_status or 'missing'}")
        if "LIMITED" in {pi_status, cr_status}:
            return self._limited_no_exposure(portfolio_intelligence, capital_rotation)
        if pi_status != "OK":
            return self._fail_closed("portfolio_intelligence_not_ok")
        if cr_status != "OK":
            return self._fail_closed("capital_rotation_not_ok")

        health_score = self._bounded(portfolio_intelligence.get("intelligence_score"), 0.0, 100.0)
        portfolio_status = str(portfolio_intelligence.get("portfolio_status", "")).upper()
        metrics = portfolio_intelligence.get("metrics", {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        max_drawdown = self._float(metrics.get("max_drawdown"))
        concentration = max(
            self._float(metrics.get("largest_symbol_concentration")),
            self._float(metrics.get("largest_asset_class_concentration")),
        )

        capital_rotation_action = self._capital_rotation_action(capital_rotation, portfolio_status)
        critical_flags = self._critical_flags(risk_context, governance_context)
        risk_flags.extend(critical_flags)

        if health_score >= 80.0:
            primary_drivers.append("Portfolio intelligence is healthy.")
        elif health_score >= 60.0:
            primary_drivers.append("Portfolio intelligence is mixed.")
            risk_flags.append("portfolio_health_watch")
        else:
            primary_drivers.append("Portfolio intelligence is weak.")
            risk_flags.append("portfolio_health_defensive")

        if max_drawdown > 0.12:
            risk_flags.append("drawdown_high")
        if concentration > 0.55:
            risk_flags.append("concentration_excessive")
        if capital_rotation_action == "DEFENSIVE":
            risk_flags.append("capital_rotation_defensive")

        if critical_flags:
            recommendation = "PAUSE_NEW_TRADES"
            committee_status = "RED"
            recommended_actions.append("Pause new trade initiation until critical safety flags clear.")
        elif health_score < 60.0 or max_drawdown > 0.12 or concentration > 0.55:
            recommendation = "REDUCE_RISK"
            committee_status = "AMBER" if health_score >= 45.0 else "RED"
            recommended_actions.append("Reduce risk exposure through advisory review before adding capital.")
        elif capital_rotation_action == "OPPORTUNISTIC" and not risk_flags:
            recommendation = "INCREASE_RISK"
            committee_status = "GREEN"
            recommended_actions.append("Consider selective risk increase subject to existing gates.")
        else:
            recommendation = "MAINTAIN"
            committee_status = "GREEN" if not risk_flags else "AMBER"
            recommended_actions.append("Maintain current posture and continue monitoring.")

        conflicts = self._conflict_count(portfolio_status, capital_rotation_action, risk_flags)
        confidence = int(round(health_score))
        confidence -= min(30, conflicts * 10)
        confidence -= 25 if committee_status == "RED" else 0
        confidence -= 10 if committee_status == "AMBER" else 0
        if critical_flags:
            confidence = min(confidence, 30)
        confidence = int(self._bounded(confidence, 0.0, 100.0))

        return {
            "status": "OK",
            "adaptive_recommendation": recommendation,
            "confidence": confidence,
            "portfolio_health_score": round(health_score, 6),
            "capital_rotation_action": capital_rotation_action,
            "risk_committee_status": committee_status,
            "primary_drivers": primary_drivers,
            "risk_flags": sorted(set(risk_flags)),
            "recommended_actions": recommended_actions,
            "advisory_only": True,
        }

    @staticmethod
    def _capital_rotation_action(capital_rotation: Mapping[str, Any], portfolio_status: str) -> str:
        allocations = capital_rotation.get("target_allocations", {})
        allocations = allocations if isinstance(allocations, Mapping) else {}
        cash = AdaptivePortfolioManager._float(allocations.get("CASH"))
        recommendation = str(capital_rotation.get("recommendation", "")).upper()
        if portfolio_status == "DEFENSIVE" or cash >= 35.0 or recommendation == "NO_ACTION":
            return "DEFENSIVE"
        if cash <= 10.0 and recommendation == "ROTATE_CAPITAL":
            return "OPPORTUNISTIC"
        return "BALANCED"

    @staticmethod
    def _critical_flags(*contexts: Mapping[str, Any] | None) -> list[str]:
        flags: list[str] = []
        for context in contexts:
            if not isinstance(context, Mapping):
                continue
            status = str(context.get("status", context.get("risk_status", ""))).upper()
            if status == "RED":
                flags.append("risk_context_red")
            for key in ("critical_flags", "risk_flags", "safety_flags"):
                raw_flags = context.get(key, [])
                if isinstance(raw_flags, str):
                    raw_flags = [raw_flags]
                if isinstance(raw_flags, list):
                    for item in raw_flags:
                        text = str(item).strip()
                        if text and text.upper() in {"RED", "CRITICAL", "HALT", "PAUSE_NEW_TRADES"}:
                            flags.append(f"{key}_critical")
                        elif text:
                            flags.append(text)
        return sorted(set(flags))

    @staticmethod
    def _conflict_count(portfolio_status: str, capital_rotation_action: str, risk_flags: list[str]) -> int:
        conflicts = 0
        if portfolio_status == "HEALTHY" and capital_rotation_action == "DEFENSIVE":
            conflicts += 1
        if portfolio_status == "DEFENSIVE" and capital_rotation_action == "OPPORTUNISTIC":
            conflicts += 2
        if risk_flags:
            conflicts += 1
        return conflicts

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _bounded(value: Any, low: float, high: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = low
        return max(low, min(high, numeric))

    @staticmethod
    def _fail_closed(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "adaptive_recommendation": "PAUSE_NEW_TRADES",
            "confidence": 25,
            "portfolio_health_score": None,
            "capital_rotation_action": None,
            "risk_committee_status": "RED",
            "primary_drivers": [],
            "risk_flags": [reason],
            "recommended_actions": ["Do not increase risk until portfolio evidence is available and valid."],
            "advisory_only": True,
        }

    @staticmethod
    def _limited_no_exposure(
        portfolio_intelligence: Mapping[str, Any],
        capital_rotation: Mapping[str, Any],
    ) -> dict[str, Any]:
        reasons: list[str] = []
        for payload in (portfolio_intelligence, capital_rotation):
            for key in ("explainability", "reasons"):
                values = payload.get(key, [])
                if isinstance(values, str):
                    values = [values]
                if isinstance(values, list):
                    reasons.extend(str(item) for item in values if str(item).strip())
        return {
            "status": "LIMITED",
            "adaptive_recommendation": "AWAIT_PORTFOLIO_BUILD",
            "confidence": 60,
            "portfolio_health_score": portfolio_intelligence.get("intelligence_score", 50.0),
            "capital_rotation_action": "HOLD_CURRENT",
            "risk_committee_status": "GREEN",
            "primary_drivers": ["Runtime is connected but there is no current exposure."],
            "risk_flags": [],
            "recommended_actions": ["Continue paper/advisory monitoring until positions are present."],
            "reasons": sorted(set(reasons or ["No current exposure."])),
            "advisory_only": True,
        }
