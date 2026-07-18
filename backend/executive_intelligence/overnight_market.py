"""Phase 175 — Overnight Market Intelligence Producer.

Derives overnight market evidence from existing CSS artifacts and producers.
Never fabricates unavailable market data. Advisory-only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.sanitizer import sanitize_payload
from backend.executive_intelligence.utils import (
    as_mapping,
    clamp01,
    confidence_band,
    normalize_freshness,
    utc_now_iso,
    worst_freshness,
)

# Frozen executive ontology regimes (presentation layer)
EXECUTIVE_REGIMES = (
    "Risk-On",
    "Risk-Off",
    "Trending",
    "Mean Reversion",
    "Volatile",
    "Quiet",
    "Liquidity Stress",
    "Event Driven",
    "Transitional",
)

# Engine canonical → executive ontology (non-destructive mapping)
ENGINE_TO_EXECUTIVE = {
    "TREND_UP": "Trending",
    "TREND_DOWN": "Trending",
    "TRENDING_UP": "Trending",
    "TRENDING_DOWN": "Trending",
    "RANGE": "Mean Reversion",
    "MEAN_REVERTING": "Mean Reversion",
    "HIGH_VOLATILITY": "Volatile",
    "LOW_VOLATILITY": "Quiet",
    "RISK_ON": "Risk-On",
    "RISK-ON": "Risk-On",
    "RISK_OFF": "Risk-Off",
    "RISK-OFF": "Risk-Off",
    "NEUTRAL": "Transitional",
}

ASSET_CLASSES = (
    "FX",
    "Crypto",
    "Futures",
    "Options",
    "Equities",
    "Fixed Income",
    "Commodities",
)

ADVISORY_IMPLICATIONS = ("MONITOR", "OBSERVE", "PREPARE", "HEDGE", "AVOID", "REVIEW")


def produce_overnight_market_intelligence(
    repo_root: Path | str | None = None,
    *,
    injected: Mapping[str, Any] | None = None,
    reporting_window_start_utc: str | None = None,
    reporting_window_end_utc: str | None = None,
) -> dict[str, Any]:
    """
    Build canonical overnight market intelligence payload.

    Returns a fail-closed structure. When critical regime evidence is absent,
    ``market_data_status`` / freshness become UNAVAILABLE (never invented).

    Evidence selection:
    - ``injected`` omitted / ``None``: load from ``repo_root`` filesystem artifacts.
    - ``injected`` non-empty mapping: use only the injected bundle (no disk merge).
    - ``injected={}`` is falsy and therefore falls through to disk — tests that need
      an empty evidence environment must pass an empty ``repo_root`` or an explicit
      unavailable injected regime object.
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    generated_at = utc_now_iso()
    window_end = reporting_window_end_utc or generated_at
    if reporting_window_start_utc:
        window_start = reporting_window_start_utc
    else:
        try:
            end_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            end_dt = datetime.now(timezone.utc)
        window_start = (end_dt - timedelta(hours=18)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    sources = _collect_sources(root, injected=injected)
    provenance, hashes, freshness_labels = _build_provenance(sources)
    overall_freshness = worst_freshness(*freshness_labels) if freshness_labels else "UNAVAILABLE"

    coverage = _asset_class_coverage(sources)
    regime = _regime_block(sources)
    summary = _overnight_summary(sources, coverage, regime)
    confidence = _market_confidence(sources, coverage, regime, overall_freshness)
    implications = _trading_implications(regime, confidence, coverage)
    opportunity_input = _opportunity_input(sources)

    market_data_status = "AVAILABLE"
    validation_status = "PASS"
    blockers: list[str] = []

    if not regime.get("current_regime") or regime.get("current_regime") == "UNAVAILABLE":
        market_data_status = "UNAVAILABLE"
        validation_status = "FAIL"
        blockers.append("regime_evidence_unavailable")
        overall_freshness = "UNAVAILABLE"

    if overall_freshness == "STALE":
        validation_status = "FAIL"
        blockers.append("market_evidence_stale")
        market_data_status = "STALE"

    if not sources and not injected:
        market_data_status = "UNAVAILABLE"
        validation_status = "FAIL"
        blockers.append("no_market_sources")
        overall_freshness = "UNAVAILABLE"

    payload = {
        "schema_version": "css.overnight_market_intelligence.v1",
        "reporting_window_start_utc": window_start,
        "reporting_window_end_utc": window_end,
        "generated_at_utc": generated_at,
        "source_provenance": provenance,
        "source_hashes": hashes,
        "freshness": overall_freshness,
        "validation_status": validation_status,
        "market_data_status": market_data_status,
        "blockers": blockers,
        "asset_class_coverage": coverage,
        "overnight_summary": summary,
        "market_regime": regime,
        "market_confidence": confidence,
        "trading_implications": implications,
        "opportunity_input": opportunity_input,
        # Convenience fields for Phase 174 evidence/assembler
        "regime": regime.get("current_regime"),
        "regime_current": regime.get("current_regime"),
        "regime_confidence": regime.get("regime_confidence"),
        "confidence": confidence.get("value"),
        "overnight_market_summary": summary,
        **SAFETY_LOCKS,
    }
    return sanitize_payload(payload)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _file_hash(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _collect_sources(root: Path, *, injected: Mapping[str, Any] | None) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    if injected:
        for key, value in injected.items():
            if value is None:
                continue
            if isinstance(value, Mapping) and "payload" in value:
                sources[str(key)] = dict(value)
            else:
                sources[str(key)] = {
                    "path": f"injected:{key}",
                    "payload": value if isinstance(value, Mapping) else {"value": value},
                    "freshness": as_mapping(value).get("freshness", "FRESH") if isinstance(value, Mapping) else "FRESH",
                }
        return sources

    candidates = {
        "runtime_advisory_snapshot": root / "artifacts" / "runtime_advisory_snapshot.json",
        "portfolio_decision": root / "artifacts" / "portfolio_decision.json",
        "portfolio_snapshot": root / "artifacts" / "portfolio_snapshot.json",
        "runtime_portfolio_state": root / "artifacts" / "runtime_portfolio_state.json",
        "validation_summary": root / "artifacts" / "validation_summary.json",
        "session_state": root / "artifacts" / "css_session_state_pcnrass.json",
    }
    for name, path in candidates.items():
        payload = _load_json(path)
        if payload is not None:
            rel = str(path)
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                pass
            sources[name] = {"path": rel, "payload": payload, "abs_path": path}
    return sources


def _build_provenance(sources: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    provenance: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    freshness_labels: list[str] = []
    for name, meta in sources.items():
        if not isinstance(meta, Mapping):
            continue
        payload = as_mapping(meta.get("payload") if "payload" in meta else meta)
        path = meta.get("path") or meta.get("source_path") or name
        abs_path = meta.get("abs_path")
        digest = None
        if isinstance(abs_path, Path):
            digest = _file_hash(abs_path)
        if digest is None and payload:
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
        fresh = normalize_freshness(payload.get("freshness") or meta.get("freshness") or "AGING")
        freshness_labels.append(fresh)
        provenance.append(
            {
                "source": name,
                "artifact_path": path,
                "freshness": fresh,
                "content_hash": digest,
            }
        )
        if digest:
            hashes[str(name)] = digest
    return provenance, hashes, freshness_labels


def _map_regime(raw: Any) -> str:
    if raw is None or raw == "":
        return "UNAVAILABLE"
    text = str(raw).strip()
    if text in EXECUTIVE_REGIMES:
        return text
    upper = text.upper().replace(" ", "_")
    if upper in ENGINE_TO_EXECUTIVE:
        return ENGINE_TO_EXECUTIVE[upper]
    # soft match
    for key, label in ENGINE_TO_EXECUTIVE.items():
        if key in upper or upper in key:
            return label
    # already human-ish
    for label in EXECUTIVE_REGIMES:
        if label.lower() == text.lower():
            return label
    return "Transitional" if text.upper() not in {"UNAVAILABLE", "UNKNOWN", "DATA UNAVAILABLE"} else "UNAVAILABLE"


def _regime_block(sources: Mapping[str, Any]) -> dict[str, Any]:
    advisory = as_mapping(as_mapping(sources.get("runtime_advisory_snapshot")).get("payload"))
    decision = as_mapping(as_mapping(sources.get("portfolio_decision")).get("payload"))
    session = as_mapping(as_mapping(sources.get("session_state")).get("payload"))
    injected_regime = as_mapping(as_mapping(sources.get("regime")).get("payload"))
    injected_market = as_mapping(as_mapping(sources.get("market")).get("payload"))

    current_raw = (
        injected_regime.get("current")
        or injected_regime.get("current_regime")
        or injected_regime.get("regime")
        or injected_market.get("regime_current")
        or injected_market.get("regime")
        or advisory.get("market_regime")
        or advisory.get("regime")
        or decision.get("market_regime")
        or as_mapping(decision.get("market_intelligence")).get("regime")
        or session.get("market_regime")
    )
    prior_raw = (
        injected_regime.get("prior")
        or injected_regime.get("prior_regime")
        or advisory.get("prior_regime")
        or decision.get("prior_regime")
        or injected_market.get("prior_regime")
    )
    transition = (
        injected_regime.get("transition_time")
        or advisory.get("regime_transition_time")
        or decision.get("regime_transition_time")
        or injected_market.get("regime_transition_time")
    )
    conf = clamp01(
        injected_regime.get("confidence")
        or injected_market.get("regime_confidence")
        or advisory.get("regime_confidence")
        or decision.get("regime_confidence")
    )

    current = _map_regime(current_raw)
    prior = _map_regime(prior_raw) if prior_raw else "UNAVAILABLE"

    implications: list[str] = []
    strategy_implications: list[str] = []
    if current == "Risk-Off":
        implications.append("Defensive posture favored; reduce risk appetite.")
        strategy_implications.append("Prefer capital preservation and hedge reviews.")
    elif current == "Risk-On":
        implications.append("Risk appetite elevated; monitor opportunity density.")
        strategy_implications.append("Momentum/participation strategies may be more relevant.")
    elif current == "Volatile":
        implications.append("Elevated volatility; widen monitoring and hedge reviews.")
        strategy_implications.append("Avoid over-concentration; prefer Review/Prepare.")
    elif current == "Quiet":
        implications.append("Compressed volatility; mean-reversion and carry may dominate.")
    elif current == "UNAVAILABLE":
        implications.append("Regime evidence unavailable — fail closed for market panel.")
    else:
        implications.append(f"Executive regime labeled {current}; monitor transitions.")

    supporting = []
    for name in ("runtime_advisory_snapshot", "portfolio_decision", "session_state", "regime"):
        if name in sources:
            supporting.append(name)

    freshness = normalize_freshness(
        advisory.get("freshness") or decision.get("freshness") or as_mapping(sources.get("regime")).get("freshness") or ("AGING" if current != "UNAVAILABLE" else "UNAVAILABLE")
    )

    return {
        "current_regime": current,
        "prior_regime": prior,
        "regime_transition_time": transition or "UNAVAILABLE",
        "regime_confidence": conf,
        "regime_implications": implications,
        "strategy_implications": strategy_implications,
        "supporting_evidence": supporting,
        "engine_regime_raw": current_raw if current_raw is not None else "UNAVAILABLE",
        "freshness": freshness if current != "UNAVAILABLE" else "UNAVAILABLE",
    }


def _asset_class_coverage(sources: Mapping[str, Any]) -> dict[str, Any]:
    decision = as_mapping(as_mapping(sources.get("portfolio_decision")).get("payload"))
    portfolio = as_mapping(as_mapping(sources.get("runtime_portfolio_state")).get("payload")) or as_mapping(
        as_mapping(sources.get("portfolio_snapshot")).get("payload")
    )
    opps = decision.get("ranked_opportunities") or decision.get("opportunities") or []
    if not isinstance(opps, list):
        opps = []

    tags_found: set[str] = set()
    instruments: list[str] = []
    for item in opps:
        if isinstance(item, Mapping):
            sym = str(item.get("symbol") or item.get("id") or "")
            if sym:
                instruments.append(sym)
            cls = str(item.get("market") or item.get("asset_class") or item.get("strategy_class") or "")
            tags_found |= _infer_asset_classes(sym, cls)
        else:
            instruments.append(str(item))

    # portfolio symbols
    positions = portfolio.get("positions") or portfolio.get("holdings") or []
    if isinstance(positions, list):
        for pos in positions:
            if isinstance(pos, Mapping):
                sym = str(pos.get("symbol") or pos.get("instrument") or "")
                if sym:
                    instruments.append(sym)
                    tags_found |= _infer_asset_classes(sym, str(pos.get("asset_class") or ""))

    injected_markets = as_mapping(sources.get("markets"))
    for cls in ASSET_CLASSES:
        if cls in injected_markets or cls.lower() in {k.lower() for k in injected_markets.keys()}:
            tags_found.add(cls)

    coverage = {}
    for cls in ASSET_CLASSES:
        if cls in tags_found:
            coverage[cls] = {"status": "AVAILABLE", "freshness": "AGING"}
        else:
            coverage[cls] = {"status": "UNAVAILABLE", "freshness": "UNAVAILABLE"}
    coverage["_instruments_monitored"] = sorted(set(instruments))
    coverage["_available_count"] = sum(1 for c in ASSET_CLASSES if coverage[c]["status"] == "AVAILABLE")
    coverage["_total_classes"] = len(ASSET_CLASSES)
    return coverage


def _infer_asset_classes(symbol: str, cls: str) -> set[str]:
    found: set[str] = set()
    blob = f"{symbol} {cls}".upper()
    if any(x in blob for x in ("USD", "EUR", "GBP", "JPY", "FX", "FOREX")) and "BTC" not in blob and "ETH" not in blob:
        found.add("FX")
    if any(x in blob for x in ("BTC", "ETH", "CRYPTO", "COIN", "USDT")):
        found.add("Crypto")
    if any(x in blob for x in ("FUT", "FUTURE", "ES", "NQ", "/")):
        found.add("Futures")
    if any(x in blob for x in ("OPT", "OPTION", "CALL", "PUT")):
        found.add("Options")
    if any(x in blob for x in ("SPY", "QQQ", "EQUITY", "STOCK", "SHARE")):
        found.add("Equities")
    if any(x in blob for x in ("BOND", "TLT", "YIELD", "FIXED", "TREAS")):
        found.add("Fixed Income")
    if any(x in blob for x in ("GOLD", "OIL", "WTI", "XAU", "COMMOD")):
        found.add("Commodities")
    # explicit class string
    for name in ASSET_CLASSES:
        if name.upper().replace(" ", "_") in blob.replace(" ", "_"):
            found.add(name)
    return found


def _overnight_summary(sources: Mapping[str, Any], coverage: Mapping[str, Any], regime: Mapping[str, Any]) -> dict[str, Any]:
    instruments = list(coverage.get("_instruments_monitored") or [])
    decision = as_mapping(as_mapping(sources.get("portfolio_decision")).get("payload"))
    advisory = as_mapping(as_mapping(sources.get("runtime_advisory_snapshot")).get("payload"))

    movers = []
    for item in (decision.get("ranked_opportunities") or [])[:5]:
        if isinstance(item, Mapping):
            movers.append(
                {
                    "symbol": item.get("symbol") or item.get("id"),
                    "change": item.get("change") or item.get("expected_return") or "UNAVAILABLE",
                    "note": "from_opportunity_ranking" if item.get("expected_return") is not None else "listed",
                }
            )

    unavailable_warnings = [
        f"{cls} evidence UNAVAILABLE"
        for cls in ASSET_CLASSES
        if as_mapping(coverage.get(cls)).get("status") == "UNAVAILABLE"
    ]

    vol = advisory.get("volatility") or decision.get("volatility") or sources.get("volatility")
    liquidity = advisory.get("liquidity") or decision.get("liquidity") or sources.get("liquidity")
    events = advisory.get("market_events") or decision.get("market_events") or sources.get("market_events") or []
    if not isinstance(events, list):
        events = []

    correlations = advisory.get("correlations") or decision.get("correlations") or []
    if not isinstance(correlations, list):
        correlations = []

    return {
        "instruments_monitored": instruments,
        "instruments_monitored_count": len(instruments),
        "market_events_observed": events if events else ["UNAVAILABLE"],
        "major_overnight_movers": movers if movers else [],
        "significant_price_changes": movers if movers else [],
        "volatility_changes": vol if vol is not None else "UNAVAILABLE",
        "liquidity_observations": liquidity if liquidity is not None else "UNAVAILABLE",
        "cross_asset_relationships": correlations if correlations else ["UNAVAILABLE"],
        "relevant_regime_transitions": [
            {
                "from": regime.get("prior_regime"),
                "to": regime.get("current_regime"),
                "at": regime.get("regime_transition_time"),
            }
        ]
        if regime.get("current_regime") not in (None, "UNAVAILABLE")
        else [],
        "material_correlations_or_divergences": correlations if correlations else ["UNAVAILABLE"],
        "unavailable_data_warnings": unavailable_warnings,
        "note": "Derived from existing CSS artifacts only; empty fields remain UNAVAILABLE.",
    }


def _market_confidence(
    sources: Mapping[str, Any],
    coverage: Mapping[str, Any],
    regime: Mapping[str, Any],
    overall_freshness: str,
) -> dict[str, Any]:
    available = int(coverage.get("_available_count") or 0)
    total = int(coverage.get("_total_classes") or len(ASSET_CLASSES))
    coverage_ratio = available / total if total else 0.0
    regime_conf = clamp01(regime.get("regime_confidence"))
    source_count = len(sources)
    agreement = 1.0 if source_count >= 2 else (0.6 if source_count == 1 else 0.0)
    fresh_factor = {"FRESH": 1.0, "AGING": 0.85, "STALE": 0.0, "UNAVAILABLE": 0.0}.get(overall_freshness, 0.0)

    if regime.get("current_regime") in (None, "UNAVAILABLE") or fresh_factor == 0.0:
        return {
            "value": None,
            "confidence_band": "UNAVAILABLE",
            "evidence_coverage": round(coverage_ratio, 6),
            "freshness": overall_freshness,
            "validation": "FAIL",
            "explanation": "Insufficient or stale market/regime evidence; confidence withheld.",
        }

    base = 0.35 * coverage_ratio + 0.35 * (regime_conf if regime_conf is not None else 0.5) + 0.20 * agreement + 0.10
    value = clamp01(base * fresh_factor)
    return {
        "value": value,
        "confidence_band": confidence_band(value),
        "evidence_coverage": round(coverage_ratio, 6),
        "freshness": overall_freshness,
        "validation": "PASS" if value is not None else "FAIL",
        "explanation": (
            f"Coverage={coverage_ratio:.2f}, regime_confidence={regime_conf}, "
            f"sources={source_count}, freshness={overall_freshness}."
        ),
    }


def _trading_implications(regime: Mapping[str, Any], confidence: Mapping[str, Any], coverage: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    current = regime.get("current_regime")
    conf = clamp01(confidence.get("value"))

    if current in (None, "UNAVAILABLE"):
        actions.append({"type": "REVIEW", "detail": "Market regime unavailable — review evidence sources."})
        return actions

    actions.append({"type": "MONITOR", "detail": f"Monitor executive regime {current}."})
    if conf is not None and conf < 0.6:
        actions.append({"type": "OBSERVE", "detail": "Market confidence low — prefer observational posture."})
    if current in {"Volatile", "Liquidity Stress"}:
        actions.append({"type": "HEDGE", "detail": "Volatility/liquidity stress — advisory hedge review."})
        actions.append({"type": "AVOID", "detail": "Avoid initiating fragile theses without fresh evidence."})
    if current == "Risk-Off":
        actions.append({"type": "PREPARE", "detail": "Prepare defensive playbooks; keep execution disarmed."})
    if int(coverage.get("_available_count") or 0) == 0:
        actions.append({"type": "REVIEW", "detail": "No asset-class coverage — review market data feeds."})

    # Deduplicate by type, cap
    seen = set()
    out = []
    for item in actions:
        t = item["type"]
        if t not in ADVISORY_IMPLICATIONS or t in seen:
            continue
        seen.add(t)
        item["advisory_only"] = True
        item["execution_allowed"] = False
        out.append(item)
        if len(out) >= 5:
            break
    return out


def _opportunity_input(sources: Mapping[str, Any]) -> dict[str, Any]:
    decision = as_mapping(as_mapping(sources.get("portfolio_decision")).get("payload"))
    opps = decision.get("ranked_opportunities") or decision.get("opportunities") or []
    if not isinstance(opps, list):
        opps = []
    # Also accept injected opportunities
    injected = sources.get("opportunities")
    if isinstance(injected, list) and injected:
        opps = injected
    normalized = []
    for item in opps[:20]:
        if isinstance(item, Mapping):
            normalized.append(
                {
                    "symbol": item.get("symbol") or item.get("id"),
                    "confidence": clamp01(item.get("confidence", item.get("score"))),
                    "expected_edge": item.get("expected_edge") or item.get("expected_return"),
                    "strategy_class": item.get("strategy_class") or item.get("strategy"),
                    "catalyst": item.get("catalyst") or "overnight_evidence",
                    "market": item.get("market") or item.get("asset_class"),
                }
            )
    return {
        "ranked_opportunity_seeds": normalized,
        "count": len(normalized),
        "note": "Feeds Phase 174 opportunity ranking; does not replace it.",
        "advisory_only": True,
    }
