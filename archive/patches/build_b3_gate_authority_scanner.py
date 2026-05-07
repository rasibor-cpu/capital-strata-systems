from pathlib import Path
from datetime import datetime
import json
import re

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "audit_logs" / "b3_gate_authority_scan.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

TARGET_EXTS = {".py"}

TRADE_PATTERNS = [
    "place_order",
    "place_market_buy",
    "register_position",
    "allocate_trade",
    "paper opened",
    "PAPER OPENED",
    "broker_order",
    "approve_trade",
    "CSSUnifiedTradeGate",
]

results = []

for path in ROOT.rglob("*.py"):
    if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.parts):
        continue

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue

    hits = []
    for pattern in TRADE_PATTERNS:
        if pattern in text:
            hits.append(pattern)

    if hits:
        has_gate = "CSSUnifiedTradeGate" in text or "approve_trade" in text

        results.append({
            "file": str(path.relative_to(ROOT)),
            "hits": hits,
            "has_gate_reference": has_gate,
            "risk": "REVIEW_REQUIRED" if not has_gate and any(
                p in hits for p in ["place_order", "place_market_buy", "register_position", "allocate_trade"]
            ) else "LOW_OR_CONTEXTUAL"
        })

OUT.write_text(json.dumps({
    "scan_time": datetime.now().isoformat(timespec="seconds"),
    "objective": "B3 Gate Authority Enforcement scan",
    "results": results,
}, indent=2), encoding="utf-8")

print("[B3 SCAN COMPLETE]")
print(f"Report written to: {OUT}")
print()
for item in results:
    if item["risk"] == "REVIEW_REQUIRED":
        print(f"[REVIEW_REQUIRED] {item['file']} | hits={item['hits']}")