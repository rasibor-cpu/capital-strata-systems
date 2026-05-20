from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class EventSeverity(Enum):
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    CRITICAL = 5


class EventCategory(Enum):
    MONETARY_POLICY = "MONETARY_POLICY"
    INFLATION = "INFLATION"
    EMPLOYMENT = "EMPLOYMENT"
    GEOPOLITICAL = "GEOPOLITICAL"
    BANKING_STRESS = "BANKING_STRESS"
    REGULATORY = "REGULATORY"
    LIQUIDITY = "LIQUIDITY"
    EXCHANGE = "EXCHANGE"
    MARKET_SENTIMENT = "MARKET_SENTIMENT"
    EARNINGS = "EARNINGS"
    UNKNOWN = "UNKNOWN"


class RegimeState(Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    DEFENSIVE = "DEFENSIVE"
    PANIC = "PANIC"
    OPPORTUNITY_EXPANSION = "OPPORTUNITY_EXPANSION"
    LIQUIDITY_CRISIS = "LIQUIDITY_CRISIS"


class EventState(Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    STABILIZING = "STABILIZING"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


@dataclass
class IntelligenceEvent:
    event_id: str
    timestamp: datetime
    title: str
    category: EventCategory
    severity: EventSeverity
    confidence: float
    source: str
    affected_assets: List[str]
    description: str = ""
    active: bool = True
    expiration_time: Optional[datetime] = None
    event_state: EventState = EventState.NEW
    cooldown_until: Optional[datetime] = None
    raw_confidence: float = field(init=False)

    def __post_init__(self) -> None:
        try:
            self.event_state = EventState(self.event_state)
        except Exception:
            self.event_state = EventState.NEW
        try:
            self.raw_confidence = float(self.confidence)
        except (TypeError, ValueError):
            self.raw_confidence = 0.0

        self.confidence = self.raw_confidence
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 100.0:
            self.confidence = 100.0

        if self.affected_assets is None:
            self.affected_assets = []
        else:
            self.affected_assets = [str(item) for item in self.affected_assets]

        self.title = str(self.title)
        self.source = str(self.source)
        self.description = str(self.description)


@dataclass
class GovernanceResponse:
    reduce_allocation_pct: float = 0.0
    freeze_new_positions: bool = False
    freeze_options: bool = False
    suppress_scalping: bool = False
    max_open_positions: Optional[int] = None
    leverage_multiplier: float = 1.0
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        try:
            self.reduce_allocation_pct = float(self.reduce_allocation_pct)
        except (TypeError, ValueError):
            self.reduce_allocation_pct = 0.0

        if self.reduce_allocation_pct < 0.0:
            self.reduce_allocation_pct = 0.0
        elif self.reduce_allocation_pct > 100.0:
            self.reduce_allocation_pct = 100.0

        try:
            self.leverage_multiplier = float(self.leverage_multiplier)
        except (TypeError, ValueError):
            self.leverage_multiplier = 1.0

        if self.leverage_multiplier < 0.0:
            self.leverage_multiplier = 0.0
        elif self.leverage_multiplier > 2.0:
            self.leverage_multiplier = 2.0

        if self.notes is None:
            self.notes = []
        else:
            self.notes = [str(note) for note in self.notes]
