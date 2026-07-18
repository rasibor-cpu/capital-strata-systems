"""Evidence gathering for Executive Intelligence Engine (read-only)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import HEARTBEAT_STALE_SECONDS
from backend.executive_intelligence.utils import as_mapping, normalize_freshness, utc_now_iso


def gather_evidence(repo_root: Path | None = None, *, injected: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """
    Build an evidence bundle.

    If ``injected`` is provided (tests / controlled runs), it is used as the base
    and only missing keys are filled from disk. Never fabricates market/broker/
    portfolio/runtime facts.
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    evidence: dict[str, Any] = dict(injected or {})

    if "runtime_health" not in evidence:
        evidence["runtime_health"] = _load_runtime_health(root)
    if "broker_health" not in evidence:
        evidence["broker_health"] = _load_broker_health(root)
    if "portfolio" not in evidence:
        evidence["portfolio"] = _load_portfolio(root)
    if "market" not in evidence:
        evidence["market"] = _load_market(root)
    if "opportunities" not in evidence:
        evidence["opportunities"] = _load_opportunities(root)
    if "committee" not in evidence:
        evidence["committee"] = _load_json(root / "artifacts" / "portfolio_decision.json") or {}
    if "learning" not in evidence:
        evidence["learning"] = {}
    if "risk" not in evidence:
        evidence["risk"] = {}
    if "alerts" not in evidence:
        evidence["alerts"] = {}
    if "explainability" not in evidence:
        evidence["explainability"] = {}

    evidence.setdefault("gathered_at_utc", utc_now_iso())
    evidence.setdefault("repo_root", str(root))
    return evidence


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _load_runtime_health(root: Path) -> dict[str, Any]:
    supervisor = _load_json(root / "runtime" / "supervisor" / "css_runtime_supervisor_state.json") or {}
    if not supervisor:
        return {}
    age = supervisor.get("heartbeat_age_seconds")
    if age is None and supervisor.get("last_heartbeat"):
        age = None  # leave unknown rather than invent
    freshness = "FRESH"
    try:
        if age is not None and float(age) > HEARTBEAT_STALE_SECONDS:
            freshness = "STALE"
        elif age is not None and float(age) > HEARTBEAT_STALE_SECONDS / 2:
            freshness = "AGING"
    except (TypeError, ValueError):
        freshness = normalize_freshness(supervisor.get("freshness", "AGING"))

    status = supervisor.get("status") or supervisor.get("runtime_status") or supervisor.get("health") or "UNKNOWN"
    return {
        "status": status,
        "runtime_health": status,
        "freshness": freshness,
        "heartbeat_age_seconds": age,
        "runtime_id": supervisor.get("runtime_id"),
        "supervisor_id": supervisor.get("supervisor_id"),
        "state_hash": supervisor.get("state_hash"),
        "source_path": "runtime/supervisor/css_runtime_supervisor_state.json",
    }


def _load_broker_health(root: Path) -> dict[str, Any]:
    # Prefer sanitized operational summaries from account/session artifacts if present
    account = _load_json(root / "artifacts" / "css_account_state_pcnrass.json") or {}
    session = _load_json(root / "artifacts" / "css_session_state_pcnrass.json") or {}
    broker_block = as_mapping(account.get("broker_operational_status") or session.get("broker_operational_status"))
    if not broker_block:
        # Try building from module if importable and no secrets required
        try:
            from backend.runtime.broker_operational_status import build_broker_operational_status

            broker_block = build_broker_operational_status()
        except Exception:
            return {}
    freshness = normalize_freshness(broker_block.get("freshness", "AGING"))
    return {
        "health": broker_block.get("overall_status") or broker_block.get("health") or broker_block.get("status") or "UNKNOWN",
        "status": broker_block.get("overall_status") or broker_block.get("status") or "UNKNOWN",
        "freshness": freshness,
        "brokers": broker_block.get("brokers") or broker_block.get("venues") or {},
        "source": "broker_operational_status",
    }


def _load_portfolio(root: Path) -> dict[str, Any]:
    payload = (
        _load_json(root / "artifacts" / "runtime_portfolio_state.json")
        or _load_json(root / "artifacts" / "portfolio_snapshot.json")
        or {}
    )
    if not payload:
        return {}
    return {
        "status": payload.get("portfolio_status") or payload.get("status") or "OK",
        "freshness": normalize_freshness(payload.get("freshness", "AGING")),
        "equity": payload.get("equity") or payload.get("total_equity"),
        "cash": payload.get("cash"),
        "total_exposure": payload.get("total_exposure") or payload.get("exposure"),
        "portfolio_health": payload.get("portfolio_health") or payload.get("health"),
        "capital_efficiency": payload.get("capital_efficiency"),
        "available_capital": payload.get("available_capital"),
        "allocated_capital": payload.get("allocated_capital"),
        "reserved_capital": payload.get("reserved_capital"),
        "source_path": "artifacts/runtime_portfolio_state.json|portfolio_snapshot.json",
    }


def _load_market(root: Path) -> dict[str, Any]:
    # Existing regime / advisory snapshots only — overnight rollup is Phase 175
    advisory = _load_json(root / "artifacts" / "runtime_advisory_snapshot.json") or {}
    decision = _load_json(root / "artifacts" / "portfolio_decision.json") or {}
    regime = (
        advisory.get("market_regime")
        or advisory.get("regime")
        or decision.get("market_regime")
        or as_mapping(decision.get("market_intelligence")).get("regime")
    )
    if not regime:
        return {}
    return {
        "regime": regime,
        "regime_current": regime,
        "freshness": normalize_freshness(advisory.get("freshness") or decision.get("freshness") or "AGING"),
        "confidence": advisory.get("regime_confidence") or decision.get("regime_confidence"),
        "overnight_market_summary": None,  # Phase 175
        "source": "runtime_advisory_snapshot|portfolio_decision",
    }


def _load_opportunities(root: Path) -> list[Any]:
    decision = _load_json(root / "artifacts" / "portfolio_decision.json") or {}
    opps = decision.get("ranked_opportunities") or decision.get("opportunities") or []
    return list(opps) if isinstance(opps, list) else []
