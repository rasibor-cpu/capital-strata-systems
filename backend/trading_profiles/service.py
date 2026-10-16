"""User-facing trading-profile service: catalog, selection, startup state, mandates, statements."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.trading_profiles.attribution import AttributionLedger, reconcile
from backend.trading_profiles.disclosures import current_disclosure
from backend.trading_profiles.mandates import (
    KeyProvider,
    MandateError,
    MandateRegistry,
    ReauthorizationPolicy,
    evaluate_mandate,
)
from backend.trading_profiles.operating_modes import OperatingMode, permissions_for
from backend.trading_profiles.preferences import PreferencesStore, default_store_root
from backend.trading_profiles.risk_personalities import RiskPersonality, policy_for

SIGNING_KEY_ENV = "CSS_COPY_MANDATE_SIGNING_KEY"


def env_key_provider() -> KeyProvider | None:
    """Mandate signing key from the environment (hex, >= 32 bytes). None when absent: no default key."""
    raw = os.environ.get(SIGNING_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        return None
    return (lambda: key) if len(key) >= 32 else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TradingProfileService:
    def __init__(self, root: Path | str | None = None, *, key_provider: KeyProvider | None = None) -> None:
        self.root = Path(root) if root is not None else default_store_root()
        self.key_provider = key_provider
        self.preferences = PreferencesStore(self.root)
        self.mandates = MandateRegistry(self.root, key_provider=key_provider)
        self.ledger = AttributionLedger(self.root)

    @staticmethod
    def catalog() -> dict[str, Any]:
        return {
            "operating_modes": [
                {"mode": m.value, **{k: v for k, v in permissions_for(m).__dict__.items() if k != "mode"}}
                for m in OperatingMode
            ],
            "risk_personalities": [policy_for(p).summary() for p in RiskPersonality],
            "disclosure": current_disclosure(),
            "live_trading": "not authorized by any selection; governed separately",
        }

    def startup_state(self, user_id: str, *, session_id: str, now: datetime | None = None) -> dict[str, Any]:
        """What the app shows at start: the persisted choice, or what still needs choosing/renewing."""
        now = now or _now()
        prefs = self.preferences.get(user_id)
        state: dict[str, Any] = {
            "user_id": user_id,
            "operating_mode": prefs.operating_mode.value if prefs.operating_mode else None,
            "risk_personality": prefs.risk_personality.value if prefs.risk_personality else None,
            "needs_selection": prefs.missing_requirements(),
            "disclosure_current": prefs.disclosure_current,
            "mandate": None,
            "can_open_new_trades": False,
            "live_trading_permitted": False,
        }
        if prefs.operating_mode is OperatingMode.COPY_CSS_TRADER:
            mandate = self.mandates.active_for(user_id, now)
            if mandate is None:
                state["needs_selection"].append("trader_mandate")
            else:
                personality = prefs.risk_personality or RiskPersonality.BALANCED
                decision = evaluate_mandate(
                    mandate, key_provider=self.key_provider, follower_user_id=user_id, trader_id=mandate.trader_id,
                    personality=personality, asset_class=mandate.asset_classes[0], session_id=session_id, now=now,
                )
                state["mandate"] = {
                    "mandate_id": mandate.mandate_id, "trader_id": mandate.trader_id, "personality": mandate.personality,
                    "asset_classes": list(mandate.asset_classes), "max_allocation": mandate.max_allocation,
                    "currency": mandate.currency, "expires_at_utc": mandate.expires_at_utc,
                    "reauthorization_policy": mandate.reauthorization_policy, "status": decision.reason,
                }
                if not decision.valid_for_new_trades:
                    state["needs_selection"].append("trader_reauthorization")
        state["can_open_new_trades"] = not state["needs_selection"]
        return state

    def authorize_trader(self, user_id: str, *, trader_id: str, asset_classes: list[str], max_allocation: float,
                         currency: str, valid_days: float, reauthorization_policy: str,
                         reauthorization_interval_hours: float, session_id: str, now: datetime | None = None) -> dict:
        prefs = self.preferences.get(user_id)
        if prefs.operating_mode is not OperatingMode.COPY_CSS_TRADER:
            raise MandateError("operating_mode_is_not_copy_trading")
        if prefs.risk_personality is None or not prefs.disclosure_current:
            raise MandateError("personality_and_current_disclosure_required")
        mandate = self.mandates.authorize(
            follower_user_id=user_id, trader_id=trader_id, personality=prefs.risk_personality,
            asset_classes=tuple(asset_classes), max_allocation=max_allocation, currency=currency,
            valid_days=valid_days, reauthorization_policy=ReauthorizationPolicy(reauthorization_policy),
            reauthorization_interval_hours=reauthorization_interval_hours, session_id=session_id, now=now or _now(),
        )
        return {"mandate_id": mandate.mandate_id, "expires_at_utc": mandate.expires_at_utc}

    def statement(self, user_id: str) -> dict[str, Any]:
        return self.ledger.follower_statement(user_id)

    def reconciliation(self) -> dict[str, Any]:
        return reconcile(self.ledger.records())
