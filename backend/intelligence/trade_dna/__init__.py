"""DIP-002 Trade DNA Foundation — immutable evidence schema (facts only).

Does not capture live executions or modify ExecutionGate / trading behaviour.
"""

from __future__ import annotations

from backend.intelligence.trade_dna.advisory import AdvisoryConclusion, build_advisory_conclusion
from backend.intelligence.trade_dna.constants import (
    ADVISORY_VERSION,
    ANALYSIS_VERSION,
    EVIDENCE_VERSION,
    LAYER_ADVISORY,
    LAYER_DERIVED,
    LAYER_FACTS,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics, assert_not_embedded_in_facts
from backend.intelligence.trade_dna.evidence_graph import (
    EvidenceGraphError,
    EvidenceGraphNode,
    build_evidence_graph,
)
from backend.intelligence.trade_dna.hashing import compute_content_hash, verify_content_hash
from backend.intelligence.trade_dna.revisions import AppendOnlyDNAStore
from backend.intelligence.trade_dna.schema import (
    BrokerFacts,
    EvidenceCustodyFacts,
    ExecutionFacts,
    GovernanceFacts,
    IndicatorFacts,
    LiquidityFacts,
    MarketFacts,
    MetadataFacts,
    OutcomeFacts,
    RevisionFacts,
    RiskFacts,
    StrategyFacts,
    TimingFacts,
    TradeDNARecord,
    TradeIdentityFacts,
    VolatilityFacts,
    trade_dna_from_dict,
)
from backend.intelligence.trade_dna.serialization import deserialize_trade_dna, serialize_trade_dna
from backend.intelligence.trade_dna.validation import TradeDNAValidationError, validate_trade_dna

__all__ = [
    "ADVISORY_VERSION",
    "ANALYSIS_VERSION",
    "EVIDENCE_VERSION",
    "LAYER_ADVISORY",
    "LAYER_DERIVED",
    "LAYER_FACTS",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "AdvisoryConclusion",
    "AppendOnlyDNAStore",
    "BrokerFacts",
    "DerivedTradeMetrics",
    "EvidenceCustodyFacts",
    "EvidenceGraphError",
    "EvidenceGraphNode",
    "ExecutionFacts",
    "GovernanceFacts",
    "IndicatorFacts",
    "LiquidityFacts",
    "MarketFacts",
    "MetadataFacts",
    "OutcomeFacts",
    "RevisionFacts",
    "RiskFacts",
    "StrategyFacts",
    "TimingFacts",
    "TradeDNARecord",
    "TradeDNAValidationError",
    "TradeIdentityFacts",
    "VolatilityFacts",
    "assert_not_embedded_in_facts",
    "build_advisory_conclusion",
    "build_evidence_graph",
    "compute_content_hash",
    "deserialize_trade_dna",
    "serialize_trade_dna",
    "trade_dna_from_dict",
    "validate_trade_dna",
    "verify_content_hash",
]
