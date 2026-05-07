from __future__ import annotations

from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap


def main() -> None:
    bootstrap = DashboardRuntimeBootstrap()

    output = bootstrap.run(
        account_payload={
            "cash_balance": 10000.00,
            "total_equity": 10250.00,
            "buying_power": 5000.00,
            "margin_used": 1000.00,
            "available_margin": 4000.00,
            "currency": "USD",
            "broker": "DEMO",
            "account_mode": "paper",
        },
        positions_payload={
            "positions": [
                {
                    "symbol": "BTC-USD",
                    "asset_class": "CRYPTO",
                    "side": "LONG",
                    "qty": 0.05,
                    "entry_price": 65000.00,
                    "current_price": 65500.00,
                    "unrealized_pnl": 25.00,
                    "realized_pnl": 0.00,
                },
                {
                    "symbol": "EUR_USD",
                    "asset_class": "FX",
                    "side": "SHORT",
                    "qty": 1000,
                    "entry_price": 1.0900,
                    "current_price": 1.0875,
                    "unrealized_pnl": 2.50,
                    "realized_pnl": 0.00,
                },
            ]
        },
        market_payload={
            "trend_state": "UPTREND",
            "volatility_state": "NORMAL",
            "liquidity_state": "HEALTHY",
            "mean_reversion_state": "NEUTRAL",
            "probability_state": "FAVORABLE",
            "velocity_state": "RISING",
            "vwap_state": "ABOVE_VWAP",
            "vwap_distance": 0.0125,
            "vwap_elasticity": 0.8300,
            "momentum_state": "POSITIVE",
            "pressure_state": "BUY_PRESSURE",
            "acceleration_state": "STABLE",
            "regime_state": "RISK_ON",
            "spread_state": "TIGHT",
            "execution_cost_state": "ACCEPTABLE",
            "signal_confluence_state": "CONFIRMED",
        },
        session_payload={
            "session_id": "DEMO-SESSION",
            "user_id": "demo_user",
            "role": "TRADER",
            "cycle_number": 1,
            "engine_mode": "SAFE",
            "live_or_paper": "paper",
        },
        diagnostics_payload={
            "message": "Demo runtime validation successful"
        },
    )

    print(output)


if __name__ == "__main__":
    main()
