"""Explicit one-attempt Questrade read-only activation for Mission Control."""
from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Mapping

from backend.brokers.questrade.live_readonly_activation import compose_questrade_live_read_only_activation
from backend.brokers.questrade.mission_control_cache import QuestradeMissionControlCache


SAFETY = {"execution_allowed": False, "live_trading_blocked": True, "broker_execution_armed": False, "advisory_only": True}


class QuestradeMissionControlActivationCoordinator:
    """Activate once per process, fetch GET-only evidence, and publish a sanitized cache snapshot."""

    def __init__(self, cache: QuestradeMissionControlCache, *, composer: Callable[..., Any] = compose_questrade_live_read_only_activation) -> None:
        self._cache = cache
        self._composer = composer
        self._lock = RLock()
        self._attempted = False
        self._activation: Any = None
        self._account_reference: str | None = None
        self._state: dict[str, Any] = {"status": "DISABLED", "reason": "NOT_ACTIVATED", "attempted": False, **SAFETY}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def activate(self, *, refresh_token_store_path: str) -> dict[str, Any]:
        with self._lock:
            if self._cache.read() is not None:
                return {"status": "READY", "reason": "CACHE_ALREADY_FRESH", "attempted": self._attempted, **SAFETY}
            if self._attempted:
                return dict(self._state)
            self._attempted = True
            self._state = {"status": "ACTIVATING", "reason": "IN_PROGRESS", "attempted": True, **SAFETY}

        try:
            activation = self._composer(refresh_token_store_path=refresh_token_store_path, activation_authorized=True)
            public = activation.as_dict()
            provider = getattr(activation, "provider", None)
            if not public.get("activated") or provider is None:
                return self._fail(str(public.get("reason") or "QUESTRADE_ACTIVATION_UNAVAILABLE"))

            lease = memoryview(b"CSS_QUESTRADE_READ_ONLY")
            accounts = provider.fetch("ACCOUNTS", authorization=lease, parameters={})
            account_reference = _select_account_reference(accounts)
            if not account_reference:
                return self._fail("QUESTRADE_ACCOUNT_SELECTION_REQUIRED")

            if hasattr(provider, "bind_account_reference"):
                provider.bind_account_reference(account_reference)
            balances = provider.fetch("BALANCES", authorization=lease, parameters={"account_reference": account_reference})
            positions = provider.fetch("POSITIONS", authorization=lease, parameters={"account_reference": account_reference})
            snapshot = {"status": "AVAILABLE", "selected_broker": "QUESTRADE", "canonical_mode": "LIVE_READ_ONLY", "balances": dict(balances), "positions": dict(positions), **SAFETY}
            self._cache.publish(snapshot)
            with self._lock:
                self._activation = activation
                self._account_reference = account_reference
                self._state = {"status": "READY", "reason": "ok", "attempted": True, "provider_available": True, **SAFETY}
                return dict(self._state)
        except Exception as exc:
            return self._fail(getattr(exc, "code", None) or type(exc).__name__)

    def refresh(self) -> dict[str, Any]:
        """Refresh broker evidence with the existing in-memory provider; never perform OAuth."""
        with self._lock:
            activation = self._activation
            account_reference = self._account_reference
        provider = getattr(activation, "provider", None) if activation is not None else None
        if provider is None or not account_reference:
            return self._fail("QUESTRADE_NOT_ACTIVATED")
        try:
            lease = memoryview(b"CSS_QUESTRADE_READ_ONLY")
            balances = provider.fetch("BALANCES", authorization=lease, parameters={"account_reference": account_reference})
            positions = provider.fetch("POSITIONS", authorization=lease, parameters={"account_reference": account_reference})
            snapshot = {"status": "AVAILABLE", "selected_broker": "QUESTRADE", "canonical_mode": "LIVE_READ_ONLY", "balances": dict(balances), "positions": dict(positions), **SAFETY}
            self._cache.publish(snapshot)
            with self._lock:
                self._state = {"status": "READY", "reason": "refreshed", "attempted": True, "provider_available": True, **SAFETY}
                return dict(self._state)
        except Exception as exc:
            return self._fail(getattr(exc, "code", None) or type(exc).__name__)


    def _fail(self, reason: str) -> dict[str, Any]:
        with self._lock:
            self._state = {"status": "UNAVAILABLE", "reason": str(reason), "attempted": True, "provider_available": False, **SAFETY}
            return dict(self._state)


def _select_account_reference(payload: Mapping[str, Any]) -> str | None:
    rows = payload.get("accounts")
    if not isinstance(rows, list):
        return None
    candidates = [row for row in rows if isinstance(row, Mapping)]
    preferred = [row for row in candidates if bool(row.get("isPrimary")) and str(row.get("status") or "").upper() in {"ACTIVE", "OPEN"}]
    chosen = preferred[0] if len(preferred) == 1 else (candidates[0] if len(candidates) == 1 else None)
    if chosen is None:
        return None
    value = chosen.get("number") or chosen.get("accountNumber") or chosen.get("id")
    return str(value).strip() if value not in (None, "") else None


__all__ = ["QuestradeMissionControlActivationCoordinator"]
