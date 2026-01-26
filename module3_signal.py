# module3_signal.py

class VWAPMeanReversionSignal:
    """
    Module 3 prompt-generation logic.
    PROMPT-ONLY. No execution. No sizing. No broker logic.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._last_prompt_bar = None

    def evaluate(self, state):
        # 1) Regime gate must ALLOW
        if not state.regime_allow:
            return None

        # 2) Cooldown protection
        if self._last_prompt_bar is not None:
            if state.bar_index - self._last_prompt_bar < self.cfg.prompt_cooldown_bars:
                return None

        # 3) VWAP distance (bps)
        dist_bps = abs(state.price - state.vwap) / state.vwap * 10_000
        if dist_bps < self.cfg.vwap_reversion_bps:
            return None

        # 4) Momentum slowing check
        if not state.momentum_slowing:
            return None

        # 5) Confidence score (bounded)
        confidence = min(0.95, dist_bps / 30.0)
        if confidence < self.cfg.min_confidence:
            return None

        # 6) Build prompt
        self._last_prompt_bar = state.bar_index

        return {
            "strategy": "VWAP_MEAN_REVERSION",
            "symbol": state.symbol,
            "bias": "LONG" if state.price < state.vwap else "SHORT",
            "price": round(state.price, 2),
            "vwap": round(state.vwap, 2),
            "dist_bps": round(dist_bps, 1),
            "confidence": round(confidence, 2),
            "regime_reason": state.regime_reason,
            "timestamp": state.ts,
        }
