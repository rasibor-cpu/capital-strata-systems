from pathlib import Path
import shutil
import subprocess
import sys

p = Path("scripts/css_live_dashboard.py")
backup = Path("scripts/css_live_dashboard.py.bak_before_closed_trade_ledger_v2")

text = p.read_text(encoding="utf-8")
shutil.copy2(p, backup)

if "CLOSED_TRADE_LEDGER_PATH" not in text:
    anchor = "PAPER_PROFIT_TARGET_MIN_AGE_CYCLES = 2\n"
    insert = '''PAPER_PROFIT_TARGET_MIN_AGE_CYCLES = 2

CLOSED_TRADE_LEDGER_PATH = Path("audit_logs") / "closed_trades.jsonl"
CLOSED_TRADE_LEDGER_MARKER = "CLOSED_TRADE_LEDGER"
'''
    if anchor not in text:
        raise RuntimeError("Profit target constant anchor not found.")
    text = text.replace(anchor, insert, 1)

if "def append_closed_trade_ledger" not in text:
    anchor = "\ndef should_take_dashboard_paper_profit(pos: dict) -> bool:\n"
    helper = r'''
def append_closed_trade_ledger(pos: dict, reason: str, realized: float) -> None:
    """CLOSED_TRADE_LEDGER: append one durable JSONL record for dashboard paper exits."""
    try:
        CLOSED_TRADE_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        ctx = globals().get("SESSION_USER_CTX") or {}
        record = {
            "marker": CLOSED_TRADE_LEDGER_MARKER,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "symbol": str(pos.get("symbol", "")),
            "asset_class": str(pos.get("asset_class", "")),
            "exit_reason": str(reason),
            "realized_pnl": float(realized),
            "floating_at_exit": float(pos.get("floating", 0.0)),
            "engine_mode": str(globals().get("ENGINE_MODE", "")),
            "broker_mode": str(globals().get("SELECTED_BROKER_MODE", "")),
            "selected_broker": str(globals().get("SELECTED_BROKER", "")),
            "cycle": int(globals().get("cycle", 0) or 0),
            "session_id": str(ctx.get("session_id", "")),
            "user_id": str(ctx.get("user_id", "")),
        }
        with CLOSED_TRADE_LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\\n")
    except Exception as exc:
        print(f"[CLOSED_TRADE_LEDGER WARN] {exc}")


'''
    if anchor not in text:
        raise RuntimeError("should_take_dashboard_paper_profit anchor not found.")
    text = text.replace(anchor, "\n" + helper + anchor, 1)

if "append_closed_trade_ledger(pos, reason, realized)" not in text:
    anchor = '''    realized = round(pos["floating"], 4)

    # === TRACKER UPDATE ===
'''
    replacement = '''    realized = round(pos["floating"], 4)
    append_closed_trade_ledger(pos, reason, realized)

    # === TRACKER UPDATE ===
'''
    if anchor not in text:
        raise RuntimeError("book_position_exit realized anchor not found.")
    text = text.replace(anchor, replacement, 1)

p.write_text(text, encoding="utf-8")

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(p)],
    capture_output=True,
    text=True,
)
print(result.stdout)
print(result.stderr)
print("COMPILE_EXIT_CODE", result.returncode)

fresh = p.read_text(encoding="utf-8")
for marker in [
    "CLOSED_TRADE_LEDGER_PATH",
    "CLOSED_TRADE_LEDGER",
    "append_closed_trade_ledger",
]:
    print(marker, "FOUND" if marker in fresh else "MISSING")

if result.returncode != 0:
    sys.exit(result.returncode)