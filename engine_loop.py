"""
engine_loop.py — REA Capital Trading Engine (Prompt-Only, Ledger-Aware)
---------------------------------------------------------------------
Purpose:
- Orchestrates data readiness, regime gating, signal prompting
- Registers trade intents into the canonical ledger
- Optionally simulates fills (dry-run)
- Emits prompt + ledger snapshot
- NO execution, NO broker calls, NO auto-risk escalation
"""

from typing import Dict, Any, Optional
from datetime import datetime

# Optional imports (graceful fallbacks)
try:
    from regime.gate import RegimeGate  # type: ignore
except Exception:
    RegimeGate = None

try:
    from signals.vwap_mean_reversion import build_vwap_prompt_default_eps  # type: ignore
except Exception:
    build_vwap_prompt_default_eps = None

try:
    from utils.prompt_export import normalize_prompt  # type: ignore
except Exception:
    normalize_prompt = None

from ledger import TradeLedger


class EngineLoop:
    def __init__(
        self,
        min_bars_required: int = 40,
        per_symbol_limit: float = 5_000_000,
        gross_limit: float = 20_000_000,
        simulate_fills: bool = False,
    ):
        self.min_bars_required = min_bars_required
        self.simulate_fills = simulate_fills

        self.ledger = TradeLedger(
            per_symbol_limit=per_symbol_limit,
            gross_limit=gross_limit,
        )

        self.regime_gate = RegimeGate() if RegimeGate else None

    # -------------------------------------------------
    # Core engine step (called per symbol / timeframe)
    # -------------------------------------------------

    def step(
        self,
        symbol: str,
        bars_available: int,
        market_context: Dict[str, Any],
    ) -> Dict[str, Any]:

        diagnostics: Dict[str, Any] = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "bars_available": bars_available,
            "regime_allowed": False,
            "prompt_generated": False,
            "intent_registered": False,
            "ledger_snapshot": None,
        }

        # 1. Data readiness
        if bars_available < self.min_bars_required:
            diagnostics["blocked_reason"] = "INSUFFICIENT_BARS"
            return diagnostics

        # 2. Regime gate
        regime_label: Optional[str] = None
        if self.regime_gate:
            allowed, regime_label = self.regime_gate.evaluate(market_context)
            diagnostics["regime_allowed"] = allowed
            diagnostics["regime"] = regime_label
            if not allowed:
                diagnostics["blocked_reason"] = "REGIME_BLOCK"
                return diagnostics
        else:
            diagnostics["regime_allowed"] = True
            regime_label = "UNKNOWN"

        # 3. Prompt generation
        if not build_vwap_prompt_default_eps:
            diagnostics["blocked_reason"] = "SIGNAL_BUILDER_MISSING"
            return diagnostics

        prompt_payload = build_vwap_prompt_default_eps(
            symbol=symbol,
            market_context=market_context,
        )

        diagnostics["prompt_generated"] = True
        diagnostics["raw_prompt"] = prompt_payload

        # Optional normalization
        if normalize_prompt:
            diagnostics["normalized_prompt"] = normalize_prompt(prompt_payload)

        # 4. Register trade intent (prompt-only)
        intent = self.ledger.register_intent(
            symbol=symbol,
            side=prompt_payload.get("side", "BUY"),
            notional=float(prompt_payload.get("notional", 0)),
            rationale=prompt_payload.get("rationale", "VWAP mean-reversion signal"),
            regime=regime_label,
            price_hint=prompt_payload.get("price"),
        )

        diagnostics["intent_registered"] = True
        diagnostics["intent_id"] = intent.intent_id

        # 5. Optional simulation (dry-run only)
        if self.simulate_fills:
            ticket = self.ledger.approve_intent(
                intent_id=intent.intent_id,
                approved_by="ENGINE_AUTO",
                approval_level="AUTO",
                notes="Dry-run simulation",
            )
            breaches = self.ledger.simulate_fill(ticket.ticket_id)
            diagnostics["simulation"] = {
                "ticket_id": ticket.ticket_id,
                "breaches": breaches,
            }

        # 6. Emit ledger snapshot
        diagnostics["ledger_snapshot"] = self.ledger.snapshot()

        return diagnostics
