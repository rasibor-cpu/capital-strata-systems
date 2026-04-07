from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from datetime import datetime, timedelta
import random


# ============================================================
# OPTIONS CONTRACT MODEL
# ============================================================

@dataclass
class OptionContract:
    symbol: str            # underlying (e.g. BTC-USD, AAPL)
    option_type: str       # CALL / PUT
    strike: float
    expiry: str            # ISO date
    price: float           # option premium
    underlying_price: float

    # Greeks (placeholder for now)
    delta: float
    gamma: float
    theta: float
    vega: float

    # Derived
    moneyness: str         # ITM / ATM / OTM
    days_to_expiry: int

    def to_row(self) -> Dict[str, Any]:
        row = asdict(self)

        # Align with CSS pipeline expectations
        row["asset_class"] = "OPTIONS"
        row["price"] = self.price

        # CRITICAL SAFETY FLAG:
        # options are scan-visible only for now
        row["tradable"] = False

        # Initial placeholders for pipeline
        row["pressure_score"] = 0.0
        row["confluence_score"] = 0.0
        row["ai_score"] = 0.0
        row["tscore"] = 0.0

        return row


# ============================================================
# OPTIONS CHAIN ADAPTER
# ============================================================

class OptionsChainAdapter:
    """
    Phase 1 (SAFE MODE)

    - Generates normalized options contracts
    - Uses MOCK chains (no broker dependency yet)
    - Compatible with CSS scanner pipeline
    - NO execution (scan-only mode)

    Future:
    - Plug into real broker APIs (Alpaca / Tradier / IBKR)
    - Add real Greeks
    """

    def __init__(self):
        self.enabled = True
        self.max_contracts_per_symbol = 6

    # ========================================================
    # PUBLIC ENTRY
    # ========================================================

    def fetch_option_rows(self, underlying_rows: List[Dict]) -> List[Dict]:
        """
        Convert underlying assets into option candidates
        """

        if not self.enabled:
            return []

        option_rows: List[Dict] = []

        for row in underlying_rows:
            symbol = row.get("symbol")
            price = float(row.get("price", 0))

            if not symbol or price <= 0:
                continue

            contracts = self._generate_mock_chain(symbol, price)

            for c in contracts:
                option_rows.append(c.to_row())

        return option_rows

    # ========================================================
    # MOCK CHAIN GENERATOR (SAFE FOR NOW)
    # ========================================================

    def _generate_mock_chain(self, symbol: str, spot: float) -> List[OptionContract]:
        """
        Generates synthetic option chain around spot price
        """

        contracts: List[OptionContract] = []

        today = datetime.utcnow()
        expiry = (today + timedelta(days=14)).date().isoformat()

        # create strikes around spot
        strikes = [
            spot * 0.95,
            spot * 0.98,
            spot,
            spot * 1.02,
            spot * 1.05,
        ]

        for strike in strikes[:self.max_contracts_per_symbol]:
            option_type = random.choice(["CALL", "PUT"])

            moneyness = self._classify_moneyness(spot, strike, option_type)

            days_to_expiry = 14
            premium = self._estimate_premium(spot, strike, days_to_expiry)

            contract = OptionContract(
                symbol=symbol,
                option_type=option_type,
                strike=round(strike, 6),
                expiry=expiry,
                price=round(premium, 6),
                underlying_price=spot,
                delta=self._mock_delta(option_type, spot, strike),
                gamma=random.uniform(0.01, 0.05),
                theta=random.uniform(-0.05, -0.01),
                vega=random.uniform(0.05, 0.2),
                moneyness=moneyness,
                days_to_expiry=days_to_expiry,
            )

            contracts.append(contract)

        return contracts

    # ========================================================
    # HELPERS
    # ========================================================

    def _classify_moneyness(self, spot: float, strike: float, opt_type: str) -> str:
        if opt_type == "CALL":
            if strike < spot:
                return "ITM"
            elif abs(strike - spot) / spot < 0.01:
                return "ATM"
            else:
                return "OTM"
        else:
            if strike > spot:
                return "ITM"
            elif abs(strike - spot) / spot < 0.01:
                return "ATM"
            else:
                return "OTM"

    def _estimate_premium(self, spot: float, strike: float, dte: int) -> float:
        intrinsic = max(0.0, spot - strike) if spot > strike else max(0.0, strike - spot)
        time_value = spot * 0.01 * (dte / 30)
        noise = random.uniform(0.9, 1.1)
        return (intrinsic + time_value) * noise

    def _mock_delta(self, opt_type: str, spot: float, strike: float) -> float:
        base = (spot - strike) / spot

        if opt_type == "CALL":
            return max(0.1, min(0.9, 0.5 + base))
        else:
            return max(-0.9, min(-0.1, -0.5 + base))