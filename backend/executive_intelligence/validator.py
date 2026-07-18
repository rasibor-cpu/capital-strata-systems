"""Fail-closed validation for ExecutiveMorningBrief FINALization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.executive_intelligence.constants import HEARTBEAT_STALE_SECONDS, SAFETY_LOCKS
from backend.executive_intelligence.sanitizer import contains_secrets
from backend.executive_intelligence.utils import as_mapping, normalize_freshness, posture_from_runtime


def validate_brief_for_final(
    brief: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return MorningBriefValidationResult-compatible dict.

    FINAL blocked when:
    - runtime stale / unavailable
    - broker stale / unavailable
    - portfolio unavailable
    - market panel UNAVAILABLE (Freeze v1.0)
    - critical artifacts missing
    - safety locks incorrect
    - secrets present
    - schema missing
    """
    evidence = evidence or {}
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    panels = as_mapping(brief.get("panels"))
    section_availability: dict[str, str] = {}

    def _check(name: str, ok: bool, reason: str = "") -> None:
        checks.append({"name": name, "pass": ok, "reason": reason})
        if not ok:
            blockers.append(reason or name)

    # Safety locks
    for key, expected in SAFETY_LOCKS.items():
        actual = brief.get(key)
        _check(f"safety_{key}", actual is expected, f"safety_lock_invalid:{key}")

    # Schema
    schema = brief.get("schema_version")
    _check("schema_version", schema == "css.executive_morning_brief.v1", "schema_version_mismatch")

    # Runtime freshness
    runtime = as_mapping(evidence.get("runtime_health") or as_mapping(panels.get("operational_health")).get("runtime_health"))
    runtime_fresh = normalize_freshness(
        runtime.get("freshness")
        or as_mapping(panels.get("operational_health")).get("freshness")
        or brief.get("data_freshness_status")
    )
    heartbeat_age = runtime.get("heartbeat_age_seconds")
    try:
        age = float(heartbeat_age) if heartbeat_age is not None else None
    except (TypeError, ValueError):
        age = None
    runtime_stale = runtime_fresh in {"STALE", "UNAVAILABLE"} or (age is not None and age > HEARTBEAT_STALE_SECONDS)
    runtime_status = posture_from_runtime(str(runtime.get("status", runtime.get("runtime_health", ""))))
    if runtime_status == "UNAVAILABLE" and not runtime:
        runtime_stale = True
    _check("runtime_fresh", not runtime_stale, "runtime_stale_or_unavailable")
    section_availability["runtime"] = "UNAVAILABLE" if runtime_stale else runtime_fresh

    # Broker freshness
    broker = as_mapping(evidence.get("broker_health"))
    broker_fresh = normalize_freshness(broker.get("freshness") or as_mapping(panels.get("operational_health")).get("broker_freshness"))
    broker_missing = not broker or broker_fresh in {"STALE", "UNAVAILABLE"}
    # Allow RED/degraded broker if evidence is present and fresh
    if broker and broker_fresh in {"FRESH", "AGING"}:
        broker_missing = False
    _check("broker_fresh", not broker_missing, "broker_stale_or_unavailable")
    section_availability["broker"] = "UNAVAILABLE" if broker_missing else broker_fresh

    # Portfolio availability (Phase 174: unavailable/stale blocks FINAL)
    portfolio = as_mapping(evidence.get("portfolio"))
    trading = as_mapping(panels.get("trading_intelligence"))
    portfolio_summary = as_mapping(trading.get("portfolio_summary")) or portfolio
    portfolio_fresh = normalize_freshness(portfolio.get("freshness") or trading.get("freshness"))
    has_portfolio_signal = bool(portfolio_summary) and (
        portfolio_summary.get("equity") is not None
        or portfolio_summary.get("status") not in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE")
        or str(trading.get("panel_status", "")).upper() not in {"", "UNAVAILABLE"}
    )
    portfolio_unavailable = (
        not has_portfolio_signal
        or str(trading.get("panel_status", "")).upper() == "UNAVAILABLE"
        or portfolio_fresh in {"UNAVAILABLE", "STALE"}
    )
    _check("portfolio_available", not portfolio_unavailable, "portfolio_stale_or_unavailable")
    section_availability["portfolio"] = "UNAVAILABLE" if portfolio_unavailable else portfolio_fresh

    # Market panel (Freeze: UNAVAILABLE blocks FINAL)
    market = as_mapping(panels.get("market_intelligence"))
    market_status = str(market.get("panel_status", "UNAVAILABLE")).upper()
    market_fresh = normalize_freshness(market.get("freshness", "UNAVAILABLE"))
    market_blocked = market_status == "UNAVAILABLE" or market_fresh == "UNAVAILABLE" or not market
    _check("market_panel", not market_blocked, "market_panel_unavailable")
    section_availability["market"] = "UNAVAILABLE" if market_blocked else market_fresh

    # Critical identity fields
    for field in ("report_id", "report_date", "generated_at_utc"):
        _check(f"identity_{field}", bool(brief.get(field)), f"missing_{field}")

    # Secrets
    has_secrets, secret_reasons = contains_secrets(brief)
    _check("secret_scan", not has_secrets, ",".join(secret_reasons) if secret_reasons else "")

    # Panels present
    for panel_id in (
        "executive_decision",
        "operational_health",
        "market_intelligence",
        "trading_intelligence",
        "learning",
    ):
        present = panel_id in panels and isinstance(panels.get(panel_id), Mapping)
        _check(f"panel_{panel_id}", present, f"missing_panel:{panel_id}")
        if present:
            section_availability[panel_id] = str(as_mapping(panels.get(panel_id)).get("panel_status", "UNKNOWN"))

    status = "PASS" if not blockers else "FAIL"
    return {
        "status": status,
        "validation_status": status,
        "pass": status == "PASS",
        "checks": checks,
        "blockers": blockers,
        "section_availability": section_availability,
        "finalization_allowed": status == "PASS",
        "advisory_only": True,
        "execution_allowed": False,
    }
