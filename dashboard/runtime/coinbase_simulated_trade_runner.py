from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

from dashboard.runtime.broker_credential_check import (
    _extract_coinbase_accounts,
    _load_coinbase_credentials,
    _to_dict,
    load_local_env,
)
from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap


NON_USD_FIAT_CURRENCIES = {
    "AUD",
    "CAD",
    "CHF",
    "EUR",
    "GBP",
    "HKD",
    "JPY",
    "SGD",
}


def main() -> int:
    load_local_env()

    account_value_usd, holdings_count, warnings, price_provider = fetch_coinbase_value_usd()
    simulated_capital = account_value_usd if account_value_usd > 0 else 200.00

    output = DashboardRuntimeBootstrap().run(
        account_payload={
            "cash_balance": simulated_capital,
            "total_equity": simulated_capital,
            "buying_power": simulated_capital,
            "margin_used": 0.0,
            "available_margin": simulated_capital,
            "currency": "USD",
            "broker": "COINBASE",
            "account_mode": "paper",
        },
        broker_payload={
            "selected_broker": "COINBASE",
            "broker_mode": "paper",
            "connected": True,
            "live_trading_enabled": False,
            "last_heartbeat": "coinbase-read-only-verified",
        },
        positions_payload={
            "positions": build_simulated_positions(simulated_capital, price_provider),
        },
        market_payload={
            "trend_state": "SIMULATED_UPTREND",
            "volatility_state": "NORMAL",
            "liquidity_state": "COINBASE_VERIFIED",
            "mean_reversion_state": "NEUTRAL",
            "probability_state": "SIMULATED_FAVORABLE",
            "velocity_state": "RISING",
            "vwap_state": "ABOVE_VWAP",
            "vwap_distance": 0.0100,
            "vwap_elasticity": 0.7500,
            "momentum_state": "POSITIVE",
            "pressure_state": "SIMULATED_BUY_PRESSURE",
            "acceleration_state": "STABLE",
            "regime_state": "PAPER_COINBASE_READ_ONLY",
            "spread_state": "PUBLIC_TICKER",
            "execution_cost_state": "SIMULATED_ONLY",
            "signal_confluence_state": "PAPER_CONFIRMED",
        },
        governance_payload={
            "governance_enabled": True,
            "session_locked": False,
            "defensive_mode_active": False,
            "unified_trade_gate_active": True,
            "audit_enabled": True,
            "last_governance_event": "Coinbase read-only balance verified; simulated trades only",
        },
        risk_payload={
            "risk_state": "PAPER_ONLY",
            "gate_status": "LIVE_ORDERS_DISABLED",
            "current_drawdown_pct": 0.0,
            "max_drawdown_pct": 2.0,
            "daily_loss_limit": simulated_capital * 0.02,
            "position_limit": 10,
            "exposure_limit": simulated_capital * 0.25,
            "risk_limits_breached": [],
        },
        execution_payload={
            "execution_state": "SIMULATED_READY",
            "accepted_trade_count": 2,
            "rejected_trade_count": 0,
            "pending_trade_count": 0,
            "total_execution_cost": 0.0,
            "slippage_cost": 0.0,
            "spread_cost": 0.0,
            "fee_cost": 0.0,
            "avg_slippage_bps": 0.0,
            "avg_spread_bps": 0.0,
            "execution_cost_state": "NO_LIVE_ORDERS",
            "last_execution_event": "Two simulated Coinbase paper positions opened",
        },
        session_payload={
            "session_id": "COINBASE-SIM-SESSION",
            "user_id": "coinbase_read_only",
            "role": "TRADER",
            "cycle_number": 1,
            "engine_mode": "SAFE",
            "live_or_paper": "paper",
        },
        diagnostics_payload={
            "message": (
                f"Coinbase read-only holdings={holdings_count}; "
                f"warnings={len(warnings)}"
            ),
        },
    )

    print(output)

    if warnings:
        print("")
        print("==============================")
        print(" COINBASE VALUATION WARNINGS")
        print("==============================")
        for warning in warnings:
            print(f"- {warning}")
        print("==============================")

    return 0


def fetch_coinbase_value_usd() -> Tuple[float, int, List[str], Any]:
    api_key, api_secret, source = _load_coinbase_credentials()
    warnings: List[str] = []

    if not api_key or not api_secret:
        raise RuntimeError("Coinbase credentials not available for read-only check")

    from coinbase.rest import RESTClient  # type: ignore

    client = RESTClient(api_key=api_key, api_secret=api_secret)
    accounts = _extract_coinbase_accounts(_to_dict(client.get_accounts()))

    total_usd = 0.0
    valued_count = 0

    for account in accounts:
        if not isinstance(account, dict):
            continue

        currency = str(account.get("currency", "") or "").upper()
        available = account.get("available_balance", {})

        if not isinstance(available, dict):
            continue

        units = _to_float(available.get("value"))

        if units <= 0:
            continue

        price = fetch_usd_price(currency, client)

        if price <= 0:
            warnings.append(f"No USD valuation for {currency}; excluded from estimate")
            continue

        total_usd += units * price
        valued_count += 1

    if valued_count == 0:
        warnings.append(f"Coinbase credentials source {source} passed, but no balances were valued")

    return round(total_usd, 2), len(accounts), warnings, client


def build_simulated_positions(capital: float, price_provider: Any) -> List[Dict[str, Any]]:
    btc_price = fetch_usd_price("BTC", price_provider) or 65000.00
    eth_price = fetch_usd_price("ETH", price_provider) or 3000.00

    btc_exposure = max(capital * 0.03, 10.00)
    eth_exposure = max(capital * 0.02, 10.00)

    btc_unrealized = btc_exposure * 0.0065
    eth_unrealized = eth_exposure * -0.0025

    return [
        {
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "side": "LONG",
            "qty": btc_exposure / btc_price,
            "entry_price": btc_price * 0.9935,
            "current_price": btc_price,
            "unrealized_pnl": btc_unrealized,
            "realized_pnl": 0.0,
        },
        {
            "symbol": "ETH-USD",
            "asset_class": "CRYPTO",
            "side": "LONG",
            "qty": eth_exposure / eth_price,
            "entry_price": eth_price * 1.0025,
            "current_price": eth_price,
            "unrealized_pnl": eth_unrealized,
            "realized_pnl": 0.0,
        },
    ]


def fetch_usd_price(currency: str, price_provider: Any = None) -> float:
    symbol = str(currency or "").upper().strip()

    if symbol in {"USD", "USDC"}:
        return 1.0

    if symbol in NON_USD_FIAT_CURRENCIES:
        return 0.0

    if symbol == "ETH2":
        symbol = "ETH"

    if price_provider is not None:
        price = fetch_coinbase_product_price(symbol, price_provider)
        if price > 0:
            return price

    return fetch_public_usd_price(symbol)


def fetch_coinbase_product_price(currency: str, client: Any) -> float:
    product_id = f"{currency}-USD"

    try:
        product = _to_product_dict(client.get_product(product_id))
    except Exception:
        return 0.0

    for key in [
        "price",
        "mid_market_price",
        "best_bid_price",
        "best_ask_price",
        "best_bid",
        "best_ask",
    ]:
        value = _to_float(product.get(key))
        if value > 0:
            return value

    return 0.0


def fetch_public_usd_price(currency: str) -> float:
    symbol = str(currency or "").upper().strip()
    product_id = urllib.parse.quote(f"{symbol}-USD", safe="")
    url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return 0.0

    return _to_float(payload.get("price"))


def _to_product_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        if isinstance(value.get("product"), dict):
            return value["product"]
        return value

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            if isinstance(data.get("product"), dict):
                return data["product"]
            return data

    return {}


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
