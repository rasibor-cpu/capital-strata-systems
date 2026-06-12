"""
Capital Strata Systems
Phase 97B.2

OANDA Margin Adapter
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from engine.risk.broker_margin_contract import (
    BrokerMarginProvider,
    BrokerMarginSnapshot,
)


class OandaMarginAdapter(BrokerMarginProvider):
    """
    OANDA margin adapter.

    No execution logic.
    No trade-gate integration.
    Deterministic simulated fallback is preserved for all LIVE failures.
    """

    def __init__(
        self,
        account_id: str = "SIMULATED-OANDA",
        available_margin: float = 10000.0,
        required_margin: float = 2000.0,
        mode: str = "SIMULATED",
        adapter_factory: Callable[[], Any] | None = None,
    ):
        self.account_id = account_id
        self.available_margin = float(available_margin)
        self.required_margin = float(required_margin)
        self.mode = self._normalize_mode(mode)
        self.adapter_factory = adapter_factory
        self.last_note = "SIMULATED_MARGIN_SNAPSHOT"

    def get_margin_snapshot(self) -> BrokerMarginSnapshot:
        if self.mode == "LIVE":
            return self._get_live_margin_snapshot()
        return self._simulated_snapshot()

    def _get_live_margin_snapshot(self) -> BrokerMarginSnapshot:
        try:
            adapter = self._build_oanda_adapter()
            if adapter is None:
                return self._fallback_snapshot("LIVE_FALLBACK_NO_OANDA_ADAPTER")

            if hasattr(adapter, "is_configured") and not adapter.is_configured():
                return self._fallback_snapshot("LIVE_FALLBACK_OANDA_NOT_CONFIGURED")

            summary = adapter.get_account_summary()
            account = self._extract_account_payload(summary)
            if not account:
                return self._fallback_snapshot("LIVE_FALLBACK_ACCOUNT_SUMMARY_UNAVAILABLE")

            snapshot = self._snapshot_from_account_payload(
                account=account,
                account_id=str(getattr(adapter, "account_id", None) or self.account_id),
            )
            self.last_note = "LIVE_MARGIN_SNAPSHOT_OK"
            return snapshot
        except Exception as exc:
            return self._fallback_snapshot(f"LIVE_FALLBACK_ERROR_{str(exc)[:80]}")

    def _build_oanda_adapter(self) -> Any:
        if self.adapter_factory is not None:
            return self.adapter_factory()

        try:
            self._load_existing_oanda_credentials()
            from backend.app.brokers.oanda_adapter import OandaAdapter

            return OandaAdapter()
        except Exception as exc:
            self.last_note = f"LIVE_FALLBACK_ADAPTER_IMPORT_ERROR_{str(exc)[:80]}"
            return None

    def _load_existing_oanda_credentials(self) -> None:
        try:
            from backend.app.brokers.credential_loader import load_credentials

            credentials = load_credentials("oanda") or {}
        except Exception:
            credentials = {}

        for key in (
            "OANDA_API_KEY",
            "OANDA_ACCESS_TOKEN",
            "OANDA_TOKEN",
            "OANDA_ACCOUNT_ID",
            "OANDA_PRACTICE_ACCOUNT_ID",
            "OANDA_ENV",
        ):
            value = credentials.get(key)
            if value and not os.getenv(key):
                os.environ[key] = str(value)

    def _snapshot_from_account_payload(
        self,
        *,
        account: dict[str, Any],
        account_id: str,
    ) -> BrokerMarginSnapshot:
        required = self._to_float(
            account.get("marginUsed")
            or account.get("margin_used")
            or account.get("requiredMargin")
            or account.get("required_margin")
        )
        available = self._to_float(
            account.get("NAV")
            or account.get("nav")
            or account.get("marginAvailable")
            or account.get("margin_available")
            or account.get("availableMargin")
            or account.get("available_margin")
        )
        free = self._to_float(
            account.get("marginAvailable")
            or account.get("margin_available")
            or account.get("freeMargin")
            or account.get("free_margin")
        )
        utilization = 0.0
        if available > 0:
            utilization = (required / available) * 100.0

        return BrokerMarginSnapshot(
            broker_name="OANDA",
            account_id=account_id or self.account_id,
            required_margin=round(required, 2),
            available_margin=round(available, 2),
            free_margin=round(free, 2),
            margin_utilization_pct=round(utilization, 2),
            margin_source="LIVE",
            timestamp=self._timestamp(),
        )

    def _simulated_snapshot(self) -> BrokerMarginSnapshot:
        free_margin = self.available_margin - self.required_margin

        utilization = 0.0
        if self.available_margin > 0:
            utilization = (
                self.required_margin / self.available_margin
            ) * 100.0

        return BrokerMarginSnapshot(
            broker_name="OANDA",
            account_id=self.account_id,
            required_margin=round(self.required_margin, 2),
            available_margin=round(self.available_margin, 2),
            free_margin=round(free_margin, 2),
            margin_utilization_pct=round(utilization, 2),
            margin_source="SIMULATED",
            timestamp=self._timestamp(),
        )

    def _fallback_snapshot(self, note: str) -> BrokerMarginSnapshot:
        self.last_note = note
        return self._simulated_snapshot()

    def _extract_account_payload(self, summary: Any) -> dict[str, Any] | None:
        if not isinstance(summary, dict):
            return None

        if "ok" in summary and not summary.get("ok"):
            return None

        data = summary.get("data") if isinstance(summary.get("data"), dict) else summary
        account = data.get("account") if isinstance(data, dict) else None
        if isinstance(account, dict):
            return account
        return None

    def _normalize_mode(self, mode: str) -> str:
        normalized = str(mode or "SIMULATED").strip().upper()
        if normalized not in {"SIMULATED", "LIVE"}:
            return "SIMULATED"
        return normalized

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
