"""Prioritized Executive Actions (advisory-only)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.executive_intelligence.utils import as_mapping, clamp01, posture_from_runtime


ALLOWED_TYPES = {
    "Monitor",
    "Observe",
    "Prepare",
    "Enter",
    "Scale In",
    "Scale Out",
    "Reduce Risk",
    "Increase Exposure",
    "Hedge",
    "Avoid",
    "Close",
    "Review",
}


def generate_executive_actions(
    *,
    evidence: Mapping[str, Any],
    panels: Mapping[str, Any],
    kpis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build prioritized advisory actions. Never grants execution authority."""
    actions: list[dict[str, Any]] = []
    runtime = as_mapping(evidence.get("runtime_health"))
    broker = as_mapping(evidence.get("broker_health"))
    decision = as_mapping(panels.get("executive_decision"))
    market = as_mapping(panels.get("market_intelligence"))
    trading = as_mapping(panels.get("trading_intelligence"))

    rh = posture_from_runtime(str(runtime.get("status", runtime.get("runtime_health", ""))))
    if rh in {"RED", "UNAVAILABLE"}:
        actions.append(
            _action(
                priority=1,
                action_type="Review",
                title="Review runtime health fail-closed state",
                detail="Runtime evidence is RED or UNAVAILABLE. Do not escalate trading posture.",
                rationale="Operational Health degraded",
            )
        )
    elif rh == "AMBER":
        actions.append(
            _action(
                priority=2,
                action_type="Monitor",
                title="Monitor runtime recovery",
                detail="Runtime is degraded/recovering. Continue advisory observation.",
                rationale="Operational Health AMBER",
            )
        )

    bh = str(broker.get("health", broker.get("status", ""))).upper()
    if bh in {"RED", "OFFLINE", "FAILED", "UNAVAILABLE", ""}:
        actions.append(
            _action(
                priority=1,
                action_type="Review",
                title="Review broker operational readiness",
                detail="Broker health is not GREEN. Keep execution disarmed.",
                rationale="Broker Reliability",
            )
        )
    elif bh in {"AMBER", "DEGRADED", "LATENT"}:
        actions.append(
            _action(
                priority=2,
                action_type="Prepare",
                title="Prepare broker remediation checklist",
                detail="Broker latency/degradation detected. Advisory-only remediation prep.",
                rationale="Broker Reliability",
            )
        )

    vetoes = decision.get("committee_vetoes") or []
    if vetoes:
        actions.append(
            _action(
                priority=1,
                action_type="Reduce Risk",
                title="Honor committee risk veto posture",
                detail=f"Active veto markers: {len(list(vetoes))}. Maintain reduced-risk advisory posture.",
                rationale="Risk Committee",
            )
        )

    conf = clamp01(decision.get("confidence") or decision.get("decision_confidence"))
    if conf is not None and conf < 0.6:
        actions.append(
            _action(
                priority=2,
                action_type="Observe",
                title="Keep decision posture observational",
                detail="Decision confidence is Very Low/Low. Prefer Observe/Monitor.",
                rationale="Decision Quality",
            )
        )

    regime = market.get("regime_current") or market.get("regime")
    if regime and str(regime).upper() not in {"UNAVAILABLE", "UNKNOWN"}:
        actions.append(
            _action(
                priority=3,
                action_type="Monitor",
                title=f"Monitor regime: {regime}",
                detail="Track regime stability into the session open.",
                rationale="Market Intelligence",
            )
        )

    opps = trading.get("ranked_opportunities") if isinstance(trading.get("ranked_opportunities"), list) else []
    if opps:
        top = opps[0] if isinstance(opps[0], Mapping) else {"title": str(opps[0])}
        title = top.get("title") or top.get("symbol") or top.get("id") or "top opportunity"
        actions.append(
            _action(
                priority=3,
                action_type="Prepare",
                title=f"Prepare review of {title}",
                detail="Top-ranked advisory opportunity available. No execution authorized.",
                rationale="Opportunity Ranking",
                provenance={"opportunity": title},
            )
        )

    # Merge explicit recommended_actions from upstream 159A-style lists
    upstream = decision.get("recommended_actions") or evidence.get("recommended_actions") or []
    if isinstance(upstream, list):
        for idx, item in enumerate(upstream[:5]):
            if isinstance(item, Mapping):
                actions.append(
                    _action(
                        priority=3 + idx,
                        action_type=_coerce_type(item.get("type", "Review")),
                        title=str(item.get("title") or item.get("action") or item.get("message") or "Upstream action"),
                        detail=str(item.get("detail") or item.get("message") or "Advisory upstream recommendation"),
                        rationale="upstream_recommended_actions",
                    )
                )
            elif isinstance(item, str) and item.strip():
                actions.append(
                    _action(
                        priority=4 + idx,
                        action_type="Review",
                        title=item.strip()[:120],
                        detail=item.strip(),
                        rationale="upstream_recommended_actions",
                    )
                )

    # KPI-driven filler if still empty
    if not actions:
        actions.append(
            _action(
                priority=5,
                action_type="Monitor",
                title="Monitor Daily Executive Brief posture",
                detail="No critical advisory actions derived. Continue monitoring.",
                rationale="default",
            )
        )

    # Deduplicate by title, sort by priority, cap at 5 for "Highest Priority Today"
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in sorted(actions, key=lambda a: int(a.get("priority", 99))):
        key = str(action.get("title", "")).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
        if len(deduped) >= 5:
            break

    # Re-number display ranks 1..N
    for i, action in enumerate(deduped, start=1):
        action["rank"] = i
        action["advisory_only"] = True
        action["execution_allowed"] = False

    # Attach KPI context snapshot (non-authoritative)
    action_block_meta = {
        "highest_priority_today": deduped,
        "kpi_names_considered": [k for k in kpis.keys() if k != "aliases"],
    }
    return deduped if not action_block_meta else deduped


def _action(
    *,
    priority: int,
    action_type: str,
    title: str,
    detail: str,
    rationale: str,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "priority": int(priority),
        "type": _coerce_type(action_type),
        "title": title,
        "detail": detail,
        "rationale": rationale,
        "provenance": dict(provenance or {}),
        "advisory_only": True,
        "execution_allowed": False,
    }


def _coerce_type(value: Any) -> str:
    text = str(value or "Review").strip()
    if text in ALLOWED_TYPES:
        return text
    # common aliases
    aliases = {
        "MONITOR": "Monitor",
        "OBSERVE": "Observe",
        "PREPARE": "Prepare",
        "ENTER": "Enter",
        "SCALE_IN": "Scale In",
        "SCALE_OUT": "Scale Out",
        "REDUCE_RISK": "Reduce Risk",
        "INCREASE_EXPOSURE": "Increase Exposure",
        "HEDGE": "Hedge",
        "AVOID": "Avoid",
        "CLOSE": "Close",
        "REVIEW": "Review",
    }
    return aliases.get(text.upper().replace(" ", "_"), "Review")
