from dataclasses import dataclass


@dataclass
class RegimeResult:
    regime: str
    confidence: float
    trend_strength: float
    volatility: float
    vwap_distance: float


class MarketRegimeDetector:
    """
    CSS Market Regime Detector

    Classifies the market into:

    TREND
    MEAN_REVERSION
    BREAKOUT
    """

    def __init__(self):

        self.trend_threshold = 0.30
        self.volatility_threshold = 0.10
        self.vwap_distance_threshold = 0.25

    def classify(
        self,
        trend_pct: float,
        volatility_pct: float,
        vwap_spread_pct: float,
    ) -> RegimeResult:

        trend_strength = abs(trend_pct)
        volatility = abs(volatility_pct)
        vwap_distance = abs(vwap_spread_pct)

        # TREND regime
        if trend_strength > self.trend_threshold:
            return RegimeResult(
                regime="TREND",
                confidence=min(1.0, trend_strength),
                trend_strength=trend_strength,
                volatility=volatility,
                vwap_distance=vwap_distance,
            )

        # BREAKOUT regime
        if volatility > self.volatility_threshold:
            return RegimeResult(
                regime="BREAKOUT",
                confidence=min(1.0, volatility),
                trend_strength=trend_strength,
                volatility=volatility,
                vwap_distance=vwap_distance,
            )

        # Default regime
        return RegimeResult(
            regime="MEAN_REVERSION",
            confidence=1 - trend_strength,
            trend_strength=trend_strength,
            volatility=volatility,
            vwap_distance=vwap_distance,
        )