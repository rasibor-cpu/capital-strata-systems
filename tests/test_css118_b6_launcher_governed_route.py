"""CSS-118 B6: launcher paper routes reach the governed router (paper only)."""
from __future__ import annotations

import time

from backend.trading_profiles.governed_launcher_entry import (
    session_from_identity,
    submit_governed_launcher_paper_order,
)
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.router import PaperBook, TradingRouter
from css118_support import KEY, SESSION, activate, system


def test_non_paper_broker_refused_as_live_ticket():
    result = submit_governed_launcher_paper_order(
        user_id="u1",
        session=(SESSION, time.time()),
        payload={"broker": "OANDA", "symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "amount": 100},
    )
    assert result["routed"] is False
    assert result["reason"] == "LIVE_TICKET_DISABLED_CSS118"
    assert result["live_order_sent"] is False


def test_open_dev_identity_has_no_governed_session():
    assert session_from_identity({"user_id": "open_dev"}) is None


def test_missing_session_fails_closed():
    result = submit_governed_launcher_paper_order(
        user_id="u1",
        session=None,
        payload={"broker": "CSS_PAPER", "symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "amount": 100},
    )
    assert result["routed"] is False
    assert "session" in result["reason"]


def test_governed_route_uses_trading_router(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    sess = (SESSION, time.time())
    router = TradingRouter(
        engine,
        book=PaperBook(engine.root),
        role_resolver=lambda u: "TRADER",
        session_resolver=lambda u: sess,
        system_provider=lambda: system(),
    )
    activate(engine.consent, "u1", "Simulated Trading", None)
    result = submit_governed_launcher_paper_order(
        user_id="u1",
        session=sess,
        payload={
            "broker": "CSS_PAPER",
            "symbol": "EUR/USD",
            "asset_class": "FX",
            "side": "BUY",
            "amount": 100,
            "stop_distance_pct": 1.0,
        },
        router=router,
    )
    assert result["routed"] is True
    assert result["live_order_sent"] is False
    # Without a fresh CSS market assessment the router rejects — fail closed, still governed.
    assert result["outcome"] in {"REJECTED", "COPIED", "PROPOSED", "SIMULATED"}


# --- Closeout reconciliation (#123 B6 x RC1): no fabricated order fields or sessions ---------

def test_quantity_is_never_treated_as_notional():
    result = submit_governed_launcher_paper_order(
        user_id="u1", session=(SESSION, time.time()),
        payload={"broker": "CSS_PAPER", "symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "BUY",
                 "quantity": 1, "stop_distance_pct": 2.0},
    )
    assert result["routed"] is False
    assert result["reason"] == "manual_order_requires_notional_and_stop"


def test_missing_stop_is_refused_not_defaulted():
    result = submit_governed_launcher_paper_order(
        user_id="u1", session=(SESSION, time.time()),
        payload={"broker": "CSS_PAPER", "symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "amount": 100},
    )
    assert result["routed"] is False
    assert result["reason"] == "manual_order_requires_notional_and_stop"


def test_session_is_never_fabricated_from_identity():
    # A header/cookie identity without a real sign-on record cannot produce a session.
    assert session_from_identity({"user_id": "u1"}) is None
    assert session_from_identity({"user_id": "u1", "session_id": "s1"}) is None  # no creation time
    assert session_from_identity({"user_id": "u1", "created": time.time()}) is None  # no session id
    assert session_from_identity({"user_id": "u1", "session_id": "s1", "created": time.time() + 3600}) is None
    created = time.time() - 30
    assert session_from_identity({"user_id": "u1", "session_id": "s1", "created": created}) == ("s1", created)
