"""User-facing trading-profile service: catalog, onboarding/consent, startup state, emergency actions."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.trading_profiles.attribution import AttributionLedger, reconcile
from backend.trading_profiles.consent import ConsentError, ConsentService
from backend.trading_profiles.mandates import KeyProvider, MandateError, MandateRegistry, evaluate_mandate
from backend.trading_profiles.manual import ControlledManual, current_manual
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
    def __init__(self, root: Path | str | None = None, *, key_provider: KeyProvider | None = None,
                 manual_provider: Callable[[], ControlledManual] = current_manual) -> None:
        self.root = Path(root) if root is not None else default_store_root()
        self.key_provider = key_provider
        self.manual_provider = manual_provider
        self.preferences = PreferencesStore(self.root)
        self.mandates = MandateRegistry(self.root, key_provider=key_provider)
        self.ledger = AttributionLedger(self.root)
        self.consent = ConsentService(self.root, preferences=self.preferences, mandates=self.mandates,
                                      manual_provider=manual_provider)
        self.trader_registry = self.consent.trader_registry

    def catalog(self) -> dict[str, Any]:
        manual = self.manual_provider()
        return {
            "operating_modes": [
                {"mode": m.value, **{k: v for k, v in permissions_for(m).__dict__.items() if k != "mode"}}
                for m in OperatingMode
            ],
            "risk_personalities": [policy_for(p).summary() for p in RiskPersonality],
            "manual": {k: v for k, v in manual.describe().items() if k != "history"},
            "precedence": [
                "platform eligibility and hard safety limits",
                "R7 / R14F / AntiBleedGuard, kill switch, margin, capital governor, pilot caps",
                "risk personality and trader mandate",
                "user-configured limits (tighten only)",
                "per-order approval (CSS-Assisted Trading)",
            ],
            "live_trading": "not authorized by any selection or acceptance; governed separately",
        }

    def startup_state(self, user_id: str, *, session_id: str, now: datetime | None = None) -> dict[str, Any]:
        """What the app shows at start: active accepted settings, or what is needed before trading."""
        now = now or _now()
        state = self.preferences.get(user_id)
        manual = self.manual_provider()
        consent_ok, consent_reason = self.consent.verify_active(user_id, state)
        out: dict[str, Any] = {
            "user_id": user_id,
            "active": state.active.to_record() if state.active else None,
            "paused": state.paused,
            "previous_selection": state.previous_selection,
            "consent": {"valid": consent_ok, "reason": consent_reason, "current_manual_version": manual.version},
            "needs": [],
            "mandate": None,
            "can_open_new_trades": False,
            "live_trading_permitted": False,
        }
        if state.active is None:
            out["needs"].append("onboarding_acceptance")
        elif not consent_ok:
            out["needs"].append("renewed_acceptance" if consent_reason == "consent_renewal_required" else "acceptance")
        if state.active and state.active.mandate_id:
            mandate = self.mandates.get(state.active.mandate_id)
            if mandate is not None:
                decision = evaluate_mandate(
                    mandate, key_provider=self.key_provider, follower_user_id=user_id, trader_id=mandate.trader_id,
                    personality=state.active.risk_personality or RiskPersonality.BALANCED,
                    asset_class=mandate.asset_classes[0], session_id=session_id, now=now)
                out["mandate"] = {"mandate_id": mandate.mandate_id, "trader_id": mandate.trader_id,
                                  "expires_at_utc": mandate.expires_at_utc, "status": decision.reason}
                if not decision.valid_for_new_trades:
                    out["needs"].append("trader_reauthorization" if "reauthorization" in decision.reason
                                        else "new_copy_mandate")
        if state.paused:
            out["needs"].append("resume")
        out["can_open_new_trades"] = not out["needs"]
        return out

    # -- risk-reducing actions: never gated by consent ------------------------
    def pause(self, user_id: str) -> dict[str, Any]:
        state = self.preferences.pause(user_id)
        return {"paused": state.paused, "paused_at_utc": state.paused_at_utc}

    def revoke_mandate(self, user_id: str, mandate_id: str, reason: str) -> dict[str, Any]:
        mandate = self.mandates.revoke(mandate_id, follower_user_id=user_id, reason=reason, now=_now())
        return {"revoked_at_utc": mandate.revoked_at_utc}

    # -- risk-enabling actions: require valid consent --------------------------
    def resume(self, user_id: str) -> dict[str, Any]:
        ok, reason = self.consent.verify_active(user_id)
        if not ok:
            raise ConsentError(reason)
        self.preferences.unpause(user_id)
        return {"paused": False}

    def reauthorize_mandate(self, user_id: str, mandate_id: str, session_id: str) -> dict[str, Any]:
        ok, reason = self.consent.verify_active(user_id)
        if not ok:
            raise ConsentError(reason)
        state = self.preferences.get(user_id)
        if state.active is None or state.active.mandate_id != mandate_id:
            raise MandateError("mandate_not_active_for_user")
        mandate = self.mandates.reauthorize(mandate_id, follower_user_id=user_id, session_id=session_id, now=_now())
        return {"expires_at_utc": mandate.expires_at_utc, "last_authorized_at_utc": mandate.last_authorized_at_utc}

    def propose(self, user_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        change = self.consent.propose_change(
            user_id, operating_mode=payload.get("operating_mode"), risk_personality=payload.get("risk_personality"),
            limits=payload.get("limits"), mandate_request=payload.get("mandate"), now=_now())
        return {"change": change.__dict__}

    def statement(self, user_id: str) -> dict[str, Any]:
        return self.ledger.follower_statement(user_id)

    def reconciliation(self) -> dict[str, Any]:
        return reconcile(self.ledger.records())
