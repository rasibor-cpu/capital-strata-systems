"""CSS trade-origin model: CSS-recommended vs user-independent trades (Issue #102).

Classification happens once, when an order is created, from explicit evidence only:
- the order must carry the id of the CSS recommendation / Trade Card it acts on, and
- that card must exist in the recommendation registry, be unexpired at the user's action, and match the
  fingerprint the user saw.

No similarity matching, ever. An order without a recommendation reference is USER_INDEPENDENT even if it looks
exactly like a recommendation. A reference that cannot be verified is UNATTRIBUTED_REVIEW_REQUIRED, never guessed.

The resulting OriginEvidence is immutable (frozen dataclass) and is recorded once per order in an append-only
OriginLedger; a second, different classification for the same order is refused.

Material-change tolerances are a versioned policy (ORIGIN_POLICY_VERSION). They decide CSS_RECOMMENDED vs
CSS_RECOMMENDED_MODIFIED only; they never move a trade from USER_INDEPENDENT to a CSS origin.
This module does not place orders and does not touch execution, risk or governance gates.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Protocol, Tuple

log = logging.getLogger("css.trade_origin")

ORIGIN_POLICY_VERSION = "TO-1.0.0"


class TradeOrigin(str, Enum):
    CSS_RECOMMENDED = "CSS_RECOMMENDED"
    CSS_RECOMMENDED_MODIFIED = "CSS_RECOMMENDED_MODIFIED"
    USER_INDEPENDENT = "USER_INDEPENDENT"
    UNATTRIBUTED_REVIEW_REQUIRED = "UNATTRIBUTED_REVIEW_REQUIRED"


ORIGIN_LABELS = {
    TradeOrigin.CSS_RECOMMENDED: "CSS Recommended",
    TradeOrigin.CSS_RECOMMENDED_MODIFIED: "CSS Recommended (modified by you)",
    TradeOrigin.USER_INDEPENDENT: "Your own trade",
    TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED: "Origin under review",
}

# Material-change policy (owner-reviewable). Relative tolerances; anything beyond them is a modification.
MATERIAL_TOLERANCES = {
    "quantity_rel": 0.01,       # more than 1% change in size
    "limit_price_rel": 0.0025,  # more than 0.25% change in entry limit price
    "stop_price_rel": 0.0025,   # stop moved more than 0.25%, or removed
    "target_price_rel": 0.0025, # target moved more than 0.25%, or removed
}


class AttributionError(RuntimeError):
    """Raised when an attribution operation would require guessing."""


@dataclass(frozen=True)
class TradeCard:
    """A CSS recommendation as shown to the user. The fingerprint covers every field the user acts on."""
    recommendation_id: str
    symbol: str
    side: str                       # BUY / SELL
    quantity: float
    order_type: str                 # MARKET / LIMIT / STOP ...
    issued_at: datetime
    expires_at: datetime
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    trade_card_id: Optional[str] = None

    @property
    def fingerprint(self) -> str:
        core = {k: v for k, v in asdict(self).items() if k not in ("issued_at", "expires_at")}
        core["issued_at"] = self.issued_at.isoformat()
        return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()


class RecommendationRegistry(Protocol):
    def get(self, recommendation_id: str) -> Optional[TradeCard]: ...


class InMemoryRecommendationRegistry:
    def __init__(self) -> None:
        self._cards: Dict[str, TradeCard] = {}

    def add(self, card: TradeCard) -> None:
        if card.recommendation_id in self._cards and self._cards[card.recommendation_id] != card:
            raise AttributionError("recommendation ids are immutable")
        self._cards[card.recommendation_id] = card

    def get(self, recommendation_id: str) -> Optional[TradeCard]:
        return self._cards.get(recommendation_id)


@dataclass(frozen=True)
class OrderIntent:
    """What the user (or a governed CSS workflow) asks to place. recommendation_id and card_fingerprint are only
    present when the order was created from a Trade Card through the CSS workflow."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    action_at: datetime
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    recommendation_id: Optional[str] = None
    card_fingerprint: Optional[str] = None
    via_css_workflow: bool = False


@dataclass(frozen=True)
class OriginEvidence:
    origin: TradeOrigin
    order_id: str
    reason: str
    classified_at: datetime
    policy_version: str = ORIGIN_POLICY_VERSION
    recommendation_id: Optional[str] = None
    trade_card_id: Optional[str] = None
    card_fingerprint: Optional[str] = None
    deviations: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["origin"] = self.origin.value
        d["classified_at"] = self.classified_at.isoformat()
        d["deviations"] = list(self.deviations)
        return d


def _rel_change(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None and b is None:
        return 0.0
    if a is None or b is None:
        return None                 # added or removed
    if a == 0:
        return 0.0 if b == 0 else float("inf")
    return abs(b - a) / abs(a)


def deviations(card: TradeCard, order: OrderIntent) -> Tuple[str, ...]:
    out = []
    if order.order_type.upper() != card.order_type.upper():
        out.append(f"order_type {card.order_type}->{order.order_type}")
    checks = [("quantity", card.quantity, order.quantity, "quantity_rel"),
              ("limit_price", card.limit_price, order.limit_price, "limit_price_rel"),
              ("stop_price", card.stop_price, order.stop_price, "stop_price_rel"),
              ("target_price", card.target_price, order.target_price, "target_price_rel")]
    for name, a, b, tol in checks:
        ch = _rel_change(a, b)
        if ch is None:
            out.append(f"{name} {'removed' if b is None else 'added'}")
        elif ch > MATERIAL_TOLERANCES[tol]:
            out.append(f"{name} changed {ch:.2%}")
    return tuple(out)


def classify_order(order: OrderIntent, registry: RecommendationRegistry, now: datetime) -> OriginEvidence:
    """Classify an order at creation. Pure function of explicit evidence; never inspects price similarity to
    recommendations the order does not reference."""
    def ev(origin, reason, card=None, devs=()):
        e = OriginEvidence(origin=origin, order_id=order.order_id, reason=reason, classified_at=now,
                           recommendation_id=order.recommendation_id,
                           trade_card_id=card.trade_card_id if card else None,
                           card_fingerprint=card.fingerprint if card else order.card_fingerprint,
                           deviations=tuple(devs))
        log.info("trade origin %s order=%s reason=%s", origin.value, order.order_id, reason)
        return e

    if not order.recommendation_id:
        return ev(TradeOrigin.USER_INDEPENDENT, "No CSS recommendation referenced by the order.")
    if not order.via_css_workflow:
        return ev(TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED,
                  "Recommendation referenced outside the governed CSS workflow; cannot be verified.")
    card = registry.get(order.recommendation_id)
    if card is None:
        return ev(TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED, "Referenced recommendation not found in the registry.")
    if not order.card_fingerprint or order.card_fingerprint != card.fingerprint:
        return ev(TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED,
                  "Trade Card fingerprint does not match the recommendation on record.", card)
    if not (card.issued_at <= order.action_at <= card.expires_at):
        return ev(TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED, "User action outside the recommendation's validity window.",
                  card)
    if order.symbol.upper() != card.symbol.upper() or order.side.upper() != card.side.upper():
        return ev(TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED,
                  "Symbol or side differs from the referenced recommendation.", card)
    devs = deviations(card, order)
    if devs:
        return ev(TradeOrigin.CSS_RECOMMENDED_MODIFIED, "User acted on a CSS recommendation with material changes.",
                  card, devs)
    return ev(TradeOrigin.CSS_RECOMMENDED, "Confirmed CSS recommendation through the governed workflow.", card)


class OriginLedger:
    """Append-only: one OriginEvidence per order id. Re-recording identical evidence is a no-op; different
    evidence is refused (origins are never rewritten after the fact)."""

    def __init__(self) -> None:
        self._by_order: Dict[str, OriginEvidence] = {}

    def record(self, evidence: OriginEvidence) -> OriginEvidence:
        prior = self._by_order.get(evidence.order_id)
        if prior is not None and prior != evidence:
            raise AttributionError(f"origin for order {evidence.order_id} is already recorded and immutable")
        self._by_order[evidence.order_id] = evidence
        return evidence

    def get(self, order_id: str) -> Optional[OriginEvidence]:
        return self._by_order.get(order_id)

    def require(self, order_id: str) -> OriginEvidence:
        e = self._by_order.get(order_id)
        if e is None:
            raise AttributionError(f"no recorded origin for order {order_id}")
        return e
