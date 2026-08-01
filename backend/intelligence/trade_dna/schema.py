"""DIP-002 Trade DNA canonical fact schema (Layer 1 — immutable).

Derived metrics and advisory conclusions are intentionally excluded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

from backend.intelligence.trade_dna.constants import (
    EVIDENCE_VERSION,
    SCHEMA_VERSION,
)
from backend.intelligence.trade_dna.hashing import compute_content_hash


@dataclass(frozen=True)
class TradeIdentityFacts:
    trade_id: str
    dna_id: str
    session_id: Optional[str] = None
    parent_trade_id: Optional[str] = None
    instrument: Optional[str] = None
    asset_class: Optional[str] = None
    side: Optional[str] = None


@dataclass(frozen=True)
class ExecutionFacts:
    order_type: Optional[str] = None
    fill_kind: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    requested_quantity: Optional[float] = None
    filled_quantity: Optional[float] = None
    requested_notional: Optional[float] = None
    scaled_notional: Optional[float] = None
    fees: Optional[float] = None
    slippage_bps: Optional[float] = None
    spread: Optional[float] = None
    latency_ms: Optional[float] = None
    quantity_contract: Optional[str] = None
    notional_contract: Optional[str] = None
    execution_result: Optional[str] = None


@dataclass(frozen=True)
class MarketFacts:
    symbol: Optional[str] = None
    venue: Optional[str] = None
    session: Optional[str] = None
    timezone: Optional[str] = None
    market_regime: Optional[str] = None
    holiday_flag: Optional[bool] = None


@dataclass(frozen=True)
class StrategyFacts:
    strategy_id: Optional[str] = None
    engine_mode: Optional[str] = None
    signal_id: Optional[str] = None
    model_version: Optional[str] = None
    confluence_score: Optional[float] = None


@dataclass(frozen=True)
class RiskFacts:
    stop_distance: Optional[float] = None
    risk_pct: Optional[float] = None
    drawdown_context: Optional[float] = None
    margin_state: Optional[str] = None
    risk_settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernanceFacts:
    gate_final: Optional[str] = None
    gate_reason: Optional[str] = None
    kill_switch_state: Optional[str] = None
    governance_decisions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiquidityFacts:
    spread_regime: Optional[str] = None
    volume_proxy: Optional[float] = None
    gap_flag: Optional[bool] = None


@dataclass(frozen=True)
class VolatilityFacts:
    atr: Optional[float] = None
    realized_vol: Optional[float] = None
    vol_mult: Optional[float] = None
    vol_regime: Optional[str] = None


@dataclass(frozen=True)
class IndicatorFacts:
    """Named indicator snapshot observed at decision time (facts, not recomputes)."""

    observed: dict[str, Any] = field(default_factory=dict)
    indicator_schema_version: Optional[str] = None


@dataclass(frozen=True)
class BrokerFacts:
    broker_name: Optional[str] = None
    broker_mode: Optional[str] = None
    account_mode: Optional[str] = None
    practice: Optional[bool] = None


@dataclass(frozen=True)
class TimingFacts:
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    decision_at: Optional[str] = None
    executed_at: Optional[str] = None


@dataclass(frozen=True)
class OutcomeFacts:
    """Factual close labels only — MAE/MFE/PnL live in Layer 2 derived metrics."""

    status: Optional[str] = None
    exit_reason: Optional[str] = None
    win_loss: Optional[str] = None
    partial: Optional[bool] = None


@dataclass(frozen=True)
class EvidenceCustodyFacts:
    evidence_version: str = EVIDENCE_VERSION
    source_event_ids: tuple[str, ...] = ()
    source_artifact_uris: tuple[str, ...] = ()
    writer: Optional[str] = None
    captured_at: Optional[str] = None


@dataclass(frozen=True)
class RevisionFacts:
    revision: int = 1
    supersedes_dna_id: Optional[str] = None
    supersede_reason: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class MetadataFacts:
    provenance: dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeDNARecord:
    """Immutable Layer-1 Trade DNA fact record.

    Never embed derived metrics or advisory recommendations in this structure.
    """

    identity: TradeIdentityFacts
    schema_version: str = SCHEMA_VERSION
    execution: ExecutionFacts = field(default_factory=ExecutionFacts)
    market: MarketFacts = field(default_factory=MarketFacts)
    strategy: StrategyFacts = field(default_factory=StrategyFacts)
    risk: RiskFacts = field(default_factory=RiskFacts)
    governance: GovernanceFacts = field(default_factory=GovernanceFacts)
    liquidity: LiquidityFacts = field(default_factory=LiquidityFacts)
    volatility: VolatilityFacts = field(default_factory=VolatilityFacts)
    indicators: IndicatorFacts = field(default_factory=IndicatorFacts)
    broker: BrokerFacts = field(default_factory=BrokerFacts)
    timing: TimingFacts = field(default_factory=TimingFacts)
    outcome: OutcomeFacts = field(default_factory=OutcomeFacts)
    evidence_custody: EvidenceCustodyFacts = field(default_factory=EvidenceCustodyFacts)
    revision: RevisionFacts = field(default_factory=RevisionFacts)
    metadata: MetadataFacts = field(default_factory=MetadataFacts)
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_content_hash(self) -> "TradeDNARecord":
        """Return a new record with content_hash set from canonical fact body."""
        payload = self.to_dict()
        payload["content_hash"] = ""
        digest = compute_content_hash(payload)
        return TradeDNARecord(
            identity=self.identity,
            schema_version=self.schema_version,
            execution=self.execution,
            market=self.market,
            strategy=self.strategy,
            risk=self.risk,
            governance=self.governance,
            liquidity=self.liquidity,
            volatility=self.volatility,
            indicators=self.indicators,
            broker=self.broker,
            timing=self.timing,
            outcome=self.outcome,
            evidence_custody=self.evidence_custody,
            revision=self.revision,
            metadata=self.metadata,
            content_hash=digest,
        )


_TUPLE_FIELDS = {
    ("EvidenceCustodyFacts", "source_event_ids"),
    ("EvidenceCustodyFacts", "source_artifact_uris"),
}


def _section(cls: type, data: Any) -> Any:
    if isinstance(data, cls):
        return data
    if data is None:
        return cls()
    if not isinstance(data, Mapping):
        raise TypeError(f"expected mapping for {cls.__name__}")
    # Filter unknown keys for forward-compatible deserialize.
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in known}
    # Tuple fields may arrive as lists from JSON.
    for key, value in list(filtered.items()):
        if (cls.__name__, key) in _TUPLE_FIELDS and isinstance(value, list):
            filtered[key] = tuple(value)
    return cls(**filtered)


def trade_dna_from_dict(payload: Mapping[str, Any]) -> TradeDNARecord:
    """Deserialize a Trade DNA fact record (unknown category keys ignored)."""
    if not isinstance(payload, Mapping):
        raise TypeError("payload_must_be_mapping")
    identity_raw = payload.get("identity")
    if not isinstance(identity_raw, Mapping):
        raise ValueError("identity_required")
    identity = TradeIdentityFacts(
        trade_id=str(identity_raw.get("trade_id") or ""),
        dna_id=str(identity_raw.get("dna_id") or ""),
        session_id=identity_raw.get("session_id"),
        parent_trade_id=identity_raw.get("parent_trade_id"),
        instrument=identity_raw.get("instrument"),
        asset_class=identity_raw.get("asset_class"),
        side=identity_raw.get("side"),
    )
    return TradeDNARecord(
        identity=identity,
        schema_version=str(payload.get("schema_version") or SCHEMA_VERSION),
        execution=_section(ExecutionFacts, payload.get("execution")),
        market=_section(MarketFacts, payload.get("market")),
        strategy=_section(StrategyFacts, payload.get("strategy")),
        risk=_section(RiskFacts, payload.get("risk")),
        governance=_section(GovernanceFacts, payload.get("governance")),
        liquidity=_section(LiquidityFacts, payload.get("liquidity")),
        volatility=_section(VolatilityFacts, payload.get("volatility")),
        indicators=_section(IndicatorFacts, payload.get("indicators")),
        broker=_section(BrokerFacts, payload.get("broker")),
        timing=_section(TimingFacts, payload.get("timing")),
        outcome=_section(OutcomeFacts, payload.get("outcome")),
        evidence_custody=_section(EvidenceCustodyFacts, payload.get("evidence_custody")),
        revision=_section(RevisionFacts, payload.get("revision")),
        metadata=_section(MetadataFacts, payload.get("metadata")),
        content_hash=str(payload.get("content_hash") or ""),
    )
