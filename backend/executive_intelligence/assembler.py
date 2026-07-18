"""ExecutiveMorningBrief assembler — canonical aggregation engine."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.executive_intelligence.actions import generate_executive_actions
from backend.executive_intelligence.constants import (
    ARCHIVE_SCHEMA_VERSION,
    BRIEF_SCHEMA_VERSION,
    BRIEFING_TYPE,
    MARKET_SESSION_DEFAULT,
    SAFETY_LOCKS,
)
from backend.executive_intelligence.scoring import score_all_kpis
from backend.executive_intelligence.utils import (
    as_mapping,
    clamp01,
    confidence_band,
    normalize_freshness,
    posture_from_runtime,
    safe_str,
    utc_now_iso,
    worst_freshness,
)


class ExecutiveMorningBriefAssembler:
    """Aggregate CSS executive evidence into css.executive_morning_brief.v1."""

    def assemble(
        self,
        evidence: Mapping[str, Any],
        *,
        report_date: str | None = None,
        reporting_window_start_utc: str | None = None,
        reporting_window_end_utc: str | None = None,
        report_version: str = "v001",
    ) -> dict[str, Any]:
        generated_at = utc_now_iso()
        report_date = report_date or generated_at[:10]
        window_end = reporting_window_end_utc or generated_at
        if reporting_window_start_utc:
            window_start = reporting_window_start_utc
        else:
            # Default overnight window: prior 18h (label only; does not invent market data)
            try:
                end_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError:
                end_dt = datetime.now(timezone.utc)
            window_start = (end_dt - timedelta(hours=18)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        panels = {
            "executive_decision": self._panel_executive_decision(evidence),
            "operational_health": self._panel_operational_health(evidence),
            "market_intelligence": self._panel_market(evidence),
            "trading_intelligence": self._panel_trading(evidence),
            "learning": self._panel_learning(evidence),
        }

        # Actions need panels first; inject after KPI scoring base panels
        kpis = score_all_kpis(evidence, panels)
        actions = generate_executive_actions(evidence=evidence, panels=panels, kpis=kpis)
        panels["executive_decision"]["executive_actions"] = actions
        panels["executive_decision"]["recommended_actions"] = actions
        # Re-score recommendation quality with actions present
        kpis = score_all_kpis(evidence, panels)

        runtime = as_mapping(evidence.get("runtime_health"))
        broker = as_mapping(evidence.get("broker_health"))
        data_freshness = worst_freshness(
            normalize_freshness(runtime.get("freshness", "UNAVAILABLE")),
            normalize_freshness(broker.get("freshness", "UNAVAILABLE")),
            normalize_freshness(as_mapping(panels["market_intelligence"]).get("freshness", "UNAVAILABLE")),
            normalize_freshness(as_mapping(panels["trading_intelligence"]).get("freshness", "UNAVAILABLE")),
        )

        overall = self._overall_status(panels, runtime, broker)
        provenance = self._provenance(evidence, panels)

        brief: dict[str, Any] = {
            "schema_version": BRIEF_SCHEMA_VERSION,
            "archive_version": ARCHIVE_SCHEMA_VERSION,
            "briefing_type": BRIEFING_TYPE,
            "report_id": str(uuid.uuid4()),
            "report_date": report_date,
            "report_version": report_version,
            "version": report_version,
            "generated_at_utc": generated_at,
            "reporting_window_start_utc": window_start,
            "reporting_window_end_utc": window_end,
            "reporting_window_start": window_start,
            "reporting_window_end": window_end,
            "runtime_id": runtime.get("runtime_id") or evidence.get("runtime_id"),
            "supervisor_id": runtime.get("supervisor_id") or evidence.get("supervisor_id"),
            "state_hash": runtime.get("state_hash") or evidence.get("state_hash"),
            "decision_hash": evidence.get("decision_hash"),
            "market_session": evidence.get("market_session") or MARKET_SESSION_DEFAULT,
            "data_freshness_status": data_freshness,
            "report_status": "DRAFT",
            "is_current_for_date": False,
            "overall_status": overall,
            "executive_kpis": kpis,
            "panels": panels,
            "provenance": provenance,
            "validation": {"status": "PENDING", "validation_status": "PENDING"},
            "report_hash": None,
            "narratives": {},
            "diff_vs_previous": None,
            **SAFETY_LOCKS,
        }
        return brief

    def _panel_executive_decision(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        committee = as_mapping(evidence.get("committee"))
        confidence_raw = evidence.get("decision_confidence")
        if isinstance(confidence_raw, Mapping):
            conf = clamp01(confidence_raw.get("confidence", confidence_raw.get("confidence_score")))
        else:
            conf = clamp01(confidence_raw)
        market = as_mapping(evidence.get("market"))
        regime = market.get("regime_current") or market.get("regime") or "UNAVAILABLE"
        risks = evidence.get("top_risks") if isinstance(evidence.get("top_risks"), list) else []
        vetoes = committee.get("vetoes") or committee.get("committee_vetoes") or []
        if not isinstance(vetoes, list):
            vetoes = []
        freshness = worst_freshness(
            normalize_freshness(as_mapping(evidence.get("runtime_health")).get("freshness", "AGING")),
            normalize_freshness(as_mapping(evidence.get("broker_health")).get("freshness", "AGING")),
        )
        status = "GREEN"
        if conf is not None and conf < 0.6:
            status = "AMBER"
        if vetoes or posture_from_runtime(str(as_mapping(evidence.get("runtime_health")).get("status", ""))) == "RED":
            status = "RED"
        if conf is None and not committee and not risks:
            # still form panel; may be AMBER
            status = "AMBER"

        return {
            "panel_id": "executive_decision",
            "panel_status": status,
            "freshness": freshness,
            "confidence": conf,
            "confidence_band": confidence_band(conf),
            "confidence_status": "OK" if conf is not None else "DATA_UNAVAILABLE",
            "overall_decision_status": status,
            "market_regime_headline": safe_str(regime),
            "decision_confidence": conf,
            "committee_consensus": committee.get("overall_recommendation") or committee.get("consensus") or "UNAVAILABLE",
            "committee_vetoes": vetoes,
            "top_opportunities_headline": [],
            "top_risks": risks,
            "recommended_actions": [],
            "executive_actions": [],
            "operational_warnings": evidence.get("operational_warnings")
            if isinstance(evidence.get("operational_warnings"), list)
            else [],
            "decision_intelligence": as_mapping(evidence.get("explainability")),
            "unavailable_fields": [] if conf is not None else ["decision_confidence"],
        }

    def _panel_operational_health(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        runtime = as_mapping(evidence.get("runtime_health"))
        broker = as_mapping(evidence.get("broker_health"))
        alerts = as_mapping(evidence.get("alerts"))
        rh_fresh = normalize_freshness(runtime.get("freshness", "UNAVAILABLE" if not runtime else "AGING"))
        bh_fresh = normalize_freshness(broker.get("freshness", "UNAVAILABLE" if not broker else "AGING"))
        freshness = worst_freshness(rh_fresh, bh_fresh)
        rh_posture = posture_from_runtime(str(runtime.get("status", runtime.get("runtime_health", ""))))
        bh_status = str(broker.get("health", broker.get("status", "UNAVAILABLE"))).upper()
        panel_status = "GREEN"
        if rh_posture == "AMBER" or bh_status in {"AMBER", "DEGRADED", "LATENT"}:
            panel_status = "AMBER"
        if rh_posture in {"RED", "UNAVAILABLE"} or bh_status in {"RED", "OFFLINE", "FAILED", "UNAVAILABLE"} or freshness in {
            "STALE",
            "UNAVAILABLE",
        }:
            panel_status = "RED" if freshness != "UNAVAILABLE" or runtime or broker else "UNAVAILABLE"
        if not runtime and not broker:
            panel_status = "UNAVAILABLE"

        return {
            "panel_id": "operational_health",
            "panel_status": panel_status,
            "freshness": freshness,
            "runtime_health": runtime or {"status": "UNAVAILABLE", "freshness": "UNAVAILABLE"},
            "heartbeat_age_seconds": runtime.get("heartbeat_age_seconds"),
            "supervisor_id": runtime.get("supervisor_id"),
            "artifact_freshness": as_mapping(evidence.get("artifact_freshness")),
            "session_continuity": as_mapping(evidence.get("session_continuity")),
            "broker_operational_status": {
                "health": broker.get("health") or broker.get("status") or "UNAVAILABLE",
                "freshness": bh_fresh,
            },
            "broker_freshness": bh_fresh,
            "broker_venues": as_mapping(broker.get("brokers") or broker.get("venues")),
            "alert_summary": alerts or {"count": 0},
            "overnight_incidents": evidence.get("overnight_incidents")
            if isinstance(evidence.get("overnight_incidents"), list)
            else [],
            "unavailable_fields": [k for k, v in (("runtime_health", runtime), ("broker_health", broker)) if not v],
        }

    def _panel_market(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        market = as_mapping(evidence.get("market"))
        unavailable: list[str] = []
        if not market:
            return {
                "panel_id": "market_intelligence",
                "panel_status": "UNAVAILABLE",
                "freshness": "UNAVAILABLE",
                "overnight_market_summary": None,
                "regime_current": "UNAVAILABLE",
                "regime_transitions": [],
                "regime_implications": [],
                "intel_highlights": [],
                "confidence": None,
                "unavailable_fields": ["overnight_market_summary", "regime_current", "market"],
            }

        regime = market.get("regime_current") or market.get("regime")
        if market.get("overnight_market_summary") in (None, "", {}):
            unavailable.append("overnight_market_summary")
        freshness = normalize_freshness(market.get("freshness", "AGING"))
        conf = clamp01(market.get("confidence"))
        # Panel available if regime evidence exists (Phase 174); overnight rollup may be unavailable until 175
        panel_status = "GREEN" if regime else "UNAVAILABLE"
        if freshness == "AGING":
            panel_status = "AMBER" if regime else "UNAVAILABLE"
        if freshness in {"STALE", "UNAVAILABLE"}:
            panel_status = "UNAVAILABLE"

        return {
            "panel_id": "market_intelligence",
            "panel_status": panel_status,
            "freshness": freshness if regime else "UNAVAILABLE",
            "overnight_market_summary": market.get("overnight_market_summary"),
            "liquidity": as_mapping(market.get("overnight_market_summary")).get("liquidity_observations")
            if isinstance(market.get("overnight_market_summary"), Mapping)
            else market.get("liquidity"),
            "volatility": as_mapping(market.get("overnight_market_summary")).get("volatility_changes")
            if isinstance(market.get("overnight_market_summary"), Mapping)
            else market.get("volatility"),
            "spread": market.get("spread"),
            "regime_current": safe_str(regime),
            "regime": safe_str(regime),
            "prior_regime": (
                market.get("prior_regime")
                or as_mapping(as_mapping(market.get("overnight_full")).get("market_regime")).get("prior_regime")
                or "UNAVAILABLE"
            ),
            "regime_transitions": market.get("regime_transitions")
            if isinstance(market.get("regime_transitions"), list)
            else (
                as_mapping(market.get("overnight_market_summary")).get("relevant_regime_transitions")
                if isinstance(as_mapping(market.get("overnight_market_summary")).get("relevant_regime_transitions"), list)
                else []
            ),
            "regime_implications": market.get("regime_implications")
            if isinstance(market.get("regime_implications"), list)
            else [],
            "intel_highlights": market.get("intel_highlights") if isinstance(market.get("intel_highlights"), list) else [],
            "confidence": conf,
            "market_confidence": as_mapping(market.get("market_confidence"))
            if isinstance(market.get("market_confidence"), Mapping)
            else {"value": conf},
            "trading_implications": market.get("trading_implications")
            if isinstance(market.get("trading_implications"), list)
            else [],
            "asset_class_coverage": as_mapping(market.get("asset_class_coverage")),
            "unavailable_fields": unavailable,
        }

    def _panel_trading(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        portfolio = as_mapping(evidence.get("portfolio"))
        opps = evidence.get("opportunities") if isinstance(evidence.get("opportunities"), list) else []
        freshness = normalize_freshness(portfolio.get("freshness", "UNAVAILABLE" if not portfolio else "AGING"))
        if not portfolio and not opps:
            panel_status = "UNAVAILABLE"
        elif freshness == "STALE":
            panel_status = "AMBER"
        else:
            panel_status = "GREEN" if portfolio else "AMBER"

        ranked = []
        for item in opps[:10]:
            if isinstance(item, Mapping):
                ranked.append(
                    {
                        "id": item.get("id") or item.get("symbol"),
                        "title": item.get("title") or item.get("symbol") or item.get("id"),
                        "symbol": item.get("symbol"),
                        "confidence": clamp01(item.get("confidence", item.get("score"))),
                        "expected_edge": item.get("expected_edge") or item.get("expected_return"),
                        "strategy_class": item.get("strategy_class") or item.get("strategy"),
                        "catalyst": item.get("catalyst"),
                        "expiry": item.get("expiry"),
                        "capital_required": item.get("capital_required"),
                        "expected_duration": item.get("expected_duration"),
                    }
                )
            else:
                ranked.append({"title": str(item), "confidence": None})

        # Update executive decision headline opportunities lazily by caller if needed
        return {
            "panel_id": "trading_intelligence",
            "panel_status": panel_status,
            "freshness": freshness,
            "ranked_opportunities": ranked,
            "selected_opportunities": [],
            "execution_action": "NO_EXECUTION",
            "portfolio_summary": portfolio
            or {
                "status": "UNAVAILABLE",
                "freshness": "UNAVAILABLE",
            },
            "portfolio_health": portfolio.get("portfolio_health") or portfolio.get("status") or "UNAVAILABLE",
            "concentration_flags": portfolio.get("concentration_flags")
            if isinstance(portfolio.get("concentration_flags"), list)
            else [],
            "capital_posture": {
                "available_capital": portfolio.get("available_capital"),
                "allocated_capital": portfolio.get("allocated_capital"),
                "reserved_capital": portfolio.get("reserved_capital"),
            },
            "unavailable_fields": [] if portfolio else ["portfolio_summary"],
        }

    def _panel_learning(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        learning = as_mapping(evidence.get("learning"))
        insights = evidence.get("ai_insights") if isinstance(evidence.get("ai_insights"), list) else []
        if not learning and not insights:
            return {
                "panel_id": "learning",
                "panel_status": "AMBER",
                "freshness": "AGING",
                "learning_summary": {"status": "UNAVAILABLE"},
                "factor_or_regime_deltas": [],
                "ai_insights": [],
                "insight_policy": {"citation_required": True},
                "confidence": None,
                "unavailable_fields": ["learning_summary"],
            }
        freshness = normalize_freshness(learning.get("freshness", "AGING"))
        # Drop insights without citations
        safe_insights = []
        for item in insights:
            if isinstance(item, Mapping) and item.get("citations"):
                safe_insights.append(item)
        return {
            "panel_id": "learning",
            "panel_status": "GREEN" if learning else "AMBER",
            "freshness": freshness,
            "learning_summary": learning.get("learning_summary") or learning or {"status": "PRESENT"},
            "factor_or_regime_deltas": learning.get("deltas") if isinstance(learning.get("deltas"), list) else [],
            "ai_insights": safe_insights,
            "insight_policy": {"citation_required": True},
            "confidence": clamp01(learning.get("confidence")),
            "unavailable_fields": [],
        }

    def _overall_status(self, panels: Mapping[str, Any], runtime: Mapping[str, Any], broker: Mapping[str, Any]) -> str:
        statuses = [
            str(as_mapping(panels.get(pid)).get("panel_status", "UNAVAILABLE")).upper()
            for pid in (
                "operational_health",
                "market_intelligence",
                "trading_intelligence",
                "executive_decision",
            )
        ]
        if "RED" in statuses or posture_from_runtime(str(runtime.get("status", ""))) == "RED":
            return "RED"
        if "UNAVAILABLE" in statuses:
            return "UNAVAILABLE"
        if "AMBER" in statuses:
            return "AMBER"
        bh = str(broker.get("health", broker.get("status", "GREEN"))).upper()
        if bh in {"RED", "OFFLINE"}:
            return "RED"
        if bh in {"AMBER", "DEGRADED", "LATENT"}:
            return "AMBER"
        return "GREEN"

    def _provenance(self, evidence: Mapping[str, Any], panels: Mapping[str, Any]) -> list[dict[str, Any]]:
        items = []
        for key in ("runtime_health", "broker_health", "portfolio", "market", "committee", "learning"):
            block = as_mapping(evidence.get(key))
            if not block:
                continue
            items.append(
                {
                    "source": key,
                    "source_module": block.get("source") or block.get("source_path") or key,
                    "artifact_path": block.get("source_path"),
                    "content_hash": block.get("state_hash") or block.get("hash"),
                    "generated_at": block.get("generated_at") or evidence.get("gathered_at_utc"),
                    "freshness": normalize_freshness(block.get("freshness", "UNAVAILABLE")),
                }
            )
        items.append(
            {
                "source": "panels",
                "source_module": "executive_morning_brief_assembler",
                "artifact_path": None,
                "content_hash": None,
                "generated_at": utc_now_iso(),
                "freshness": worst_freshness(
                    *[normalize_freshness(as_mapping(p).get("freshness", "UNAVAILABLE")) for p in panels.values()]
                ),
            }
        )
        return items
