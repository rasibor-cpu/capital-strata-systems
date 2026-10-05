"""CSS trade-origin attribution model (Issue #102), policy TO-2.0.0.

Four user-facing states:
  CSS_RECOMMENDED           "CSS Recommended"
  CSS_RECOMMENDED_MODIFIED  "CSS Recommended — Modified by You"
  USER_INDEPENDENT          "Your Own Trade"
  ORIGIN_UNDER_REVIEW       "Origin Under Review"

Principles
- Evidence only. An order is CSS-attributable only if it carries the id, version and fingerprint of a CSS
  recommendation it was created from through the governed CSS workflow. No fuzzy or similarity matching, ever.
- Materiality is measured against the recommendation's own validity envelope (entry zone, fill-slippage limit, stop,
  leverage, validity window), not against global magic numbers.
- Policy values that need an owner/compliance decision are explicit fields; while undecided (None) any deviation that
  depends on them is routed to ORIGIN_UNDER_REVIEW, never guessed.
- Every determination is a frozen AttributionRecord holding all inputs (recommendation snapshot, order snapshot,
  policy snapshot + hash), so `reproduce()` recomputes the same result.
- State changes after classification are explicit, actor-attributed, append-only transitions on the OriginLedger.
  USER_INDEPENDENT can never become a CSS state. Nothing is reassigned silently.

This module does not place orders and does not touch execution, risk or governance gates.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Protocol, Tuple

log = logging.getLogger("css.trade_origin")

ORIGIN_POLICY_VERSION = "TO-2.0.0"


class TradeOrigin(str, Enum):
    CSS_RECOMMENDED = "CSS_RECOMMENDED"
    CSS_RECOMMENDED_MODIFIED = "CSS_RECOMMENDED_MODIFIED"
    USER_INDEPENDENT = "USER_INDEPENDENT"
    ORIGIN_UNDER_REVIEW = "ORIGIN_UNDER_REVIEW"

    @classmethod
    def parse(cls, raw: str) -> "TradeOrigin":
        raw = str(raw or "").upper()
        if raw == "UNATTRIBUTED_REVIEW_REQUIRED":          # TO-1.0.0 name, never deployed
            return cls.ORIGIN_UNDER_REVIEW
        return cls(raw) if raw in cls.__members__ else cls.ORIGIN_UNDER_REVIEW


ORIGIN_LABELS = {
    TradeOrigin.CSS_RECOMMENDED: "CSS Recommended",
    TradeOrigin.CSS_RECOMMENDED_MODIFIED: "CSS Recommended — Modified by You",
    TradeOrigin.USER_INDEPENDENT: "Your Own Trade",
    TradeOrigin.ORIGIN_UNDER_REVIEW: "Origin Under Review",
}


class Severity(str, Enum):
    NON_MATERIAL = "NON_MATERIAL"       # preserves the thesis and stays inside the governed risk envelope
    MATERIAL = "MATERIAL"               # changes exposure/risk/entry/validity beyond the envelope
    THESIS_BREAK = "THESIS_BREAK"       # different direction or instrument: not the recommended idea any more
    POLICY_PENDING = "POLICY_PENDING"   # depends on a policy value not yet decided by the owner/compliance


class AttributionError(RuntimeError):
    """Raised when an attribution operation would require guessing or an illegal state change."""


# ---------------------------------------------------------------------------------------------- policy
@dataclass(frozen=True)
class MaterialityPolicy:
    """Material-deviation policy. Defaults are conservative and documented in ATTRIBUTION_SPEC.md; None = TBD by the
    owner/compliance (any deviation needing that value goes to ORIGIN_UNDER_REVIEW)."""
    version: str = ORIGIN_POLICY_VERSION
    # Size: a smaller position keeps the thesis and lowers risk. Increases are measured against the recommended size.
    size_decrease_is_material: bool = False
    size_increase_allowance: Optional[float] = 0.0          # relative; 0.0 = any increase is material (owner may raise)
    # Leverage above the recommendation's leverage (default 1x) increases exposure.
    leverage_increase_allowance: Optional[float] = 0.0      # absolute multiple above recommended leverage
    # Entry: inside the card's entry zone is non-material. If a card has no zone, this fallback (bps around the
    # recommended limit) applies; None = TBD.
    entry_fallback_tolerance_bps: Optional[float] = None
    # Fill quality: inside the card's max_slippage_bps is non-material. Fallback when the card has none; None = TBD.
    fill_slippage_fallback_bps: Optional[float] = None
    # Stop: tighter stops lower risk. Widening beyond the card's own stop_tolerance_bps (or this fallback) is
    # material; removing the stop is always material.
    stop_widening_fallback_bps: Optional[float] = 0.0       # 0.0 = any widening is material when the card is silent
    # Target changes don't change the risk envelope but do change the idea's payoff. TBD.
    target_change_material: Optional[bool] = None
    # Disposition of an executed-after-expiry order (directive: material).
    expired_disposition: TradeOrigin = TradeOrigin.CSS_RECOMMENDED_MODIFIED
    # Disposition of a direction or instrument change. TBD between MODIFIED and USER_INDEPENDENT; review until then.
    thesis_break_disposition: Optional[TradeOrigin] = None

    def pending_decisions(self) -> List[str]:
        return [f.name for f in fields(self) if getattr(self, f.name) is None]

    def snapshot(self) -> dict:
        return {f.name: (getattr(self, f.name).value if isinstance(getattr(self, f.name), Enum) else getattr(self, f.name))
                for f in fields(self)}

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()


DEFAULT_POLICY = MaterialityPolicy()


# ---------------------------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class TradeCard:
    """A CSS recommendation (one version of it) exactly as shown to the user, including its validity envelope."""
    recommendation_id: str
    symbol: str
    side: str                              # BUY / SELL
    quantity: float                        # recommended size
    order_type: str
    issued_at: datetime
    valid_until: datetime
    version: int = 1
    limit_price: Optional[float] = None
    entry_low: Optional[float] = None      # entry zone (envelope)
    entry_high: Optional[float] = None
    max_slippage_bps: Optional[float] = None
    stop_price: Optional[float] = None
    stop_tolerance_bps: Optional[float] = None
    target_price: Optional[float] = None
    leverage: float = 1.0
    trade_card_id: Optional[str] = None

    def snapshot(self) -> dict:
        d = asdict(self)
        d["issued_at"], d["valid_until"] = self.issued_at.isoformat(), self.valid_until.isoformat()
        return d

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True, default=str).encode()).hexdigest()


class RecommendationRegistry(Protocol):
    def get(self, recommendation_id: str, version: int) -> Optional[TradeCard]: ...


class InMemoryRecommendationRegistry:
    """Versioned and immutable: a (id, version) pair can be registered once."""

    def __init__(self) -> None:
        self._cards: Dict[Tuple[str, int], TradeCard] = {}

    def add(self, card: TradeCard) -> None:
        key = (card.recommendation_id, card.version)
        if key in self._cards and self._cards[key] != card:
            raise AttributionError("a recommendation version is immutable; issue a new version instead")
        self._cards[key] = card

    def get(self, recommendation_id: str, version: int) -> Optional[TradeCard]:
        return self._cards.get((recommendation_id, version))


@dataclass(frozen=True)
class OrderIntent:
    """What is submitted for execution. Recommendation fields are present only when the order was created from a
    Trade Card through the CSS workflow."""
    order_id: str
    user_key: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    action_at: datetime
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    leverage: float = 1.0
    recommendation_id: Optional[str] = None
    recommendation_version: Optional[int] = None
    card_fingerprint: Optional[str] = None
    via_css_workflow: bool = False

    def snapshot(self) -> dict:
        d = asdict(self)
        d["action_at"] = self.action_at.isoformat()
        return d


@dataclass(frozen=True)
class Deviation:
    field: str
    severity: Severity
    recommended: Optional[str]
    executed: Optional[str]
    note: str

    def to_dict(self) -> dict:
        return {"field": self.field, "severity": self.severity.value, "recommended": self.recommended,
                "executed": self.executed, "note": self.note}


@dataclass(frozen=True)
class AttributionRecord:
    """Immutable, self-contained evidence for one determination."""
    order_id: str
    user_key: str
    origin: TradeOrigin
    reason: str
    determined_at: datetime
    stage: str                                  # "order_creation" or "fill"
    symbol: str
    side: str
    order: dict                                 # executed/requested parameters snapshot
    recommendation: Optional[dict]              # recommendation snapshot (incl. id/version) or None
    deviations: Tuple[Deviation, ...]
    policy: dict
    policy_version: str
    policy_fingerprint: str
    recommendation_id: Optional[str] = None
    recommendation_version: Optional[int] = None
    trade_card_id: Optional[str] = None
    card_fingerprint: Optional[str] = None

    def to_dict(self) -> dict:
        return {"order_id": self.order_id, "user_key": self.user_key, "origin": self.origin.value,
                "label": ORIGIN_LABELS[self.origin], "reason": self.reason, "determined_at": self.determined_at.isoformat(),
                "stage": self.stage, "symbol": self.symbol, "side": self.side, "order": self.order,
                "recommendation": self.recommendation, "deviations": [d.to_dict() for d in self.deviations],
                "policy_version": self.policy_version, "policy_fingerprint": self.policy_fingerprint,
                "recommendation_id": self.recommendation_id, "recommendation_version": self.recommendation_version,
                "trade_card_id": self.trade_card_id, "card_fingerprint": self.card_fingerprint}


# ---------------------------------------------------------------------------------------------- deviations
def _bps(a: float, b: float) -> float:
    return abs(b - a) / abs(a) * 10_000 if a else float("inf")


def assess_deviations(card: TradeCard, order: OrderIntent, policy: MaterialityPolicy) -> List[Deviation]:
    out: List[Deviation] = []
    add = lambda f, sev, r, e, note: out.append(Deviation(f, sev, None if r is None else str(r), None if e is None else str(e), note))

    # Thesis: direction and instrument
    if order.symbol.upper() != card.symbol.upper():
        add("symbol", Severity.THESIS_BREAK, card.symbol, order.symbol, "Different instrument from the recommendation")
    if order.side.upper() != card.side.upper():
        add("side", Severity.THESIS_BREAK, card.side, order.side, "Opposite direction to the recommendation")

    # Validity window
    if order.action_at > card.valid_until:
        add("valid_until", Severity.MATERIAL, card.valid_until.isoformat(), order.action_at.isoformat(),
            "Executed after the recommendation expired")
    if order.action_at < card.issued_at:
        add("issued_at", Severity.THESIS_BREAK, card.issued_at.isoformat(), order.action_at.isoformat(),
            "Order time precedes the recommendation")

    # Size
    if order.quantity < card.quantity:
        add("quantity", Severity.MATERIAL if policy.size_decrease_is_material else Severity.NON_MATERIAL,
            card.quantity, order.quantity, "Smaller than recommended (less exposure)")
    elif order.quantity > card.quantity:
        rel = (order.quantity - card.quantity) / card.quantity
        if policy.size_increase_allowance is None:
            add("quantity", Severity.POLICY_PENDING, card.quantity, order.quantity, "Size increase; allowance not yet decided")
        else:
            add("quantity", Severity.MATERIAL if rel > policy.size_increase_allowance else Severity.NON_MATERIAL,
                card.quantity, order.quantity, f"Larger than recommended (+{rel:.1%})")

    # Leverage
    if order.leverage > card.leverage:
        if policy.leverage_increase_allowance is None:
            add("leverage", Severity.POLICY_PENDING, card.leverage, order.leverage, "Leverage increase; allowance not yet decided")
        else:
            add("leverage", Severity.MATERIAL if order.leverage - card.leverage > policy.leverage_increase_allowance
                else Severity.NON_MATERIAL, card.leverage, order.leverage, "More leverage than recommended")

    # Entry vs envelope (limit orders: the limit price; market orders are checked at fill)
    if order.limit_price is not None:
        lo, hi = card.entry_low, card.entry_high
        if lo is None or hi is None:
            if card.limit_price is None or order.limit_price == card.limit_price:
                lo = hi = order.limit_price if card.limit_price is None else card.limit_price
            elif policy.entry_fallback_tolerance_bps is None:
                add("entry", Severity.POLICY_PENDING, card.limit_price, order.limit_price,
                    "Entry differs; card has no entry zone and the fallback tolerance is not yet decided")
                lo = hi = None
            else:
                tol = card.limit_price * policy.entry_fallback_tolerance_bps / 10_000
                lo, hi = card.limit_price - tol, card.limit_price + tol
        if lo is not None and hi is not None:
            inside = lo <= order.limit_price <= hi
            better = (order.side.upper() == "BUY" and order.limit_price < lo) or \
                     (order.side.upper() == "SELL" and order.limit_price > hi)
            if not inside:
                add("entry", Severity.MATERIAL if not better else Severity.NON_MATERIAL, f"{lo}–{hi}", order.limit_price,
                    "Entry better than the zone (may not fill)" if better else "Entry outside the recommendation's zone")

    # Stop
    if card.stop_price is not None:
        if order.stop_price is None:
            add("stop_price", Severity.MATERIAL, card.stop_price, None, "Stop removed")
        elif order.stop_price != card.stop_price:
            long = card.side.upper() == "BUY"
            widened = order.stop_price < card.stop_price if long else order.stop_price > card.stop_price
            if not widened:
                add("stop_price", Severity.NON_MATERIAL, card.stop_price, order.stop_price, "Stop tightened (less risk)")
            else:
                allowance = card.stop_tolerance_bps if card.stop_tolerance_bps is not None else policy.stop_widening_fallback_bps
                if allowance is None:
                    add("stop_price", Severity.POLICY_PENDING, card.stop_price, order.stop_price,
                        "Stop widened; allowance not yet decided")
                else:
                    add("stop_price", Severity.MATERIAL if _bps(card.stop_price, order.stop_price) > allowance
                        else Severity.NON_MATERIAL, card.stop_price, order.stop_price, "Stop widened (more risk)")

    # Target
    if card.target_price is not None and order.target_price != card.target_price:
        if policy.target_change_material is None:
            add("target_price", Severity.POLICY_PENDING, card.target_price, order.target_price,
                "Target changed; treatment not yet decided")
        else:
            add("target_price", Severity.MATERIAL if policy.target_change_material else Severity.NON_MATERIAL,
                card.target_price, order.target_price, "Target changed")
    return out


def _resolve(devs: List[Deviation], policy: MaterialityPolicy) -> Tuple[TradeOrigin, str]:
    sev = {d.severity for d in devs}
    if Severity.THESIS_BREAK in sev:
        if policy.thesis_break_disposition is None:
            return TradeOrigin.ORIGIN_UNDER_REVIEW, "Direction/instrument differs from the recommendation; disposition not yet decided"
        return policy.thesis_break_disposition, "Direction/instrument differs from the recommendation (policy disposition)"
    if Severity.POLICY_PENDING in sev:
        return TradeOrigin.ORIGIN_UNDER_REVIEW, "A deviation depends on a policy value not yet decided"
    if any(d.field == "valid_until" for d in devs):
        return policy.expired_disposition, "Executed after the recommendation expired"
    if Severity.MATERIAL in sev:
        return TradeOrigin.CSS_RECOMMENDED_MODIFIED, "Acted on a CSS recommendation with material changes"
    if devs:
        return TradeOrigin.CSS_RECOMMENDED, "Acted on a CSS recommendation; only non-material changes"
    return TradeOrigin.CSS_RECOMMENDED, "Acted on a CSS recommendation as recommended"


# ---------------------------------------------------------------------------------------------- classification
def classify_order(order: OrderIntent, registry: RecommendationRegistry, now: datetime,
                   policy: MaterialityPolicy = DEFAULT_POLICY) -> AttributionRecord:
    """Classify once, at order creation, from explicit evidence only."""
    card = None
    devs: List[Deviation] = []
    if not order.recommendation_id:
        origin, reason = TradeOrigin.USER_INDEPENDENT, "No CSS recommendation referenced by the order"
    elif not order.via_css_workflow:
        origin, reason = TradeOrigin.ORIGIN_UNDER_REVIEW, "Recommendation referenced outside the governed CSS workflow"
    elif order.recommendation_version is None:
        origin, reason = TradeOrigin.ORIGIN_UNDER_REVIEW, "Recommendation version missing"
    else:
        card = registry.get(order.recommendation_id, order.recommendation_version)
        if card is None:
            origin, reason = TradeOrigin.ORIGIN_UNDER_REVIEW, "Referenced recommendation version not found"
        elif not order.card_fingerprint or order.card_fingerprint != card.fingerprint:
            origin, reason = TradeOrigin.ORIGIN_UNDER_REVIEW, "Trade Card fingerprint does not match the recommendation on record"
        else:
            devs = assess_deviations(card, order, policy)
            origin, reason = _resolve(devs, policy)
    rec = AttributionRecord(
        order_id=order.order_id, user_key=order.user_key, origin=origin, reason=reason, determined_at=now,
        stage="order_creation", symbol=order.symbol, side=order.side, order=order.snapshot(),
        recommendation=card.snapshot() if card else None, deviations=tuple(devs), policy=policy.snapshot(),
        policy_version=policy.version, policy_fingerprint=policy.fingerprint,
        recommendation_id=order.recommendation_id, recommendation_version=order.recommendation_version,
        trade_card_id=card.trade_card_id if card else None,
        card_fingerprint=card.fingerprint if card else order.card_fingerprint)
    log.info("trade origin %s order=%s reason=%s", origin.value, order.order_id, reason)
    return rec


def reproduce(record: AttributionRecord) -> Tuple[TradeOrigin, Tuple[Deviation, ...]]:
    """Recompute an order-creation determination from the record alone (recommendation, order and policy snapshots)."""
    if record.stage != "order_creation":
        raise AttributionError("only order-creation records are reproduced this way")
    o = dict(record.order)
    o["action_at"] = datetime.fromisoformat(o["action_at"])
    order = OrderIntent(**o)
    pol = dict(record.policy)
    for k in ("expired_disposition", "thesis_break_disposition"):
        pol[k] = TradeOrigin(pol[k]) if pol[k] is not None else None
    policy = MaterialityPolicy(**pol)
    reg = InMemoryRecommendationRegistry()
    if record.recommendation:
        r = dict(record.recommendation)
        r["issued_at"], r["valid_until"] = datetime.fromisoformat(r["issued_at"]), datetime.fromisoformat(r["valid_until"])
        reg.add(TradeCard(**r))
    again = classify_order(order, reg, record.determined_at, policy)
    return again.origin, again.deviations


def assess_fill(record: AttributionRecord, card: Optional[TradeCard], fill_price: float,
                policy: MaterialityPolicy = DEFAULT_POLICY) -> Optional[Deviation]:
    """Execution-quality check at fill for CSS-attributed orders. Returns a deviation when the fill falls outside the
    recommendation's envelope (slippage), else None. The caller records any resulting state change explicitly."""
    if record.origin not in (TradeOrigin.CSS_RECOMMENDED, TradeOrigin.CSS_RECOMMENDED_MODIFIED) or card is None:
        return None
    ref = card.limit_price if card.limit_price is not None else (
        (card.entry_low + card.entry_high) / 2 if card.entry_low is not None and card.entry_high is not None else None)
    if ref is None:
        return None
    adverse = (fill_price > ref) if card.side.upper() == "BUY" else (fill_price < ref)
    if not adverse:
        return None
    if card.entry_low is not None and card.entry_high is not None and card.entry_low <= fill_price <= card.entry_high:
        return None
    limit = card.max_slippage_bps if card.max_slippage_bps is not None else policy.fill_slippage_fallback_bps
    slip = _bps(ref, fill_price)
    if limit is None:
        return Deviation("fill_price", Severity.POLICY_PENDING, str(ref), str(fill_price),
                         f"Fill {slip:.1f} bps from reference; slippage limit not yet decided")
    if slip > limit:
        return Deviation("fill_price", Severity.MATERIAL, str(ref), str(fill_price),
                         f"Fill slippage {slip:.1f} bps exceeds the {limit:.1f} bps envelope")
    return None


# ---------------------------------------------------------------------------------------------- state machine
ALLOWED_TRANSITIONS = {
    # from -> {to: who may make it}
    TradeOrigin.CSS_RECOMMENDED: {TradeOrigin.CSS_RECOMMENDED_MODIFIED: "system", TradeOrigin.ORIGIN_UNDER_REVIEW: "system"},
    TradeOrigin.CSS_RECOMMENDED_MODIFIED: {TradeOrigin.ORIGIN_UNDER_REVIEW: "system"},
    TradeOrigin.ORIGIN_UNDER_REVIEW: {TradeOrigin.CSS_RECOMMENDED: "reviewer", TradeOrigin.CSS_RECOMMENDED_MODIFIED: "reviewer",
                                      TradeOrigin.USER_INDEPENDENT: "reviewer"},
    TradeOrigin.USER_INDEPENDENT: {},   # terminal: a user's own trade is never re-attributed to CSS
}


@dataclass(frozen=True)
class Transition:
    order_id: str
    from_origin: TradeOrigin
    to_origin: TradeOrigin
    at: datetime
    actor: str                     # "system:<component>" or "reviewer:<id>"
    reason: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"order_id": self.order_id, "from": self.from_origin.value, "to": self.to_origin.value,
                "at": self.at.isoformat(), "actor": self.actor, "reason": self.reason, "evidence": self.evidence}


class OriginLedger:
    """Append-only. One initial AttributionRecord per order, then explicit transitions. Current state = last entry."""

    def __init__(self) -> None:
        self._records: Dict[str, AttributionRecord] = {}
        self._transitions: Dict[str, List[Transition]] = {}

    def record(self, rec: AttributionRecord) -> AttributionRecord:
        prior = self._records.get(rec.order_id)
        if prior is not None and prior != rec:
            raise AttributionError(f"origin for order {rec.order_id} is already recorded; use an explicit transition")
        self._records[rec.order_id] = rec
        self._transitions.setdefault(rec.order_id, [])
        return rec

    def get(self, order_id: str) -> Optional[AttributionRecord]:
        return self._records.get(order_id)

    def require(self, order_id: str) -> AttributionRecord:
        r = self._records.get(order_id)
        if r is None:
            raise AttributionError(f"no recorded origin for order {order_id}")
        return r

    def current(self, order_id: str) -> TradeOrigin:
        t = self._transitions.get(order_id) or []
        return t[-1].to_origin if t else self.require(order_id).origin

    def history(self, order_id: str) -> List[dict]:
        r = self.require(order_id)
        return [{"origin": r.origin.value, "at": r.determined_at.isoformat(), "actor": "system:classifier",
                 "reason": r.reason}] + [t.to_dict() for t in self._transitions.get(order_id, [])]

    def transition(self, order_id: str, to: TradeOrigin, at: datetime, actor: str, reason: str,
                   evidence: Optional[dict] = None) -> Transition:
        frm = self.current(order_id)
        allowed = ALLOWED_TRANSITIONS[frm]
        if to not in allowed:
            raise AttributionError(f"{frm.value} -> {to.value} is not an allowed transition")
        kind = allowed[to]
        if not actor.startswith(kind + ":"):
            raise AttributionError(f"{frm.value} -> {to.value} must be made by a {kind}")
        if not reason.strip():
            raise AttributionError("a transition needs a reason")
        if kind == "reviewer" and not evidence:
            raise AttributionError("a review resolution needs supporting evidence")
        t = Transition(order_id, frm, to, at, actor, reason, dict(evidence or {}))
        self._transitions[order_id].append(t)
        log.info("trade origin transition order=%s %s->%s by %s", order_id, frm.value, to.value, actor)
        return t

    def apply_fill_check(self, order_id: str, card: Optional[TradeCard], fill_price: float, at: datetime,
                         policy: MaterialityPolicy = DEFAULT_POLICY) -> Optional[Transition]:
        """Fill-time envelope check. A material slippage moves CSS_RECOMMENDED to MODIFIED; a pending policy value
        moves it to review. Each is an explicit, evidenced transition."""
        rec = self.require(order_id)
        dev = assess_fill(replace(rec, origin=self.current(order_id)), card, fill_price, policy)
        if dev is None:
            return None
        cur = self.current(order_id)
        target = TradeOrigin.ORIGIN_UNDER_REVIEW if dev.severity is Severity.POLICY_PENDING else TradeOrigin.CSS_RECOMMENDED_MODIFIED
        if target == cur or target not in ALLOWED_TRANSITIONS[cur]:
            return None
        return self.transition(order_id, target, at, "system:fill_check", dev.note, {"deviation": dev.to_dict(),
                                                                                    "policy_version": policy.version})
