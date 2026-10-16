"""Closeout: commercial fee accrual (commission only on profitable CSS-attributable trades above the
loss-recovery hurdle; independent-trade platform fees; idempotency; reversals; refunds; reconciliation).

Accounting only: nothing here collects, charges or transfers money."""
from __future__ import annotations

import json
import time
from datetime import timedelta
from decimal import Decimal

import pytest

from css118_support import NOW, SESSION, KEY, activate, signal, system

ROLES = {"auto-1": "TRADER", "auto-2": "TRADER"}
from backend.commercial.fee_ledger import (
    COPY_TRADER,
    CSS,
    INDEPENDENT,
    FeeLedger,
    FeeLedgerError,
    Terms,
    classify,
    css_fee,
)
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, MANUAL_ORDER_PREFIX, CopyTradeEngine
from backend.trading_profiles.router import PaperBook, TradingRouter

ADMIN = {"user_id": "root-1", "role": "SUPER_USER"}


def profile(basis="PERCENT_PROFIT", rate="20", ind_basis="FIXED_PER_TRADE", ind_rate="1.50", accepted=True):
    return {"acceptance_status": "ACCEPTED" if accepted else "PENDING", "agreement_version": "v1",
            "trade_commission": {"basis": basis, "rate": rate},
            "independent_trade_platform_fee": {"basis": ind_basis, "rate": ind_rate}}


def ledger(tmp_path, profiles=None, **kw):
    profiles = profiles if profiles is not None else {"u1": profile()}
    return FeeLedger(tmp_path / "fees", terms_resolver=profiles.get, **kw)


def close(led, pid, pnl, *, trader=AUTONOMOUS_SOURCE_ID, user="u1", notional=1000):
    return led.post_close(position_id=pid, user_id=user, trader_id=trader, signal_id="s-" + pid,
                          notional=notional, pnl=pnl, now=NOW)


def test_attribution_separates_css_independent_and_copy_trades():
    assert classify(AUTONOMOUS_SOURCE_ID) == CSS
    assert classify(MANUAL_ORDER_PREFIX + "u1") == INDEPENDENT
    assert classify("trader-alpha") == COPY_TRADER
    assert classify("trader-alpha", copy_trades_attributable=True) == CSS


def test_commission_only_on_profit_above_loss_recovery_hurdle(tmp_path):
    led = ledger(tmp_path)
    assert close(led, "p1", "-100")["fee"] == "0"                      # loss: no fee, hurdle 100
    r = close(led, "p2", "60")
    assert (r["fee"], r["reason"]) == ("0", "no_profit_above_loss_recovery_hurdle")  # 40 still to recover
    assert close(led, "p3", "90")["fee"] == "10.00"                    # 50 above HWM x 20%
    assert close(led, "p4", "25")["fee"] == "5.00"                     # new profit, no hurdle left
    st = led.statement("u1")
    assert st["net_fees"] == "15.00" and st["loss_recovery_remaining"] == "0" and st["reconciled"]
    assert st["money_moved"] is False


@pytest.mark.parametrize("basis,rate,pnl,expected", [
    ("FIXED_PER_TRADE", "5", "100", "5.00"),
    ("FIXED_PER_TRADE", "5", "3", "3.00"),          # capped at the trade's hurdle-clearing profit
    ("FIXED_PER_TRADE", "5", "-3", "0"),             # never on a loss
    ("PERCENT_NOTIONAL", "0.1", "50", "1.00"),       # 0.1% of 1000
    ("PERCENT_PROFIT", "33.333", "10", "3.33"),      # rounded down, customer's favour
    ("NONE", "0", "100", "0"),
])
def test_every_commission_basis_is_profit_only_and_capped(tmp_path, basis, rate, pnl, expected):
    led = ledger(tmp_path, {"u1": profile(basis, rate)})
    assert close(led, "p1", pnl)["fee"] == expected


def test_independent_trades_pay_platform_fee_only_and_do_not_touch_hurdle(tmp_path):
    led = ledger(tmp_path, {"u1": profile(ind_basis="PERCENT_NOTIONAL", ind_rate="0.05")})
    r = close(led, "m1", "-40", trader=MANUAL_ORDER_PREFIX + "u1", notional=2000)
    assert (r["fee"], r["attribution"]) == ("1.00", INDEPENDENT)
    assert close(led, "c1", "100")["fee"] == "20.00"  # CSS hurdle unaffected by the manual loss
    assert led.statement("u1")["css_attributable_cum_pnl"] == "100"


def test_copy_trader_trades_are_not_charged_unless_owner_enables_attribution(tmp_path):
    led = ledger(tmp_path)
    r = close(led, "x1", "100", trader="trader-alpha")
    assert (r["fee"], r["reason"]) == ("0", "copy_trader_not_css_attributable")
    led2 = ledger(tmp_path / "b", copy_trades_attributable=True)
    assert close(led2, "x1", "100", trader="trader-alpha")["fee"] == "20.00"


def test_no_fee_without_accepted_terms_or_with_malformed_terms(tmp_path):
    led = ledger(tmp_path, {"u1": profile(accepted=False), "u2": {"acceptance_status": "ACCEPTED",
                                                                  "trade_commission": {"basis": "BOGUS", "rate": "5"}}})
    assert close(led, "p1", "100")["reason"] == "terms_not_accepted"
    assert close(led, "p2", "100", user="u2")["reason"] == "terms_not_accepted"
    assert close(led, "p3", "100", user="nobody")["fee"] == "0"
    with pytest.raises(FeeLedgerError, match="rate_out_of_range"):
        Terms.from_profile(profile("PERCENT_PROFIT", "150"))


def test_posting_is_idempotent_and_conflicts_are_refused(tmp_path):
    led = ledger(tmp_path)
    assert close(led, "p1", "100")["status"] == "POSTED"
    assert close(led, "p1", "100")["status"] == "DUPLICATE_IGNORED"
    with pytest.raises(FeeLedgerError, match="different_data"):
        close(led, "p1", "101")
    assert len([e for e in led.log.events() if e["type"] == "TRADE_CLOSED"]) == 1


def test_reversal_recomputes_later_fees_and_reconcile_is_idempotent(tmp_path):
    led = ledger(tmp_path)
    close(led, "p1", "100")    # fee 20, HWM 100
    close(led, "p2", "-50")    # hurdle 50
    close(led, "p3", "80")     # 30 above HWM -> fee 6
    with pytest.raises(FeeLedgerError, match="super_user_required"):
        led.reverse_trade("p2", reason="bust", actor_ctx={"user_id": "x", "role": "TRADER"})
    out = led.reverse_trade("p2", reason="exchange bust", actor_ctx=ADMIN)
    # Without p2's loss, p3's whole 80 is above the HWM: fee 16, so +10 is accrued for p3.
    assert [(a["position_id"], a["amount"], a["kind"]) for a in out["adjustments"]] == [("p3", "10.00", "ACCRUAL_DUE")]
    assert led.reconcile() == []
    out = led.reverse_trade("p3", reason="void", actor_ctx=ADMIN)
    assert [(a["position_id"], a["amount"]) for a in out["adjustments"]] == [("p3", "-16.00")]
    assert led.statement("u1")["net_fees"] == "20.00" and led.statement("u1")["reconciled"]
    assert led.reverse_trade("p3", reason="again", actor_ctx=ADMIN)["status"] == "ALREADY_REVERSED"


def test_refund_is_admin_only_bounded_and_recorded(tmp_path):
    led = ledger(tmp_path)
    close(led, "p1", "100")
    with pytest.raises(FeeLedgerError, match="refund_exceeds_net_fees"):
        led.refund("u1", "25", reason="goodwill", actor_ctx=ADMIN)
    with pytest.raises(FeeLedgerError, match="super_user_required"):
        led.refund("u1", "5", reason="goodwill", actor_ctx={"user_id": "u1", "role": "TRADER"})
    assert led.refund("u1", "5", reason="goodwill", actor_ctx=ADMIN)["amount"] == "5.00"
    assert led.statement("u1")["net_fees"] == "15.00"


def test_ledger_is_tamper_evident(tmp_path):
    led = ledger(tmp_path)
    close(led, "p1", "100")
    lines = led.log.path.read_text().splitlines()
    doc = json.loads(lines[0])
    doc["fee"] = "0"
    led.log.path.write_text(json.dumps(doc) + "\n")
    with pytest.raises(FeeLedgerError, match="chain_broken"):
        led.statement("u1")


def test_css_fee_function_never_exceeds_profit():
    t = Terms(True, "FIXED_PER_TRADE", Decimal("1000"))
    assert css_fee(t, notional=Decimal("10"), hurdle_clearing_profit=Decimal("0.07")) == Decimal("0.07")


def test_router_exit_cycle_posts_fees_once_and_never_blocks_exits(tmp_path, monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "tp"
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    sessions = {uid: (SESSION, time.time()) for uid in ROLES}
    real = FeeLedger(root / "commercial", terms_resolver={"auto-1": profile(), "auto-2": profile()}.get)

    class FlakyForAuto2:
        """Delegates to the real ledger; fails for auto-2 as a full disk would."""
        def post_close(self, **kw):
            if kw["user_id"] == "auto-2":
                raise OSError("disk full")
            return real.post_close(**kw)

    router = TradingRouter(engine, book=PaperBook(root), role_resolver=ROLES.get, session_resolver=sessions.get,
                           system_provider=lambda: system(), fee_ledger=FlakyForAuto2())
    for uid in ("auto-1", "auto-2"):
        activate(engine.consent, uid, "CSS Autonomous Trading", "Balanced")
    decisions = router.on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID), now=NOW).decisions
    assert sorted(d.outcome for d in decisions) == ["COPIED", "COPIED"]
    sym = router.book.positions()[0].symbol
    entry = router.book.positions()[0].entry_price
    closed = router.run_exit_cycle({sym: entry * 1.5}, now=NOW + timedelta(minutes=5))
    by_user = {c["user_id"]: c for c in closed}
    assert set(by_user) == {"auto-1", "auto-2"} and all(c["pnl"] > 0 for c in closed)
    assert by_user["auto-1"]["fee"]["status"] == "POSTED" and Decimal(by_user["auto-1"]["fee"]["fee"]) > 0
    # The failed posting is recorded, and the protective exit still happened.
    assert by_user["auto-2"]["fee"]["status"] == "POSTING_FAILED" and router.fee_posting_errors
    assert router.book.positions() == []
    st = real.statement("auto-1")
    assert st["trades"] == 1 and st["reconciled"] and st["money_moved"] is False
    # Re-posting the same closed position (e.g. a recovery replay) does not double-charge.
    pos_id = by_user["auto-1"]["position_id"]
    assert real.post_close(position_id=pos_id, user_id="auto-1", trader_id=AUTONOMOUS_SOURCE_ID,
                           signal_id=decisions[0].signal_id, notional=[d for d in decisions
                                                                         if d.follower_user_id == "auto-1"][0].notional,
                           pnl=by_user["auto-1"]["pnl"])["status"] == "DUPLICATE_IGNORED"
