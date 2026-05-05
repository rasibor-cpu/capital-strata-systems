from pathlib import Path

ORCH_PATH = Path("backend/intelligence/trade_decision_orchestrator.py")

def main():
    if not ORCH_PATH.exists():
        print("[FAIL] Orchestrator file not found")
        return

    code = ORCH_PATH.read_text(encoding="utf-8")

    # -------------------------------
    # 1. SAFE IMPORT INJECTION
    # -------------------------------
    if "from backend.intelligence.capital_allocator import" not in code:
        code = code.replace(
            "class TradeDecisionOrchestrator:",
            "from backend.intelligence.capital_allocator import CapitalAllocator\n"
            "from backend.intelligence.adaptive_exit_engine import AdaptiveExitEngine\n\n"
            "class TradeDecisionOrchestrator:"
        )

    # -------------------------------
    # 2. INIT INJECTION
    # -------------------------------
    if "self.capital_allocator" not in code:
        code = code.replace(
            "def __init__(self) -> None:",
            "def __init__(self) -> None:\n"
            "        self.capital_allocator = CapitalAllocator()\n"
            "        self.exit_engine = AdaptiveExitEngine()"
        )

    # -------------------------------
    # 3. DECISION PACKAGE INJECTION
    # -------------------------------
    anchor = "return {"
    if anchor in code and "capital_allocation" not in code:
        code = code.replace(
            anchor,
            "allocation = self.capital_allocator.allocate(\n"
            "            asset_class=asset_class,\n"
            "            confidence=confidence,\n"
            "            regime=regime\n"
            "        )\n\n"
            "        exit_plan = self.exit_engine.get_exit_plan(\n"
            "            asset_class=asset_class,\n"
            "            regime=regime,\n"
            "            confidence=confidence\n"
            "        )\n\n"
            "        return {"
        )

        # Now extend returned dictionary safely
        code = code.replace(
            "}",
            "    ,\n"
            "    'capital_allocation': allocation,\n"
            "    'position_size': allocation.get('size', 0),\n"
            "    'max_hold_cycles': exit_plan.get('max_cycles', 3),\n"
            "    'exit_type': exit_plan.get('type', 'adaptive')\n"
            "}"
        )

    # -------------------------------
    # WRITE BACK
    # -------------------------------
    ORCH_PATH.write_text(code, encoding="utf-8")
    print("[SUCCESS] R24 orchestrator integration applied")

if __name__ == "__main__":
    main()