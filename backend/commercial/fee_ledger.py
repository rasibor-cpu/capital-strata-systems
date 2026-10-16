"""CSS commercial fee accrual ledger (paper accounting only; no money moves).

Policy implemented (owner terms are read from the user's accepted account profile):

1. Attribution. Every closed paper position is classified exactly once:
     CSS          the signal came from CSS (trader_id == CSS_AUTONOMOUS_ENGINE): Autonomous, or
                  Assisted proposals the user confirmed.
     INDEPENDENT  the user's own order (trader_id starts with USER_MANUAL:), even if CSS supplied
                  the market assessment: the user chose instrument, side, size and stop.
     COPY_TRADER  a third-party approved trader's signal. Not CSS-attributable unless the owner
                  enables copy_trades_attributable (open owner decision); otherwise no fee.
2. CSS commission is charged ONLY on profit, and ONLY on profit above the loss-recovery hurdle:
   cumulative CSS-attributable net P&L must exceed its previous high-water mark. Losses raise the
   hurdle; later profits first recover them. For every basis the fee is capped at the
   hurdle-clearing profit of that trade, so a fee can never exceed what the trade earned above
   the hurdle (PERCENT_PROFIT: rate% of it; FIXED_PER_TRADE / PERCENT_NOTIONAL: that amount,
   capped).
3. Independent trades pay only the configured independent-trade platform fee (NONE,
   FIXED_PER_TRADE or PERCENT_NOTIONAL), regardless of P&L, and never touch the CSS hurdle.
4. Terms must be ACCEPTED by the user; otherwise the trade is recorded with no fee.
5. Idempotency: one TRADE_CLOSED entry per position_id. Re-posting identical data is a no-op;
   conflicting data is refused.
6. Reversals (busted/voided trades) are SUPER_USER actions. Fees are always derivable by replaying
   non-reversed trades in order; reconcile() posts ADJUSTMENT entries so that charged fees equal
   the replayed fees exactly (refunding or re-accruing the difference).
7. Refunds (goodwill) are SUPER_USER actions, bounded by the user's net fees.
8. Every entry is hash-chained (tamper-evident). Amounts are Decimal strings, rounded DOWN to
   cents in the customer's favour. Nothing here collects, transfers or charges real money.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, MANUAL_ORDER_PREFIX
from backend.trading_profiles.hash_chain import HashChainLog

CENT = Decimal("0.01")
ZERO = Decimal("0")
SUPER_USER = "SUPER_USER"
CSS, INDEPENDENT, COPY_TRADER = "CSS", "INDEPENDENT", "COPY_TRADER"


class FeeLedgerError(RuntimeError):
    pass


def _dec(value: Any, field: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FeeLedgerError(f"invalid_decimal:{field}") from exc
    if not d.is_finite():
        raise FeeLedgerError(f"invalid_decimal:{field}")
    return d


def _cents(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_DOWN)


def classify(trader_id: str, *, copy_trades_attributable: bool = False) -> str:
    tid = str(trader_id or "")
    if tid == AUTONOMOUS_SOURCE_ID:
        return CSS
    if tid.startswith(MANUAL_ORDER_PREFIX):
        return INDEPENDENT
    return CSS if copy_trades_attributable else COPY_TRADER


@dataclass(frozen=True)
class Terms:
    accepted: bool
    commission_basis: str = "NONE"       # NONE | PERCENT_PROFIT | FIXED_PER_TRADE | PERCENT_NOTIONAL
    commission_rate: Decimal = ZERO      # percent for PERCENT_*, currency amount for FIXED_*
    independent_basis: str = "NONE"      # NONE | FIXED_PER_TRADE | PERCENT_NOTIONAL
    independent_rate: Decimal = ZERO
    agreement_version: str = ""

    @classmethod
    def from_profile(cls, profile: Mapping[str, Any] | None) -> "Terms":
        if not isinstance(profile, Mapping):
            return cls(False)
        accepted = str(profile.get("acceptance_status") or "").upper() == "ACCEPTED"
        tc = profile.get("trade_commission") or {}
        ind = profile.get("independent_trade_platform_fee") or {}
        terms = cls(accepted, str(tc.get("basis") or "NONE").upper(), _dec(tc.get("rate") or 0, "commission_rate"),
                    str(ind.get("basis") or "NONE").upper(), _dec(ind.get("rate") or 0, "independent_rate"),
                    str(profile.get("agreement_version") or ""))
        terms.validate()
        return terms

    def validate(self) -> None:
        if self.commission_basis not in {"NONE", "PERCENT_PROFIT", "FIXED_PER_TRADE", "PERCENT_NOTIONAL"}:
            raise FeeLedgerError("commission_basis_invalid")
        if self.independent_basis not in {"NONE", "FIXED_PER_TRADE", "PERCENT_NOTIONAL"}:
            raise FeeLedgerError("independent_basis_invalid")
        for basis, rate in ((self.commission_basis, self.commission_rate), (self.independent_basis, self.independent_rate)):
            if rate < 0 or (basis.startswith("PERCENT_") and rate > 100):
                raise FeeLedgerError("rate_out_of_range")


def css_fee(terms: Terms, *, notional: Decimal, hurdle_clearing_profit: Decimal) -> Decimal:
    if hurdle_clearing_profit <= 0 or terms.commission_basis == "NONE":
        return ZERO
    if terms.commission_basis == "PERCENT_PROFIT":
        raw = hurdle_clearing_profit * terms.commission_rate / 100
    elif terms.commission_basis == "FIXED_PER_TRADE":
        raw = terms.commission_rate
    else:  # PERCENT_NOTIONAL
        raw = notional * terms.commission_rate / 100
    return _cents(min(raw, hurdle_clearing_profit))


def independent_fee(terms: Terms, *, notional: Decimal) -> Decimal:
    if terms.independent_basis == "FIXED_PER_TRADE":
        return _cents(terms.independent_rate)
    if terms.independent_basis == "PERCENT_NOTIONAL":
        return _cents(notional * terms.independent_rate / 100)
    return ZERO


@dataclass
class _State:
    cum_pnl: Decimal = ZERO
    hwm: Decimal = ZERO


def _replay(trades: list[Mapping[str, Any]]) -> dict[str, Decimal]:
    """position_id -> fee, recomputed from scratch (per user, in posting order)."""
    states: dict[str, _State] = {}
    fees: dict[str, Decimal] = {}
    for t in trades:
        terms = Terms(t["terms"]["accepted"], t["terms"]["commission_basis"], Decimal(t["terms"]["commission_rate"]),
                      t["terms"]["independent_basis"], Decimal(t["terms"]["independent_rate"]),
                      t["terms"]["agreement_version"])
        notional, pnl = Decimal(t["notional"]), Decimal(t["pnl"])
        if not terms.accepted:
            fees[t["position_id"]] = ZERO
            continue
        if t["attribution"] == CSS:
            st = states.setdefault(t["user_id"], _State())
            st.cum_pnl += pnl
            clearing = max(ZERO, st.cum_pnl - st.hwm)
            fees[t["position_id"]] = css_fee(terms, notional=notional, hurdle_clearing_profit=clearing)
            st.hwm = max(st.hwm, st.cum_pnl)
        elif t["attribution"] == INDEPENDENT:
            fees[t["position_id"]] = independent_fee(terms, notional=notional)
        else:
            fees[t["position_id"]] = ZERO
    return fees


class FeeLedger:
    def __init__(self, root: Path | str, *, terms_resolver: Callable[[str], Mapping[str, Any] | None],
                 copy_trades_attributable: bool = False, currency: str = "USD") -> None:
        self.root = Path(root)
        self.log = HashChainLog(self.root, "commercial_fee_ledger", FeeLedgerError)
        self.lock = self.root / "commercial_fee_ledger.lock"
        self.terms_resolver = terms_resolver
        self.copy_trades_attributable = bool(copy_trades_attributable)
        self.currency = currency

    # ------------------------------------------------------------------ posting
    def post_close(self, *, position_id: str, user_id: str, trader_id: str, signal_id: str, notional: Any, pnl: Any,
                   now: datetime | None = None) -> dict[str, Any]:
        """Record a closed paper position and accrue its fee. Idempotent per position_id."""
        if not position_id or not user_id:
            raise FeeLedgerError("position_and_user_required")
        notional_d, pnl_d = _dec(notional, "notional"), _dec(pnl, "pnl")
        if notional_d <= 0:
            raise FeeLedgerError("notional_must_be_positive")
        attribution = classify(trader_id, copy_trades_attributable=self.copy_trades_attributable)
        try:
            terms = Terms.from_profile(self.terms_resolver(user_id))
        except FeeLedgerError:
            terms = Terms(False)  # malformed terms never charge
        body = {"position_id": str(position_id), "user_id": str(user_id), "trader_id": str(trader_id),
                "signal_id": str(signal_id), "attribution": attribution, "notional": str(notional_d),
                "pnl": str(pnl_d),
                "terms": {"accepted": terms.accepted, "commission_basis": terms.commission_basis,
                          "commission_rate": str(terms.commission_rate), "independent_basis": terms.independent_basis,
                          "independent_rate": str(terms.independent_rate), "agreement_version": terms.agreement_version}}
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            events = self.log.events()
            prior = next((e for e in events if e["type"] == "TRADE_CLOSED" and e["position_id"] == position_id), None)
            if prior is not None:
                same = all(prior[k] == body[k] for k in ("user_id", "trader_id", "attribution", "notional", "pnl"))
                if not same:
                    raise FeeLedgerError("position_already_posted_with_different_data")
                return {"status": "DUPLICATE_IGNORED", "position_id": position_id, "fee": prior["fee"]}
            trades = [e for e in events if e["type"] == "TRADE_CLOSED" and not self._reversed(events, e["position_id"])]
            fees = _replay(trades + [body])
            fee = fees[position_id]
            reason = ("terms_not_accepted" if not terms.accepted else
                      "copy_trader_not_css_attributable" if attribution == COPY_TRADER else
                      "no_profit_above_loss_recovery_hurdle" if attribution == CSS and fee == 0 else "accrued")
            event = self.log.append({"type": "TRADE_CLOSED", **body, "fee": str(fee), "fee_kind":
                                     "CSS_COMMISSION" if attribution == CSS else
                                     "INDEPENDENT_PLATFORM_FEE" if attribution == INDEPENDENT else "NONE",
                                     "reason": reason, "currency": self.currency, "money_moved": False,
                                     "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return {"status": "POSTED", "position_id": position_id, "fee": event["fee"], "reason": reason,
                "attribution": attribution}

    @staticmethod
    def _reversed(events: list[Mapping[str, Any]], position_id: str) -> bool:
        return any(e["type"] == "TRADE_REVERSED" and e["position_id"] == position_id for e in events)

    # ------------------------------------------------------------------ admin actions
    @staticmethod
    def _admin(actor_ctx: Mapping[str, Any]) -> str:
        if str((actor_ctx or {}).get("role", "")).upper() != SUPER_USER or not (actor_ctx or {}).get("user_id"):
            raise FeeLedgerError("super_user_required")
        return str(actor_ctx["user_id"])

    def reverse_trade(self, position_id: str, *, reason: str, actor_ctx: Mapping[str, Any],
                      now: datetime | None = None) -> dict[str, Any]:
        actor = self._admin(actor_ctx)
        if not str(reason or "").strip():
            raise FeeLedgerError("reason_required")
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            events = self.log.events()
            if not any(e["type"] == "TRADE_CLOSED" and e["position_id"] == position_id for e in events):
                raise FeeLedgerError("position_not_posted")
            if self._reversed(events, position_id):
                return {"status": "ALREADY_REVERSED", "position_id": position_id}
            self.log.append({"type": "TRADE_REVERSED", "position_id": position_id, "reason": str(reason)[:300],
                             "actor": actor, "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return {"status": "REVERSED", "position_id": position_id, "adjustments": self.reconcile(now=now, actor=actor)}

    def refund(self, user_id: str, amount: Any, *, reason: str, actor_ctx: Mapping[str, Any],
               now: datetime | None = None) -> dict[str, Any]:
        actor = self._admin(actor_ctx)
        amt = _cents(_dec(amount, "amount"))
        if amt <= 0:
            raise FeeLedgerError("refund_must_be_positive")
        if not str(reason or "").strip():
            raise FeeLedgerError("reason_required")
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            if amt > self._net_fees(self.log.events(), user_id):
                raise FeeLedgerError("refund_exceeds_net_fees")
            self.log.append({"type": "REFUND", "user_id": user_id, "amount": str(amt), "reason": str(reason)[:300],
                             "actor": actor, "money_moved": False,
                             "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return {"status": "REFUND_RECORDED", "user_id": user_id, "amount": str(amt)}

    # ------------------------------------------------------------------ reconciliation and statements
    def _charged(self, events: list[Mapping[str, Any]]) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for e in events:
            if e["type"] == "TRADE_CLOSED":
                out[e["position_id"]] = out.get(e["position_id"], ZERO) + Decimal(e["fee"])
            elif e["type"] == "ADJUSTMENT":
                out[e["position_id"]] = out.get(e["position_id"], ZERO) + Decimal(e["amount"])
        return out

    def expected_fees(self, events: list[Mapping[str, Any]] | None = None) -> dict[str, Decimal]:
        events = self.log.events() if events is None else events
        trades = [e for e in events if e["type"] == "TRADE_CLOSED"]
        live = [t for t in trades if not self._reversed(events, t["position_id"])]
        expected = {t["position_id"]: ZERO for t in trades}
        expected.update(_replay(live))
        return expected

    def reconcile(self, *, now: datetime | None = None, actor: str = "SYSTEM_RECONCILE") -> list[dict[str, Any]]:
        """Post ADJUSTMENT entries so charged fees equal replayed fees. Idempotent: a second call posts nothing."""
        posted = []
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            events = self.log.events()
            charged, expected = self._charged(events), self.expected_fees(events)
            users = {e["position_id"]: e["user_id"] for e in events if e["type"] == "TRADE_CLOSED"}
            for pid in sorted(expected):
                diff = expected[pid] - charged.get(pid, ZERO)
                if diff != 0:
                    posted.append(self.log.append({
                        "type": "ADJUSTMENT", "position_id": pid, "user_id": users[pid], "amount": str(diff),
                        "kind": "REFUND_DUE" if diff < 0 else "ACCRUAL_DUE", "actor": actor, "money_moved": False,
                        "at_utc": (now or datetime.now(timezone.utc)).isoformat()}))
        return posted

    def _net_fees(self, events: list[Mapping[str, Any]], user_id: str) -> Decimal:
        total = ZERO
        for e in events:
            if e.get("user_id") != user_id:
                continue
            if e["type"] == "TRADE_CLOSED":
                total += Decimal(e["fee"])
            elif e["type"] == "ADJUSTMENT":
                total += Decimal(e["amount"])
            elif e["type"] == "REFUND":
                total -= Decimal(e["amount"])
        return total

    def statement(self, user_id: str) -> dict[str, Any]:
        events = self.log.events()
        mine = [e for e in events if e.get("user_id") == user_id]
        css = [e for e in mine if e["type"] == "TRADE_CLOSED" and e["attribution"] == CSS
               and not self._reversed(events, e["position_id"])]
        cum = hwm = ZERO
        for e in css:
            cum += Decimal(e["pnl"])
            hwm = max(hwm, cum)
        charged, expected = self._charged(events), self.expected_fees(events)
        pids = {e["position_id"] for e in mine if e["type"] == "TRADE_CLOSED"}
        return {
            "user_id": user_id, "currency": self.currency, "money_moved": False,
            "net_fees": str(self._net_fees(events, user_id)),
            "css_attributable_cum_pnl": str(cum), "css_high_water_mark": str(hwm),
            "loss_recovery_remaining": str(max(ZERO, hwm - cum)),
            "trades": len(pids), "reconciled": all(charged.get(p, ZERO) == expected.get(p, ZERO) for p in pids),
        }
