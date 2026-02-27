import json
from decimal import Decimal

dr = Decimal("0")
cr = Decimal("0")

with open("audit_logs/journal.jsonl", "r", encoding="utf-8-sig") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        j = json.loads(line)
        amt = Decimal(str(j.get("amount", 0)))
        if j.get("side") == "DR":
            dr += amt
        elif j.get("side") == "CR":
            cr += amt

print("GLOBAL DR:", dr)
print("GLOBAL CR:", cr)
print("DIFF:", dr - cr)