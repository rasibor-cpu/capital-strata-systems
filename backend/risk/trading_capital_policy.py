from __future__ import annotations

from typing import Any, Dict, Optional


class TradingCapitalPolicy:
    """
    CSS Trading Capital Policy

    Determines the capital base the engine should use for:
    - allocation
    - asset exposure limits
    - portfolio exposure limits

    Priority order:
    1. executor-reported available cash / buying power
    2. executor-reported total equity / portfolio value
    3. configured fallback capital

    This lets CSS enforce risk limits against real available capital
    instead of a hardcoded placeholder.
    """

    def __init__(
        self,
        fallback_capital: float = 250.0,
        reserve_ratio: float = 0.10,
        max_asset_exposure: float = 0.40,
        max_portfolio_exposure: float = 1.00,
    ) -> None:
        self.fallback_capital = float(fallback_capital)
        self.reserve_ratio = float(reserve_ratio)
        self.max_asset_exposure = float(max_asset_exposure)
        self.max_portfolio_exposure = float(max_portfolio_exposure)

    def get_policy_snapshot(self, executor: Any) -> Dict[str, float]:
        """
        Returns a normalized capital/risk snapshot for the current cycle.
        """
        gross_capital = self._discover_capital(executor)
        reserve_amount = gross_capital * self.reserve_ratio
        deployable_capital = max(gross_capital - reserve_amount, 0.0)

        asset_limit = deployable_capital * self.max_asset_exposure
        portfolio_limit = deployable_capital * self.max_portfolio_exposure

        return {
            "gross_capital": round(gross_capital, 2),
            "reserve_amount": round(reserve_amount, 2),
            "deployable_capital": round(deployable_capital, 2),
            "max_asset_exposure_pct": self.max_asset_exposure,
            "max_portfolio_exposure_pct": self.max_portfolio_exposure,
            "max_asset_exposure_usd": round(asset_limit, 2),
            "max_portfolio_exposure_usd": round(portfolio_limit, 2),
        }

    def _discover_capital(self, executor: Any) -> float:
        """
        Best-effort capital discovery from executor.
        """

        # 1) Preferred: directly exposed available cash / buying power
        for method_name in (
            "get_available_capital",
            "get_available_cash",
            "get_buying_power",
            "get_cash_balance",
        ):
            value = self._call_numeric_method(executor, method_name)
            if value is not None and value > 0:
                return value

        # 2) Secondary: account summary dict
        for method_name in (
            "get_account_summary",
            "get_portfolio_summary",
            "get_balance_summary",
        ):
            summary = self._call_method(executor, method_name)
            value = self._extract_capital_from_mapping(summary)
            if value is not None and value > 0:
                return value

        # 3) Fallback: accounts list / portfolio list
        for method_name in (
            "get_accounts",
            "list_accounts",
            "get_portfolios",
        ):
            payload = self._call_method(executor, method_name)
            value = self._extract_capital_from_collection(payload)
            if value is not None and value > 0:
                return value

        return self.fallback_capital

    def _call_numeric_method(self, obj: Any, method_name: str) -> Optional[float]:
        value = self._call_method(obj, method_name)
        return self._to_float(value)

    def _call_method(self, obj: Any, method_name: str) -> Any:
        try:
            method = getattr(obj, method_name, None)
            if callable(method):
                return method()
        except Exception:
            return None
        return None

    def _extract_capital_from_mapping(self, payload: Any) -> Optional[float]:
        if not isinstance(payload, dict):
            return None

        candidates = (
            "available_cash",
            "available_capital",
            "buying_power",
            "cash_balance",
            "cash",
            "usd_balance",
            "equity",
            "portfolio_value",
            "total_equity",
            "net_liquidation_value",
        )

        for key in candidates:
            value = self._to_float(payload.get(key))
            if value is not None and value > 0:
                return value

        for nested_key in ("account", "balances", "summary", "data", "portfolio"):
            nested = payload.get(nested_key)
            if isinstance(nested, dict):
                value = self._extract_capital_from_mapping(nested)
                if value is not None and value > 0:
                    return value

        return None

    def _extract_capital_from_collection(self, payload: Any) -> Optional[float]:
        if not isinstance(payload, (list, tuple)):
            return None

        total = 0.0
        found = False

        for item in payload:
            if not isinstance(item, dict):
                continue

            for key in (
                "available_cash",
                "cash_balance",
                "cash",
                "usd_balance",
                "balance",
                "equity",
                "value",
            ):
                value = self._to_float(item.get(key))
                if value is not None and value > 0:
                    total += value
                    found = True
                    break

        if found and total > 0:
            return total

        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    class DummyExecutor:
        def get_account_summary(self) -> Dict[str, float]:
            return {
                "available_cash": 1000.0,
                "equity": 1125.0,
            }

    policy = TradingCapitalPolicy(
        fallback_capital=250.0,
        reserve_ratio=0.10,
        max_asset_exposure=0.40,
        max_portfolio_exposure=1.00,
    )

    snapshot = policy.get_policy_snapshot(DummyExecutor())
    print(snapshot)