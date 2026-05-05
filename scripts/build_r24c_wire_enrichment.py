from pathlib import Path

ORCH = Path("backend/intelligence/trade_decision_orchestrator.py")

def main():
    code = ORCH.read_text(encoding="utf-8")

    # -------------------------------
    # FIND SAFE RETURN POINT
    # -------------------------------
    anchor = "return {"

    if "enrich_decision(" in code:
        print("[SKIP] Already wired")
        return

    if anchor not in code:
        print("[FAIL] return anchor not found")
        return

    # Replace ONLY first occurrence safely
    parts = code.split(anchor, 1)

    before = parts[0]
    after = parts[1]

    injection = """
        decision = {
"""

    # reconstruct decision dictionary start
    new_after = injection + after

    # Now append enrichment BEFORE final return
    new_after = new_after.replace(
        "}",
        "}\n\n        decision = self.enrich_decision(decision, asset_class, confidence, regime)\n        return decision",
        1
    )

    code = before + new_after

    ORCH.write_text(code, encoding="utf-8")

    print("[SUCCESS] R24C enrichment wired into decision flow")

if __name__ == "__main__":
    main()