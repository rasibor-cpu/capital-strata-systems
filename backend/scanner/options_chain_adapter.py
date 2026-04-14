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
    Phase 1.5 (SAFE MODE WITH STAGGERED EXPIRY SUPPORT)

    - Generates normalized options contracts
    - Uses MOCK chains (no broker dependency yet)
    - Compatible with CSS scanner pipeline
    - NO execution at broker layer
    - Surfaces realistic expiry diversity for pricing realism

    Future:
    - Plug into real broker APIs (Alpaca / Tradier / IBKR)
    - Add real Greeks
    """

    def __init__(self):
        self.enabled = True
        self.max_contracts_per_symbol = 10
        self.expiry_buckets_days = [7, 14, 21, 30, 45]

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
        with staggered expiries for realism.
        """

        contracts: List[OptionContract] = []
        today = datetime.utcnow()

        strikes = [
            spot * 0.95,
            spot * 0.98,
            spot,
            spot * 1.02,
            spot * 1.05,
        ]

        for dte in self.expiry_buckets_days:
            expiry = (today + timedelta(days=dte)).date().isoformat()

            for strike in strikes:
                for option_type in ["CALL", "PUT"]:
                    moneyness = self._classify_moneyness(spot, strike, option_type)
                    premium = self._estimate_premium(
                        spot=spot,
                        strike=strike,
                        dte=dte,
                        option_type=option_type,
                    )

                    contract = OptionContract(
                        symbol=symbol,
                        option_type=option_type,
                        strike=round(strike, 6),
                        expiry=expiry,
                        price=round(premium, 6),
                        underlying_price=spot,
                        delta=self._mock_delta(option_type, spot, strike),
                        gamma=self._mock_gamma(dte),
                        theta=self._mock_theta(dte),
                        vega=self._mock_vega(dte),
                        moneyness=moneyness,
                        days_to_expiry=dte,
                    )

                    contracts.append(contract)

        contracts.sort(
            key=lambda c: (
                c.days_to_expiry,
                abs(c.strike - spot),
                0 if c.option_type == "CALL" else 1,
            )
        )

        return contracts[: self.max_contracts_per_symbol]


    # ========================================================
    # HELPERS
    # ========================================================

    def _classify_moneyness(self, spot: float, strike: float, opt_type: str) -> str:
        if opt_type == "CALL":
            if strike < spot:
                return "ITM"
            elif abs(strike - spot) / max(spot, 1e-9) < 0.01:
                return "ATM"
            else:
                return "OTM"
        else:
            if strike > spot:
                return "ITM"
            elif abs(strike - spot) / max(spot, 1e-9) < 0.01:
                return "ATM"
            else:
                return "OTM"

    def _estimate_premium(self, spot: float, strike: float, dte: int, option_type: str) -> float:
        if option_type == "CALL":
            intrinsic = max(0.0, spot - strike)
        else:
            intrinsic = max(0.0, strike - spot)

        moneyness_distance = abs(strike - spot) / max(spot, 1e-9)
        proximity_factor = max(0.35, 1.20 - moneyness_distance)
        time_value = spot * 0.0085 * (dte / 30.0) * proximity_factor
        noise = random.uniform(0.96, 1.04)

        premium = (intrinsic + time_value) * noise
        return max(0.50, premium)

    def _mock_delta(self, opt_type: str, spot: float, strike: float) -> float:
        base = (spot - strike) / max(spot, 1e-9)

        if opt_type == "CALL":
            return max(0.1, min(0.9, 0.5 + base))
        else:
            return max(-0.9, min(-0.1, -0.5 + base))

    def _mock_gamma(self, dte: int) -> float:
        if dte <= 7:
            return random.uniform(0.03, 0.07)
        if dte <= 21:
            return random.uniform(0.02, 0.05)
        return random.uniform(0.01, 0.035)

    def _mock_theta(self, dte: int) -> float:
        if dte <= 7:
            return random.uniform(-0.09, -0.03)
        if dte <= 21:
            return random.uniform(-0.06, -0.02)
        return random.uniform(-0.04, -0.01)

    def _mock_vega(self, dte: int) -> float:
        if dte <= 7:
            return random.uniform(0.03, 0.08)
        if dte <= 21:
            return random.uniform(0.06, 0.16)
        return random.uniform(0.10, 0.24)