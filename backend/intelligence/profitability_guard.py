# PCNRASS SAFE MODULE
# Profitability Guard v2 (Liquidity + Volatility + Pressure + Acceleration)

class ProfitabilityGuard:
    def __init__(self):
        # Core thresholds
        self.min_score = 70
        self.min_probability = 0.60

        # VWAP
        self.min_vwap_edge = 0.002   # 0.2%
        self.max_vwap_edge = 0.02    # avoid overextension

        # Liquidity
        self.min_liquidity_score = 60
        self.max_spread_pct = 0.003  # 0.3%

        # Volatility band
        self.min_volatility = 0.005
        self.max_volatility = 0.05

        # Momentum / acceleration
        self.min_acceleration = 0.1

        # Pressure (order flow proxy)
        self.min_pressure = 50

        # Allowed regimes
        self.allowed_regimes = ["TREND", "MOMENTUM"]

    def evaluate(self, signal: dict) -> tuple:
        """
        Returns: (approved: bool, reason: str)
        """

        score = signal.get("score", 0)
        probability = signal.get("probability", 0)
        vwap_edge = signal.get("vwap_edge", 0)
        regime = signal.get("regime", "NEUTRAL")

        liquidity_score = signal.get("liquidity_score", 0)
        spread_pct = signal.get("spread_pct", 999)

        volatility = signal.get("volatility", 0)
        acceleration = signal.get("acceleration", 0)
        pressure = signal.get("pressure_score", 0)

        # 1. Score
        if score < self.min_score:
            return False, "LOW_SCORE"

        # 2. Probability
        if probability < self.min_probability:
            return False, "LOW_PROBABILITY"

        # 3. VWAP edge (min)
        if abs(vwap_edge) < self.min_vwap_edge:
            return False, "WEAK_VWAP_EDGE"

        # 4. VWAP overextension
        if abs(vwap_edge) > self.max_vwap_edge:
            return False, "OVEREXTENDED_MOVE"

        # 5. Liquidity
        if liquidity_score < self.min_liquidity_score:
            return False, "LOW_LIQUIDITY"

        # 6. Spread
        if spread_pct > self.max_spread_pct:
            return False, "SPREAD_TOO_WIDE"

        # 7. Volatility (too flat)
        if volatility < self.min_volatility:
            return False, "TOO_FLAT"

        # 8. Volatility (too chaotic)
        if volatility > self.max_volatility:
            return False, "TOO_VOLATILE"

        # 9. Acceleration
        if abs(acceleration) < self.min_acceleration:
            return False, "WEAK_ACCELERATION"

        # 10. Pressure
        if abs(pressure) < self.min_pressure:
            return False, "LOW_PRESSURE"

        # 11. Regime alignment
        if regime not in self.allowed_regimes:
            return False, "BAD_REGIME"

        return True, "APPROVED"
