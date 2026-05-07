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