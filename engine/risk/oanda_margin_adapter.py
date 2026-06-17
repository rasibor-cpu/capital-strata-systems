from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable
from dataclasses import dataclass

from engine.risk.broker_margin_contract import BrokerMarginProvider
from engine.risk.margin_snapshot import MarginSnapshot
from engine.risk.margin_state import MarginState

@dataclass(frozen=True)
class LegacyCompatibleMarginSnapshot(MarginSnapshot):
    # Legacy fields mapping
    required_margin: float = 0.0
    available_margin: float = 0.0
    free_margin: float = 0.0
    margin_utilization_pct: float = 0.0
    margin_source: str = "LIVE"
    broker_name: str = "OANDA"


class OandaMarginAdapter(BrokerMarginProvider):
    """
    Authoritative OANDA margin adapter returning canonical MarginSnapshot.
    No execution logic. Read-only.
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

    def get_margin_snapshot(self) -> MarginSnapshot:
        if self.mode == "LIVE":
            return self._get_live_margin_snapshot()
        return self._simulated_snapshot()

    def _get_live_margin_snapshot(self) -> MarginSnapshot:
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
            from backend.app.brokers.oanda_adapter import OandaAdapter
            return OandaAdapter()
        except Exception as exc:
            self.last_note = f"LIVE_FALLBACK_ADAPTER_IMPORT_ERROR_{str(exc)[:80]}"
            return None

    def _snapshot_from_account_payload(
        self,
        *,
        account: dict[str, Any],
        account_id: str,
    ) -> MarginSnapshot:
        # 1. Parse Required Inputs
        margin_used_raw = self._to_float(
            account.get("marginUsed") or account.get("margin_used") or account.get("requiredMargin") or 0.0
        )
        nav_raw = self._to_float(account.get("NAV") or account.get("nav") or 0.0)
        balance_raw = self._to_float(account.get("balance") or nav_raw)
        margin_available_raw = self._to_float(
            account.get("marginAvailable") or account.get("margin_available") or account.get("freeMargin") or 0.0
        )

        # 2. Canonical mapping calculations
        equity = nav_raw
        cash = balance_raw
        buying_power = margin_available_raw
        maintenance_margin = margin_used_raw
        initial_margin = margin_used_raw
        margin_used = margin_used_raw
        margin_available = margin_available_raw

        if equity > 0:
            margin_ratio = margin_used / equity
            margin_utilization_pct = margin_ratio * 100.0
        else:
            margin_ratio = 0.0
            margin_utilization_pct = 0.0

        # 3. Canonical margin state classification
        if margin_ratio >= 1.0:
            margin_state = MarginState.LIQUIDATION_RISK
        elif margin_ratio >= 0.85:
            margin_state = MarginState.CRITICAL
        elif margin_ratio >= 0.70:
            margin_state = MarginState.RESTRICTED
        elif margin_ratio >= 0.50:
            margin_state = MarginState.WARNING
        else:
            margin_state = MarginState.NORMAL

        return LegacyCompatibleMarginSnapshot(
            broker="OANDA",
            account_id=account_id or self.account_id,
            timestamp=self._timestamp(),
            equity=round(equity, 2),
            cash=round(cash, 2),
            buying_power=round(buying_power, 2),
            maintenance_margin=round(maintenance_margin, 2),
            initial_margin=round(initial_margin, 2),
            margin_used=round(margin_used, 2),
            margin_available=round(margin_available, 2),
            margin_ratio=round(margin_ratio, 4),
            margin_state=margin_state,
            # Legacy Fields
            required_margin=round(margin_used, 2),
            available_margin=round(equity, 2),
            free_margin=round(buying_power, 2),
            margin_utilization_pct=round(margin_utilization_pct, 2),
            margin_source="LIVE",
            broker_name="OANDA"
        )

    def _simulated_snapshot(self) -> MarginSnapshot:
        free_margin = self.available_margin - self.required_margin
        equity = self.available_margin
        cash = self.available_margin
        margin_used = self.required_margin

        if equity > 0:
            margin_ratio = margin_used / equity
            margin_utilization_pct = margin_ratio * 100.0
        else:
            margin_ratio = 0.0
            margin_utilization_pct = 0.0

        if margin_ratio >= 1.0:
            margin_state = MarginState.LIQUIDATION_RISK
        elif margin_ratio >= 0.85:
            margin_state = MarginState.CRITICAL
        elif margin_ratio >= 0.70:
            margin_state = MarginState.RESTRICTED
        elif margin_ratio >= 0.50:
            margin_state = MarginState.WARNING
        else:
            margin_state = MarginState.NORMAL

        return LegacyCompatibleMarginSnapshot(
            broker="OANDA",
            account_id=self.account_id,
            timestamp=self._timestamp(),
            equity=round(equity, 2),
            cash=round(cash, 2),
            buying_power=round(free_margin, 2),
            maintenance_margin=round(margin_used, 2),
            initial_margin=round(margin_used, 2),
            margin_used=round(margin_used, 2),
            margin_available=round(free_margin, 2),
            margin_ratio=round(margin_ratio, 4),
            margin_state=margin_state,
            # Legacy Fields
            required_margin=round(margin_used, 2),
            available_margin=round(equity, 2),
            free_margin=round(free_margin, 2),
            margin_utilization_pct=round(margin_utilization_pct, 2),
            margin_source="SIMULATED",
            broker_name="OANDA"
        )

    def _fallback_snapshot(self, note: str) -> MarginSnapshot:
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
