from __future__ import annotations

from typing import Dict, List
from backend.common.numeric_utils import clamp


def clamp01(v: float) -> float:
    return clamp(v, 0.0, 1.0)


class CapitalReallocationEngine:
    """
    CSS Capital Reallocation Engine (Phase 1 - Advisory Only)

    Purpose:
    - Evaluate open positions continuously
    - Detect weakening trades
    - Compare against new opportunities
    - Recommend capital movement decisions

    IMPORTANT:
    - Does NOT execute trades
    - Only produces advisory signals
    """

    def __init__(
        self,
        min_hold_cycles: int = 2,
        strong_threshold: float = 0.75,
        reduce_threshold: float = 0.50,
        exit_threshold: float = 0.35,
    ):
        self.min_hold_cycles = min_hold_cycles
        self.strong_threshold = strong_threshold
        self.reduce_threshold = reduce_threshold
        self.exit_threshold = exit_threshold

    def score_position(self, pos: Dict) -> Dict:
        """
        Compute reallocation score for a position
        """

        # Core signals (safe extraction)
        pnl = float(pos.get("unrealized_pnl_pct", 0.0))
        momentum = float(pos.get("momentum", 0.0))
        confluence = float(pos.get("confluence_score", 0.0))
        pressure = float(pos.get("pressure_score", 0.0))
        regime_ok = 1.0 if pos.get("regime_ok", True) else 0.0
        hold_cycles = int(pos.get("hold_cycles", 0))

        # Normalize components
        pnl_score = clamp01((pnl + 0.02) / 0.04)  # maps -2% → 0, +2% → 1
        momentum_score = clamp01(momentum)
        confluence_score = clamp01(confluence)
        pressure_score = clamp01(pressure)

        # Core composite score
        base_score = (
            0.25 * pnl_score
            + 0.20 * momentum_score
            + 0.20 * confluence_score
            + 0.15 * pressure_score
            + 0.20 * regime_ok
        )

        # Penalty for stalling
        deterioration_penalty = 0.0
        if momentum_score < 0.2:
            deterioration_penalty += 0.15
        if pnl < -0.01:
            deterioration_penalty += 0.15

        # Early hold protection
        if hold_cycles < self.min_hold_cycles:
            base_score = max(base_score, 0.5)

        final_score = clamp01(base_score - deterioration_penalty)

        return {
            "symbol": pos.get("symbol"),
            "score": final_score,
            "pnl": pnl,
            "momentum": momentum_score,
            "hold_cycles": hold_cycles,
        }

    def evaluate(
        self,
        open_positions: List[Dict],
        candidate_trades: List[Dict],
    ) -> Dict:
        """
        Main evaluation loop
        """

        scored_positions = [self.score_position(p) for p in open_positions]

        if not scored_positions:
            return {
                "actions": [],
                "notes": ["No open positions"],
            }

        # Find best new opportunity
        best_candidate_score = 0.0
        best_candidate = None

        for c in candidate_trades:
            s = float(c.get("score", 0.0))
            if s > best_candidate_score:
                best_candidate_score = s
                best_candidate = c

        actions = []
        notes = []

        for p in scored_positions:
            score = p["score"]

            if score >= self.strong_threshold:
                action = "HOLD_STRONG"

            elif score >= self.reduce_threshold:
                action = "HOLD_MONITOR"

            elif score >= self.exit_threshold:
                action = "REDUCE"

            else:
                # Only rotate if a better opportunity exists
                if best_candidate_score > score + 0.15:
                    action = "ROTATE_OUT"
                else:
                    action = "REDUCE"

            actions.append({
                "symbol": p["symbol"],
                "score": round(score, 3),
                "action": action,
                "pnl": round(p["pnl"], 4),
            })

        # Add diagnostic note
        if best_candidate:
            notes.append(
                f"Best candidate: {best_candidate.get('symbol')} "
                f"(score={round(best_candidate_score,3)})"
            )

        return {
            "actions": actions,
            "notes": notes,
        }