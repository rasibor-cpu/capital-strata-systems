"""Canonical paper routing for CSS-Assisted, Copy a CSS Trader and CSS Autonomous Trading.

Every entry point ends in CopyTradeEngine, so every new paper position passes the same
chain (safety -> consent -> authority -> personality -> sizing incl. capital governors
and the optional CAD pilot envelope -> counts -> trade quality / CAIE -> R14F -> R7 ->
ExecutionGate (AntiBleed, margin, risk governor) -> paper validation pipeline). There is
no other way to open a position here, and nothing here can reach a broker.

Entry points
  on_trader_signal(envelope)   signed trader signal -> SignalFeed (registry, signature,
                               freshness, replay) -> each COPY follower with a mandate
                               for that trader
  on_css_engine_signal(signal) CSS engine signal -> AUTONOMOUS followers (decide now),
                               ASSISTED followers (proposal awaiting approval) and
                               SIMULATED followers (practice, no route)
  decide_proposal(...)         the user's individual approve/reject of one proposal
  submit_manual_order(...)     the user's own order; in CSS-Assisted it becomes a
                               proposal the user must then confirm
  run_exit_cycle(marks)        protective exits for open paper positions. Exempt from
                               consent and mandate state (risk-reducing).
  reconcile_orders()           (with an OMS) resolve orders from the venue's records and book
                               any fills not yet booked

Execution (optional, R2): with `oms` set, a COPIED decision is not filled at the model price.
It becomes one immediate-or-cancel order in the paper OMS and only the venue's reported fill
(quantity, price incl. slippage) is booked; rejected orders book nothing, partial fills book the
filled part, a dropped connection books nothing until reconciliation. An OMS emergency halt
rejects every new decision before evaluation. Without `oms` behaviour is unchanged.

Context is resolved server-side and fails closed: no current sign-on session, unknown
role, or an unreadable safety-flag provider rejects the follower with a recorded reason.
"""
from __future__ import annotations

import hashlib
import math
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.oms.paper_oms import OMSError, Order, OrderIntent, PaperOMS
from backend.trading_profiles.copy_engine import (
    AUTONOMOUS_SOURCE_ID,
    MANUAL_ORDER_PREFIX,
    CopyDecision,
    CopyTradeEngine,
    FollowerContext,
    ProposalError,
    SourceSignal,
    SystemContext,
)
from backend.trading_profiles.exits import CopiedPosition, evaluate_exit, realized_pnl
from backend.trading_profiles.limits import LimitsError, effective_policy
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.risk_personalities import RiskPersonality, policy_for
from backend.trading_profiles.market_assessment import MarketAssessmentStore
from backend.trading_profiles.signal_feed import SignalFeed, SignalFeedError

_CLIENT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
BOOK_SCHEMA = "css.trading_profiles.paper_book.v1"
DEFAULT_PAPER_EQUITY_CAD = 10_000.0
ROLE_RESOLVER = Callable[[str], str | None]
# -> (session_id, session_created_epoch) of the user's current sign-on, or None
SESSION_RESOLVER = Callable[[str], tuple[str, float] | None]
ASSESSMENT_PROVIDER = Callable[[str, str, str], Mapping[str, Any] | None]


class PaperBookError(RuntimeError):
    pass


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class PaperBook:
    """Persistent per-user paper account and open positions (realized-PnL equity)."""

    def __init__(self, root: Path | str, *, starting_equity: float = DEFAULT_PAPER_EQUITY_CAD,
                 pilot_envelope: bool = False) -> None:
        self.root = Path(root)
        self.path = self.root / "paper_book.json"
        self.lock_path = self.root / "paper_book.lock"
        self.starting_equity = float(starting_equity)
        self.pilot_envelope = bool(pilot_envelope)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": BOOK_SCHEMA, "accounts": {}, "positions": {}}
        try:
            doc = read_json_object(self.path)
        except PersistenceError as exc:
            raise PaperBookError(f"paper_book_unreadable:{exc}") from exc
        if doc.get("schema") != BOOK_SCHEMA:
            raise PaperBookError("paper_book_schema_mismatch")
        return doc

    def _mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            doc = self._read()
            out = fn(doc)
            atomic_write_json(self.path, doc, expected_root=self.root)
        return out

    def _new_account(self, now: datetime) -> dict[str, Any]:
        e = self.starting_equity
        return {"currency": "CAD", "equity": e, "equity_peak": e, "day": now.date().isoformat(),
                "day_start_equity": e, "pilot_envelope": self.pilot_envelope, "realized_pnl": 0.0, "fees": 0.0}

    def account(self, user_id: str, now: datetime) -> dict[str, Any]:
        def fn(doc):
            acct = doc["accounts"].setdefault(user_id, self._new_account(now))
            if acct["day"] != now.date().isoformat():  # daily-loss reference rolls at UTC midnight
                acct["day"], acct["day_start_equity"] = now.date().isoformat(), acct["equity"]
            return dict(acct)
        return self._mutate(fn)

    def positions(self, user_id: str | None = None) -> list[CopiedPosition]:
        out = []
        for rec in self._read()["positions"].values():
            if user_id is None or rec["position"]["follower_user_id"] == user_id:
                p = dict(rec["position"])
                p["opened_at"] = datetime.fromisoformat(p["opened_at"])
                out.append(CopiedPosition(**p))
        return sorted(out, key=lambda p: p.position_id)

    def position_meta(self, position_id: str) -> dict[str, Any]:
        return dict(self._read()["positions"][position_id]["meta"])

    def open(self, position: CopiedPosition, *, personality: str, entry_fee: float, fee_bps: float) -> None:
        def fn(doc):
            if position.position_id in doc["positions"]:
                raise PaperBookError("position_exists")
            rec = asdict(position)
            rec["opened_at"] = _iso(position.opened_at)
            doc["positions"][position.position_id] = {"position": rec, "meta": {
                "personality": personality, "fee_bps": fee_bps, "entry_fee": entry_fee}}
            acct = doc["accounts"][position.follower_user_id]
            acct["equity"] = round(acct["equity"] - entry_fee, 2)
            acct["fees"] = round(acct["fees"] + entry_fee, 2)
        self._mutate(fn)

    def update_best_price(self, position_id: str, best_price: float) -> None:
        def fn(doc):
            doc["positions"][position_id]["position"]["best_price"] = best_price
        self._mutate(fn)

    def close(self, position_id: str, pnl: float) -> None:
        def fn(doc):
            rec = doc["positions"].pop(position_id, None)
            if rec is None:
                raise PaperBookError("position_not_found")
            acct = doc["accounts"][rec["position"]["follower_user_id"]]
            acct["equity"] = round(acct["equity"] + pnl, 2)
            acct["realized_pnl"] = round(acct["realized_pnl"] + pnl, 2)
            acct["equity_peak"] = max(acct["equity_peak"], acct["equity"])
        self._mutate(fn)


@dataclass(frozen=True)
class RouteResult:
    signal_id: str
    accepted: bool
    reason: str
    decisions: tuple[CopyDecision, ...] = ()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TradingRouter:
    def __init__(
        self,
        engine: CopyTradeEngine,
        *,
        book: PaperBook,
        role_resolver: ROLE_RESOLVER,
        session_resolver: SESSION_RESOLVER,
        system_provider: Callable[[], SystemContext],
        feed: SignalFeed | None = None,
        assessment_provider: ASSESSMENT_PROVIDER | None = None,
        oms: PaperOMS | None = None,
    ) -> None:
        self.engine = engine
        self.book = book
        self.role_resolver = role_resolver
        self.session_resolver = session_resolver
        self.system_provider = system_provider
        self.feed = feed or SignalFeed(engine.root, engine.trader_registry)
        # CSS's own market view for manual orders, recorded from CSS engine signals (C3).
        self.assessments = MarketAssessmentStore(engine.root)
        self.assessment_provider = assessment_provider
        self.oms = oms

    # -- context (fail closed) ---------------------------------------------------
    def _system(self) -> SystemContext | None:
        try:
            system = self.system_provider()
        except Exception:
            return None
        return system if isinstance(system, SystemContext) else None

    def _follower(self, user_id: str, now: datetime, *, session: tuple[str, float] | None = None) -> FollowerContext | str:
        try:
            role = self.role_resolver(user_id)
            session = session or self.session_resolver(user_id)
            acct = self.book.account(user_id, now)
            positions = tuple(self.book.positions(user_id))
        except Exception as exc:
            return f"context_unavailable:{type(exc).__name__}"
        if not role:
            return "role_unknown"
        if not session:
            return "no_current_sign_on_session"
        return FollowerContext(
            user_id=user_id, role=str(role), session_id=str(session[0]), session_created_epoch=float(session[1]),
            equity=acct["equity"], equity_peak=acct["equity_peak"], day_start_equity=acct["day_start_equity"],
            buying_power=max(0.0, acct["equity"] - sum(p.notional for p in positions)),
            open_positions=positions, pilot_envelope=bool(acct["pilot_envelope"]), account_currency=acct["currency"])

    def _reject(self, signal: SourceSignal, user_id: str, reason: str, now: datetime) -> CopyDecision:
        decision = CopyDecision(user_id, signal.signal_id, "REJECTED", "routing", reason, None, None)
        self.engine._record(signal, decision, now)
        return decision

    def _decide(self, signal: SourceSignal, user_id: str, now: datetime, system: SystemContext | None,
                *, session: tuple[str, float] | None = None, requested_notional: float | None = None) -> CopyDecision:
        if system is None:
            return self._reject(signal, user_id, "safety_flags_unavailable", now)
        if self.oms is not None:
            try:
                halted = self.oms.halted
            except OMSError:
                return self._reject(signal, user_id, "oms_state_unavailable", now)
            if halted:
                return self._reject(signal, user_id, "oms_emergency_halt", now)
        follower = self._follower(user_id, now, session=session)
        if isinstance(follower, str):
            return self._reject(signal, user_id, follower, now)
        decision = self.engine.evaluate(signal, follower, system, now=now, requested_notional=requested_notional)
        self._book_fill(decision, signal, now)
        return decision

    def _book_fill(self, decision: CopyDecision, signal: SourceSignal, now: datetime) -> None:
        if not decision.copied:
            return
        position = self.engine.position_from_decision(decision, signal, opened_at=now)
        if self.oms is None:
            self.book.open(position, personality=str(decision.personality), entry_fee=float(decision.fill["fees"]),
                           fee_bps=signal.fee_bps)
            return
        # deterministic id: a retried decision can never produce a second order
        coid = "css-" + hashlib.sha256(position.position_id.encode()).hexdigest()[:32]
        intent = OrderIntent(coid, position.follower_user_id, position.symbol, position.side,
                             position.notional / position.entry_price, position.entry_price)
        rec = asdict(position)
        rec["opened_at"] = _iso(position.opened_at)
        try:
            order = self.oms.submit(intent, context={"position": rec, "personality": str(decision.personality),
                                                     "fee_bps": signal.fee_bps})
        except OMSError as exc:
            self.engine.ledger.append("ORDER_EXECUTION", {"position_id": position.position_id,
                                                          "follower_user_id": position.follower_user_id,
                                                          "outcome": "NOT_SUBMITTED", "reason": str(exc),
                                                          "at_utc": now.isoformat()})
            return
        self._book_order(order, now)

    def _book_order(self, order: Order, now: datetime) -> bool:
        """Book exactly what the venue filled, once. Returns True when a position was opened."""
        ctx = order.context
        if order.booked or not order.terminal or not ctx.get("position"):
            return False
        pos = dict(ctx["position"])
        filled = order.filled_qty > 0 and order.avg_price
        self.engine.ledger.append("ORDER_EXECUTION", {
            "position_id": pos["position_id"], "follower_user_id": pos["follower_user_id"],
            "client_order_id": order.intent.client_order_id, "venue_order_id": order.venue_order_id,
            "state": order.state.value, "reason": order.reason, "requested_qty": order.intent.quantity,
            "filled_qty": order.filled_qty, "avg_price": order.avg_price,
            "reference_price": order.intent.reference_price, "at_utc": now.isoformat()})
        if filled:
            notional = round(order.filled_qty * float(order.avg_price), 2)
            pos.update(notional=notional, entry_price=float(order.avg_price), best_price=float(order.avg_price),
                       opened_at=datetime.fromisoformat(pos["opened_at"]))
            try:
                self.book.open(CopiedPosition(**pos), personality=ctx["personality"],
                               entry_fee=round(notional * float(ctx["fee_bps"]) / 10_000.0, 2),
                               fee_bps=float(ctx["fee_bps"]))
            except PaperBookError as exc:
                if str(exc) != "position_exists":
                    raise
        self.oms.mark_booked(order.intent.client_order_id)
        return bool(filled)

    def reconcile_orders(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Resolve orders against the venue, then book every terminal fill not yet booked."""
        if self.oms is None:
            raise OMSError("no_oms_configured")
        now = now or _now()
        report = self.oms.reconcile()
        report["booked"] = [o.intent.client_order_id for o in self.oms.orders() if self._book_order(o, now)]
        report.pop("resolved_orders", None)
        return report

    def _users_in(self, modes: set[OperatingMode]) -> list[tuple[str, Any]]:
        out = []
        for uid in self.engine.preferences.user_ids():
            active = self.engine.preferences.get(uid).active
            if active is not None and active.operating_mode in modes:
                out.append((uid, active))
        return out

    # -- signal entry points ---------------------------------------------------------
    def on_trader_signal(self, envelope: Mapping[str, Any], *, now: datetime | None = None) -> RouteResult:
        now = now or _now()
        payload = envelope.get("payload") if isinstance(envelope, Mapping) else None
        sid = str((payload or {}).get("signal_id", "")) if isinstance(payload, Mapping) else ""
        try:
            signal = self.feed.ingest(envelope, now=now)
        except SignalFeedError as exc:
            return RouteResult(sid, False, str(exc))
        system = self._system()
        decisions = []
        for uid, active in self._users_in({OperatingMode.COPY_CSS_TRADER}):
            mandate = self.engine.mandates.get(active.mandate_id) if active.mandate_id else None
            if mandate is None or mandate.trader_id != signal.trader_id:
                continue  # this follower does not copy this trader
            decisions.append(self._decide(signal, uid, now, system))
        return RouteResult(signal.signal_id, True, "fanned_out", tuple(decisions))

    def on_css_engine_signal(self, signal: SourceSignal, *, now: datetime | None = None) -> RouteResult:
        now = now or _now()
        if signal.trader_id != AUTONOMOUS_SOURCE_ID:
            return RouteResult(signal.signal_id, False, "not_a_css_engine_signal")
        self.assessments.record(signal, now=now)
        system = self._system()
        modes = {OperatingMode.CSS_AUTONOMOUS_TRADING, OperatingMode.CSS_ASSISTED_TRADING, OperatingMode.SIMULATED_TRADING}
        decisions = tuple(self._decide(signal, uid, now, system) for uid, _ in self._users_in(modes))
        return RouteResult(signal.signal_id, True, "fanned_out", decisions)

    # -- user actions (identity from the caller's authenticated session) ---------------
    def decide_proposal(self, user_id: str, session: tuple[str, float], proposal_id: str, *, approve: bool,
                        now: datetime | None = None) -> CopyDecision:
        now = now or _now()
        system = self._system()
        if system is None:
            raise ProposalError("safety_flags_unavailable")
        follower = self._follower(user_id, now, session=session)
        if isinstance(follower, str):
            raise ProposalError(follower)
        proposal = self.engine._read_proposals().get(proposal_id)
        decision = self.engine.decide_proposal(proposal_id, follower, system, approve=approve, now=now)
        if proposal is not None:
            self._book_fill(decision, SourceSignal(**proposal["signal"]), now)
        return decision

    def submit_manual_order(self, user_id: str, session: tuple[str, float], order: Mapping[str, Any], *,
                            now: datetime | None = None) -> CopyDecision:
        """The user's own paper order: the user decides instrument, side, size and stop.

        CSS supplies only its fresh market assessment for that instrument and side (price,
        probability, expected move, costs) and enforces every platform limit; the user's size is
        a cap that CSS may reduce but never enlarge. No fresh assessment -> rejected. In
        CSS-Assisted mode the order becomes a proposal the user must confirm individually.
        """
        now = now or _now()
        symbol = str(order.get("symbol") or "").strip()[:32]
        asset = str(order.get("asset_class") or "").strip().upper()
        side = str(order.get("side") or "").strip().upper()
        client_id = str(order.get("client_order_id") or "")
        signal_id = "man-" + (client_id if _CLIENT_ID.match(client_id) else secrets.token_hex(8))
        base = dict(signal_id=signal_id, trader_id=MANUAL_ORDER_PREFIX + user_id, symbol=symbol or "?",
                    asset_class=asset or "?", side=side or "?")

        def stub_reject(reason: str) -> CopyDecision:
            stub = SourceSignal(**base, reference_price=1.0, probability=0.0, signal_score=0.0, confidence=0.0,
                                expected_move_bps=0.0, fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0,
                                stop_distance_pct=1.0, risk_reward=0.0)
            return self._reject(stub, user_id, reason, now)

        try:
            requested = float(order["notional"])
            stop = float(order["stop_distance_pct"])
        except (KeyError, TypeError, ValueError):
            return stub_reject("manual_order_requires_notional_and_stop")
        if not (math.isfinite(requested) and requested > 0 and math.isfinite(stop) and stop > 0):
            return stub_reject("manual_order_requires_notional_and_stop")
        try:
            if self.assessment_provider is not None:
                assessment = self.assessment_provider(symbol, asset, side)
            else:
                assessment = self.assessments.get(symbol, asset, side, now=now)
        except Exception:
            assessment = None
        if not assessment:
            return stub_reject("manual_order_requires_css_market_assessment")
        allowed = {"reference_price", "probability", "signal_score", "confidence", "expected_move_bps", "fee_bps",
                   "spread_bps", "slippage_bps", "risk_reward", "market_regime", "strategy_score", "replay_confidence",
                   "liquidity_score", "regime_alignment", "risk_score", "volatility_state", "regime_persistence"}
        try:
            signal = SourceSignal(**base, stop_distance_pct=stop, **{k: v for k, v in assessment.items() if k in allowed})
        except TypeError:
            return stub_reject("manual_order_requires_css_market_assessment")
        return self._decide(signal, user_id, now, self._system(), session=session, requested_notional=requested)

    # -- protective exits (never gated by consent, mandate or pause) ----------------------
    def run_exit_cycle(self, marks: Mapping[str, float], *, now: datetime | None = None,
                       source_exited: set[str] | frozenset[str] = frozenset()) -> list[dict[str, Any]]:
        now = now or _now()
        closed = []
        for position in self.book.positions():
            mark = marks.get(position.symbol)
            if mark is None or not mark > 0:
                continue  # no mark: hold, keep protection on the next cycle
            meta = self.book.position_meta(position.position_id)
            policy = policy_for(RiskPersonality.parse(meta["personality"]))
            active = self.engine.preferences.get(position.follower_user_id).active
            if active is not None:
                try:
                    policy = effective_policy(policy, active.limits)
                except LimitsError:
                    pass  # keep the personality's own exit rules
            exit_decision = evaluate_exit(position, policy, mark_price=mark, now=now,
                                          source_exited=position.trader_id in source_exited)
            if exit_decision.action != "EXIT":
                if exit_decision.best_price != position.best_price:
                    self.book.update_best_price(position.position_id, exit_decision.best_price)
                continue
            pnl = realized_pnl(position, mark, meta["fee_bps"])
            self.engine.record_exit(position, exit_price=mark, reason=exit_decision.reason, pnl=pnl, now=now)
            self.book.close(position.position_id, pnl)
            closed.append({"position_id": position.position_id, "user_id": position.follower_user_id,
                           "reason": exit_decision.reason, "pnl": pnl})
        return closed
