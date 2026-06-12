"""
Capital Strata Systems
Phase 97C

Coinbase Margin Adapter
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from engine.risk.broker_margin_contract import (
    BrokerMarginProvider,
    BrokerMarginSnapshot,
)


class CoinbaseMarginAdapter(BrokerMarginProvider):
    """
    Coinbase margin adapter.

    Coinbase spot defaults to non-margin unless live broker data clearly
    reports margin or leverage fields.

    No execution logic.
    No trade-gate integration.
    Deterministic simulated fallback is preserved for all LIVE failures.
    """

    def __init__(
        self,
        account_id: str = "SIMULATED-COINBASE",
        available_margin: float = 10000.0,
        required_margin: float = 0.0,
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
            adapter = self._build_coinbase_adapter()
            if adapter is None:
                return self._fallback_snapshot("LIVE_FALLBACK_NO_COINBASE_ADAPTER")

            payload = self._load_live_payload(adapter)
            if payload is None:
                return self._fallback_snapshot("LIVE_FALLBACK_COINBASE_ACCOUNT_UNAVAILABLE")

            snapshot = self._snapshot_from_live_payload(
                payload=payload,
                account_id=str(getattr(adapter, "account_id", None) or self.account_id),
            )
            self.last_note = "LIVE_MARGIN_SNAPSHOT_OK"
            return snapshot
        except Exception as exc:
            return self._fallback_snapshot(f"LIVE_FALLBACK_ERROR_{str(exc)[:80]}")

    def _build_coinbase_adapter(self) -> Any:
        if self.adapter_factory is not None:
            return self.adapter_factory()

        try:
            from backend.app.brokers.broker_bootstrap import initialize_broker

            return initialize_broker("coinbase", mode="live")
        except Exception as exc:
            self.last_note = f"LIVE_FALLBACK_ADAPTER_INIT_ERROR_{str(exc)[:80]}"
            return None

    def _load_live_payload(self, adapter: Any) -> Any:
        for method_name in (
            "get_margin_summary",
            "get_portfolio_summary",
            "get_account_summary",
            "get_account_balance",
            "get_balance",
            "get_account",
            "get_accounts",
        ):
            method = getattr(adapter, method_name, None)
            if not callable(method):
                continue
            payload = method()
            if payload is not None:
                return payload
        return None

    def _snapshot_from_live_payload(
        self,
        *,
        payload: Any,
        account_id: str,
    ) -> BrokerMarginSnapshot:
        plain = self._to_plain(payload)

        required = self._extract_first_float(
            plain,
            (
                "margin_used",
                "marginUsed",
                "required_margin",
                "requiredMargin",
                "initial_margin",
                "initialMargin",
            ),
        )
        available = self._extract_first_float(
            plain,
            (
                "available_margin",
                "availableMargin",
                "margin_available",
                "marginAvailable",
                "equity",
                "balance",
                "portfolio_balance",
                "available_balance",
            ),
        )
        free = self._extract_first_float(
            plain,
            (
                "free_margin",
                "freeMargin",
                "available_margin",
                "availableMargin",
                "margin_available",
                "marginAvailable",
            ),
        )

        if required is None:
            required = 0.0
        if available is None:
            available = 0.0
        if free is None:
            free = available - required

        utilization = 0.0
        if available > 0:
            utilization = (required / available) * 100.0

        return BrokerMarginSnapshot(
            broker_name="COINBASE",
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
            broker_name="COINBASE",
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

    def _extract_first_float(
        self,
        payload: Any,
        keys: tuple[str, ...],
    ) -> float | None:
        if payload is None:
            return None

        if isinstance(payload, list):
            total = 0.0
            found = False
            for item in payload:
                value = self._extract_first_float(item, keys)
                if value is not None:
                    total += value
                    found = True
            return total if found else None

        if not isinstance(payload, dict):
            return None

        for key in keys:
            if key not in payload:
                continue
            value = self._coerce_amount(payload.get(key))
            if value is not None:
                return value

        for nested_key in ("account", "accounts", "data", "summary", "portfolio"):
            nested = payload.get(nested_key)
            value = self._extract_first_float(nested, keys)
            if value is not None:
                return value

        return None

    def _coerce_amount(self, value: Any) -> float | None:
        if isinstance(value, dict):
            for key in ("value", "amount", "balance", "available"):
                if key in value:
                    return self._coerce_amount(value.get(key))
            return None

        try:
            return float(value)
        except Exception:
            return None

    def _to_plain(self, obj: Any) -> Any:
        if obj is None:
            return None

        if isinstance(obj, (dict, list, str, int, float, bool)):
            return obj

        if hasattr(obj, "to_dict"):
            try:
                return obj.to_dict()
            except Exception:
                pass

        if hasattr(obj, "__dict__"):
            try:
                return {
                    key: self._to_plain(value)
                    for key, value in vars(obj).items()
                    if not key.startswith("_")
                }
            except Exception:
                pass

        return obj

    def _normalize_mode(self, mode: str) -> str:
        normalized = str(mode or "SIMULATED").strip().upper()
        if normalized not in {"SIMULATED", "LIVE"}:
            return "SIMULATED"
        return normalized

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
