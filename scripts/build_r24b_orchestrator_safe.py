from pathlib import Path

ORCH = Path("backend/intelligence/trade_decision_orchestrator.py")

def main():
    code = ORCH.read_text(encoding="utf-8")

    # -------------------------------
    # 1. IMPORTS (SAFE INSERT)
    # -------------------------------
    if "CapitalAllocator" not in code:
        code = code.replace(
            "from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine",
            "from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine\n"
            "from backend.intelligence.capital_allocator import CapitalAllocator\n"
            "from backend.intelligence.adaptive_exit_engine import AdaptiveExitEngine"
        )

    # -------------------------------
    # 2. INIT EXTENSION (SAFE)
    # -------------------------------
    if "self.capital_allocator" not in code:
        code = code.replace(
            "self.acceleration_engine = PressureAccelerationEngine()",
            "self.acceleration_engine = PressureAccelerationEngine()\n"
            "        self.capital_allocator = CapitalAllocator()\n"
            "        self.exit_engine = AdaptiveExitEngine()"
        )

    # -------------------------------
    # 3. APPEND DECISION ENRICHMENT (SAFE — NO REPLACEMENT)
    # -------------------------------
    if "def enrich_decision" not in code:
        code += """

    def enrich_decision(self, decision: dict, asset_class: str, confidence: float, regime: str):
        try:
            allocation = self.capital_allocator.allocate(
                asset_class=asset_class,
                confidence=confidence,
                regime=regime
            )

            exit_plan = self.exit_engine.get_exit_plan(
                asset_class=asset_class,
                regime=regime,
                confidence=confidence
            )

            decision.update({
                "capital_allocation": allocation,
                "position_size": allocation.get("size", 0),
                "max_hold_cycles": exit_plan.get("max_cycles", 3),
                "exit_type": exit_plan.get("type", "adaptive")
            })

        except Exception as e:
            decision["enrichment_error"] = str(e)

        return decision
"""

    ORCH.write_text(code, encoding="utf-8")
    print("[SUCCESS] R24B safe integration added")

if __name__ == "__main__":
    main()