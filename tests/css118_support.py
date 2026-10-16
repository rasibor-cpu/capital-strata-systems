"""Shared helpers for the CSS-118 trading-profile tests.

`activate()` performs the real consent flow (propose -> open review -> present and
review every manual page -> accept), so tests never bypass the gate they rely on.
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from backend.trading_profiles.copy_engine import FollowerContext, SourceSignal, SystemContext
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256
from backend.trading_profiles.mandates import ReauthorizationPolicy

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
KEY = b"synthetic-test-mandate-key-0123456789abcdef"
SAFE_FLAGS = {"verdict": "SAFE", "fail_closed": False, "execution_allowed": False, "live_trading_blocked": True}
TRADER = "trader-alpha"
SESSION = "sess-1"
ALL_ASSETS = ("FX", "CRYPTO", "FUTURES", "OPTIONS")
ADMIN_A = {"user_id": "synthetic-admin-a", "role": "SUPER_USER"}
ADMIN_B = {"user_id": "synthetic-admin-b", "role": "SUPER_USER"}
# Deterministic synthetic trader keys (test data only; never a real trader).
_TRADER_KEYS: dict[str, Ed25519PrivateKey] = {}


def trader_key(trader_id: str = TRADER) -> Ed25519PrivateKey:
    if trader_id not in _TRADER_KEYS:
        seed = (trader_id.encode() * 32)[:32]
        _TRADER_KEYS[trader_id] = Ed25519PrivateKey.from_private_bytes(seed)
    return _TRADER_KEYS[trader_id]


def public_key_b64(trader_id: str = TRADER) -> str:
    raw = trader_key(trader_id).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def approve_trader(registry, trader_id: str = TRADER, assets=ALL_ASSETS):
    """Synthetic dual-control approval: admin A proposes, admin B approves."""
    existing = registry.get(trader_id)
    if existing is not None and existing.status == "ACTIVE":
        return existing
    registry.propose(trader_id=trader_id, display_name=f"Synthetic {trader_id}", public_key_b64=public_key_b64(trader_id),
                     asset_classes=list(assets), actor_ctx=ADMIN_A, now=NOW)
    return registry.approve(trader_id, actor_ctx=ADMIN_B, now=NOW)


def mandate_request(**overrides) -> dict:
    request = {"trader_id": TRADER, "asset_classes": list(ALL_ASSETS), "max_allocation": 5_000.0, "currency": "CAD",
               "valid_days": 30, "reauthorization_policy": ReauthorizationPolicy.INTERVAL.value,
               "reauthorization_interval_hours": 168}
    request.update(overrides)
    return request


def review_all_pages(consent, user_id, review, *, session=SESSION, now=NOW, method="scroll_bottom"):
    for page_id in review.pages:
        page = consent.present_page(user_id, auth_session_hash=session, review_id=review.review_id, page_id=page_id, now=now)
        consent.mark_reviewed(user_id, auth_session_hash=session, review_id=review.review_id, page_id=page_id,
                              method=method, page_sha256=page["sha256"], now=now)


def activate(consent, user_id, mode, personality=None, *, limits=None, mandate=None, session=SESSION, now=NOW,
             register_trader=True):
    """Propose, review every page and accept. Returns the receipt.

    For copy mandates the synthetic trader is first approved under dual control
    (register_trader=False tests the unapproved-trader path)."""
    if mandate and register_trader:
        approve_trader(consent.trader_registry, mandate["trader_id"])
    change = consent.propose_change(user_id, operating_mode=mode, risk_personality=personality, limits=limits,
                                    mandate_request=mandate, now=now)
    review = consent.open_review(user_id, auth_session_hash=session, change_id=change.change_id, now=now)
    review_all_pages(consent, user_id, review, session=session, now=now)
    manual = consent.manual_provider()
    return consent.accept(user_id, auth_session_hash=session, review_id=review.review_id, acknowledgement_checked=True,
                          acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256, manual_version=manual.version,
                          manual_sha256=manual.sha256, policy_hash_shown=change.policy_hash, now=now)


def signal(**overrides) -> SourceSignal:
    base = dict(
        signal_id="sig-1", trader_id=TRADER, symbol="EUR/USD", asset_class="FX", side="BUY",
        reference_price=1.08, probability=0.67, signal_score=16.0, confidence=0.75,
        expected_move_bps=80.0, fee_bps=2.0, spread_bps=1.0, slippage_bps=1.0,
        stop_distance_pct=2.5, risk_reward=2.4, strategy_score=0.9, replay_confidence=0.9,
    )
    base.update(overrides)
    return SourceSignal(**base)


def follower(user_id: str, **overrides) -> FollowerContext:
    base = dict(user_id=user_id, role="TRADER", session_id=SESSION, session_created_epoch=time.time(),
                equity=10_000.0, equity_peak=10_000.0, day_start_equity=10_000.0, buying_power=10_000.0)
    base.update(overrides)
    return FollowerContext(**base)


def system(**overrides) -> SystemContext:
    base = dict(engine_mode="BALANCED", safety_flags=SAFE_FLAGS, mobile_controls={}, env={})
    base.update(overrides)
    return SystemContext(**base)
