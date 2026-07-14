from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.options.options_broker_abstraction import HEALTH_STATUSES, PAPER_ONLY_FLAGS, OptionsBrokerAbstractionError


@dataclass(frozen=True)
class OptionsBrokerHealth:
    provider_name: str
    availability: str
    data_freshness: str
    quote_latency_ms: float
    chain_latency_ms: float
    greeks_availability: str
    iv_coverage: float
    market_data_completeness: float
    health_score: float
    status: str
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


class OptionsBrokerHealthMonitor:
    def assess(
        self,
        *,
        provider_name: str,
        market_data: Mapping[str, Any] | None,
        chain: Mapping[str, Any] | None,
        quote_latency_ms: float = 0.0,
        chain_latency_ms: float = 0.0,
    ) -> OptionsBrokerHealth:
        if quote_latency_ms < 0 or chain_latency_ms < 0:
            raise OptionsBrokerAbstractionError("latency cannot be negative")
        md = dict(market_data or {})
        ch = dict(chain or {})
        availability = "ONLINE" if md and ch else "UNAVAILABLE"
        data_freshness = "FRESH" if md.get("freshness_timestamp") and ch.get("generated_at") else "STALE"
        greeks = dict(md.get("greeks") or {})
        greeks_availability = "AVAILABLE" if all(field in greeks for field in ("delta", "gamma", "theta", "vega", "rho")) else "UNAVAILABLE"
        contracts = list(ch.get("calls") or []) + list(ch.get("puts") or [])
        iv_count = sum(1 for row in contracts if float(row.get("implied_volatility", 0.0) or 0.0) > 0.0)
        iv_coverage = round(iv_count / len(contracts), 8) if contracts else 0.0
        complete_fields = sum(1 for field in ("quote", "greeks", "implied_volatility", "freshness_timestamp") if md.get(field) not in (None, {}, ""))
        market_data_completeness = round(complete_fields / 4.0, 8)
        score = 100.0
        if availability != "ONLINE":
            score -= 45.0
        if data_freshness != "FRESH":
            score -= 15.0
        if greeks_availability != "AVAILABLE":
            score -= 15.0
        score -= (1.0 - iv_coverage) * 15.0
        score -= max(0.0, quote_latency_ms - 250.0) / 50.0
        score -= max(0.0, chain_latency_ms - 500.0) / 50.0
        health_score = round(max(0.0, min(100.0, score)), 6)
        status = "ONLINE" if health_score >= 90 else ("DEGRADED" if health_score >= 50 else ("OFFLINE" if availability == "ONLINE" else "UNAVAILABLE"))
        if status not in HEALTH_STATUSES:
            status = "UNAVAILABLE"
        return OptionsBrokerHealth(
            provider_name=str(provider_name or ""),
            availability=availability,
            data_freshness=data_freshness,
            quote_latency_ms=round(float(quote_latency_ms), 6),
            chain_latency_ms=round(float(chain_latency_ms), 6),
            greeks_availability=greeks_availability,
            iv_coverage=iv_coverage,
            market_data_completeness=market_data_completeness,
            health_score=health_score,
            status=status,
        )


__all__ = ["OptionsBrokerHealth", "OptionsBrokerHealthMonitor"]
