from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.portfolio.utils import advisory_response, safe_float
from backend.reporting.executive_recommendations import ExecutiveRecommendations
from backend.reporting.executive_summary_formatter import ExecutiveSummaryFormatter


class ExecutiveDecisionBrief:
    """Aggregates advisory metrics, risks, and health reports into a unified presentation layer."""

    def __init__(
        self,
        *,
        recommendations: ExecutiveRecommendations | None = None,
        formatter: ExecutiveSummaryFormatter | None = None,
    ) -> None:
        self.recommendations = recommendations or ExecutiveRecommendations()
        self.formatter = formatter or ExecutiveSummaryFormatter()

    def generate_brief(
        self,
        *,
        market_intelligence: Mapping[str, Any] | None = None,
        adaptive_strategy_intelligence: Mapping[str, Any] | None = None,
        portfolio_construction: Mapping[str, Any] | None = None,
        optimizer: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            # 1. Enforce validation check: if portfolio construction or committee is missing, fail closed.
            if not portfolio_construction or not committee:
                return self._fail_closed(["portfolio_construction_or_committee_data_unavailable"])

            pc_status = portfolio_construction.get("status", "DATA UNAVAILABLE")
            comm_status = committee.get("status", "DATA UNAVAILABLE")
            if pc_status == "DATA UNAVAILABLE" or comm_status == "DATA UNAVAILABLE":
                return self._fail_closed(["constituent_payloads_contain_data_unavailable"])

            # 2. Extract constituent metrics
            # Market Regime
            regime = "Unknown"
            if market_intelligence and isinstance(market_intelligence, Mapping):
                regime = market_intelligence.get("regime", market_intelligence.get("market_regime", "Unknown"))
            elif portfolio_construction and isinstance(portfolio_construction, Mapping):
                # Fallback to portfolio_resilience section
                pr = portfolio_construction.get("portfolio_resilience", {})
                if isinstance(pr, Mapping):
                    regime = pr.get("market_regime", "Unknown")

            # Decision Confidence
            conf = 80.0
            if decision_confidence and isinstance(decision_confidence, Mapping):
                conf = safe_float(decision_confidence.get("confidence", decision_confidence.get("confidence_score", 80.0)))

            # Broker Health overall status & details map
            bh_status = "UNKNOWN"
            bh_details = {}
            if broker_health and isinstance(broker_health, Mapping):
                bh_status = str(broker_health.get("health", broker_health.get("broker_health", "UNKNOWN"))).upper()
                # Parse brokers details if available
                brokers_map = broker_health.get("brokers", {})
                if isinstance(brokers_map, Mapping) and brokers_map:
                    for name, details in brokers_map.items():
                        bh_details[name.upper()] = str(details.get("health", details.get("status", "UNKNOWN"))).upper()
                else:
                    # Try flat list
                    broker_name = str(broker_health.get("broker", "UNKNOWN")).upper()
                    if broker_name != "UNKNOWN":
                        bh_details[broker_name] = bh_status

            # Runtime Health
            rh_status = "UNKNOWN"
            if runtime_health and isinstance(runtime_health, Mapping):
                rh_status = str(runtime_health.get("status", runtime_health.get("runtime_health", runtime_health.get("overall_operational_health", "UNKNOWN")))).upper()

            # Portfolio Quality
            quality = safe_float(portfolio_construction.get("portfolio_quality", 0.0))

            # Preferred Portfolio Scenario
            preferred_scenario = "Balanced"
            if optimizer and isinstance(optimizer, Mapping):
                preferred_scenario = optimizer.get("best_overall", "Balanced")

            # Investment Committee recommendation & vote
            comm_rec = committee.get("overall_recommendation", "REJECT")
            comm_vote = committee.get("committee_vote", {"approve": 0, "conditional": 0, "reject": 6})

            # Derive Overall Status
            overall_status = "GREEN"
            any_broker_red = any(h == "RED" for h in bh_details.values())
            any_broker_amber = any(h in {"AMBER", "FAIL"} for h in bh_details.values())

            if comm_rec == "REJECT" or rh_status == "RED" or bh_status == "RED" or any_broker_red:
                overall_status = "RED"
            elif comm_rec in {"CONDITIONAL", "NEEDS_REVIEW"} or rh_status in {"AMBER", "DEGRADED"} or bh_status in {"AMBER", "FAIL"} or any_broker_amber:
                overall_status = "AMBER"
            elif pc_status == "DEFENSIVE":
                overall_status = "DEFENSIVE"
            elif pc_status == "PARTIAL":
                overall_status = "AMBER"

            # 3. Consolidate Recommendations and Warnings
            top_risks = self.recommendations.extract_risks(
                portfolio_construction=portfolio_construction,
                broker_health=broker_health,
                runtime_health=runtime_health,
                decision_confidence=decision_confidence,
                committee=committee,
            )
            top_opps = self.recommendations.extract_opportunities(
                portfolio_construction=portfolio_construction,
                optimizer=optimizer,
            )
            actions = self.recommendations.generate_recommended_actions(
                overall_status=overall_status,
                portfolio_construction=portfolio_construction,
                committee=committee,
                broker_health=broker_health,
            )
            warnings = self.recommendations.generate_operational_warnings(
                broker_health=broker_health,
                runtime_health=runtime_health,
                decision_confidence=decision_confidence,
            )
            decision_intel = self.recommendations.generate_decision_intelligence(
                portfolio_construction=portfolio_construction,
                optimizer=optimizer,
                committee=committee,
                decision_confidence=decision_confidence,
                broker_health=broker_health,
                runtime_health=runtime_health,
            )

            # Build return brief payload
            res = advisory_response(
                "OK",
                overall_status=overall_status,
                market_regime=regime,
                decision_confidence=conf,
                broker_health=bh_status,
                broker_health_details=bh_details,
                runtime_health=rh_status,
                portfolio_quality=quality,
                preferred_portfolio=preferred_scenario,
                investment_committee=comm_rec,
                committee_vote=comm_vote,
                top_opportunities=top_opps,
                top_risks=top_risks,
                recommended_actions=actions,
                operational_warnings=warnings,
                decision_intelligence=decision_intel,
                execution_status={
                    "execution_authority": "NOT GRANTED",
                    "live_trading": "BLOCKED",
                    "broker_execution": "DISARMED",
                },
                integration={
                    "phase157a_consumed": isinstance(adaptive_strategy_intelligence, Mapping),
                    "phase157b_consumed": True,
                    "phase157c_consumed": isinstance(optimizer, Mapping),
                    "phase158a_consumed": True,
                    "decision_confidence_consumed": isinstance(decision_confidence, Mapping),
                    "broker_health_consumed": isinstance(broker_health, Mapping),
                    "runtime_health_consumed": isinstance(runtime_health, Mapping),
                },
                live_trading_blocked=True,
                broker_execution_armed=False,
                reasons=["briefing_payload_compiled"],
            )
            return res

        except Exception as exc:  # noqa: BLE001 - must fail closed
            return self._fail_closed([f"briefing_exception:{exc.__class__.__name__}"])

    @staticmethod
    def _fail_closed(reasons: list[str]) -> dict[str, Any]:
        return advisory_response(
            "DATA UNAVAILABLE",
            overall_status="RED",
            market_regime="Unknown",
            decision_confidence=0.0,
            broker_health="DATA UNAVAILABLE",
            broker_health_details={},
            runtime_health="DATA UNAVAILABLE",
            portfolio_quality=0.0,
            preferred_portfolio="DATA UNAVAILABLE",
            investment_committee="REJECT",
            committee_vote={"approve": 0, "conditional": 0, "reject": 6},
            top_opportunities=["None identified due to data unavailability."],
            top_risks=[f"Data aggregation failed: {', '.join(reasons)}."],
            recommended_actions=["Remediate system integration and metrics pipelines."],
            operational_warnings=[f"CRITICAL: Executive Brief is running in fail-closed state. Reasons: {', '.join(reasons)}."],
            execution_status={
                "execution_authority": "NOT GRANTED",
                "live_trading": "BLOCKED",
                "broker_execution": "DISARMED",
            },
            integration={
                "phase157a_consumed": False,
                "phase157b_consumed": False,
                "phase157c_consumed": False,
                "phase158a_consumed": False,
                "decision_confidence_consumed": False,
                "broker_health_consumed": False,
                "runtime_health_consumed": False,
            },
            live_trading_blocked=True,
            broker_execution_armed=False,
            reasons=reasons,
        )
