# gemini_liquidity_filter.py
"""
CSS-GEMINI LIQUIDITY GUARDRAIL
Prevents execution in low-volume markets to avoid slippage.
"""
from audit_logger import get_audit

class LiquidityFilter:
    def __init__(self):
        self.audit = get_audit()
        self.min_volume_24h = 1000000 # Institutional floor: $1M

    def has_sufficient_liquidity(self, asset: str, volume: float) -> bool:
        """Checks if the asset meets the minimum volume requirements."""
        if volume < self.min_volume_24h:
            self.audit.trade_rejected(asset, "Insufficient Liquidity", "liquidity_filter")
            return False
        return True