"""Connect launcher paper-trade routes to the canonical TradingRouter (CSS-118 B6).

Live/broker tickets remain refused. Missing consent or market assessment fails closed.
The JSONL request file remains an audit dual-write; execution only occurs via the router.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.trading_profiles.copy_engine import CopyTradeEngine, SystemContext
from backend.trading_profiles.router import PaperBook, TradingRouter
from backend.trading_profiles.service import TradingProfileService, env_key_provider

DEFAULT_ROOT = Path("artifacts") / "trading_profiles"


def _default_system() -> SystemContext:
    return SystemContext(
        engine_mode="SAFE",
        safety_flags={
            "verdict": "SAFE",
            "fail_closed": False,
            "execution_allowed": False,
            "live_trading_blocked": True,
        },
        mobile_controls={},
        env={},
    )


def build_default_router(
    *,
    root: Path | str | None = None,
    role_resolver: Callable[[str], str | None] | None = None,
    session_resolver: Callable[[str], tuple[str, float] | None] | None = None,
    system_provider: Callable[[], SystemContext] | None = None,
) -> TradingRouter:
    store = Path(root) if root is not None else DEFAULT_ROOT
    key = env_key_provider()
    service = TradingProfileService(store, key_provider=key)
    engine = CopyTradeEngine(store, key_provider=key, trader_registry=service.trader_registry)
    return TradingRouter(
        engine,
        book=PaperBook(store),
        role_resolver=role_resolver or (lambda _u: None),
        session_resolver=session_resolver or (lambda _u: None),
        system_provider=system_provider or _default_system,
    )


def submit_governed_launcher_paper_order(
    *,
    user_id: str,
    session: tuple[str, float] | None,
    payload: Mapping[str, Any],
    router: TradingRouter | None = None,
) -> dict[str, Any]:
    """Submit a paper manual order through TradingRouter. Never arms a broker."""
    broker = str(payload.get("broker") or "CSS_PAPER").strip().upper()
    if broker not in {"CSS_PAPER", "PAPER", "NONE", ""}:
        return {
            "routed": False,
            "outcome": "REFUSED",
            "reason": "LIVE_TICKET_DISABLED_CSS118",
            "live_order_sent": False,
        }
    if session is None:
        return {
            "routed": False,
            "outcome": "REFUSED",
            "reason": "authenticated_session_required_for_governed_route",
            "live_order_sent": False,
        }
    # The user states notional (account currency) and stop. Nothing is defaulted: a unit
    # quantity is not a notional, and an omitted stop is not a 1% stop.
    try:
        notional = float(payload.get("notional") if payload.get("notional") not in (None, "") else payload["amount"])
        stop = float(payload["stop_distance_pct"])
    except (KeyError, TypeError, ValueError):
        return {"routed": False, "outcome": "REFUSED", "reason": "manual_order_requires_notional_and_stop",
                "live_order_sent": False}
    if not (math.isfinite(notional) and notional > 0 and math.isfinite(stop) and stop > 0):
        return {"routed": False, "outcome": "REFUSED", "reason": "manual_order_requires_notional_and_stop",
                "live_order_sent": False}

    active = router or build_default_router()
    order = {
        "symbol": payload.get("symbol") or payload.get("instrument"),
        "asset_class": payload.get("asset_class"),
        "side": payload.get("side"),
        "notional": notional,
        "stop_distance_pct": stop,
        "client_order_id": payload.get("client_order_id") or "",
    }
    decision = active.submit_manual_order(str(user_id), session, order)
    return {
        "routed": True,
        "outcome": decision.outcome,
        "stage": decision.stage,
        "reason": decision.reason,
        "notional": decision.notional,
        "proposal_id": decision.proposal_id,
        "pipeline_status": decision.pipeline_status,
        "live_order_sent": False,
    }


def session_from_identity(identity: Mapping[str, Any] | None) -> tuple[str, float] | None:
    if not identity:
        return None
    user_id = str(identity.get("user_id") or "").strip()
    if not user_id or user_id == "open_dev":
        # open_dev profile has no real trading mandate/consent; refuse governed fill
        return None
    # Both values must come from the authenticated sign-on. Fabricating either (e.g. the user
    # id as session id, or "now" as the creation time) would defeat R7's recent-sign-on check.
    sid = str(identity.get("session_id") or identity.get("token_hash") or "").strip()
    raw_created = identity.get("created", identity.get("session_created_epoch"))
    try:
        created = float(raw_created)
    except (TypeError, ValueError):
        return None
    if not sid or not math.isfinite(created) or created <= 0 or created > time.time() + 60:
        return None
    return sid, created
