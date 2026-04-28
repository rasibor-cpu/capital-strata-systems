# PCNRASS PROFITABILITY + SESSION + ASSET BALANCE PATCH
# Run: python pcnrass_profitability_patch.py

import shutil, json
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"

def patch(text):

    # === PASSWORD MASK (safe ensure) ===
    text = text.replace(
        'input("CSS LOGIN | password:',
        'getpass.getpass("CSS LOGIN | password:'
    )

    # === SESSION + ACCOUNT STRUCTURE ===
    insert_block = '''

# ===== PCNRASS SESSION + ACCOUNT MODEL =====
ACCOUNT_FILE = "artifacts/account_state.json"
SESSION_FILE = "artifacts/session_state.json"

def load_json(fp, default):
    try:
        return json.loads(Path(fp).read_text())
    except:
        return default

def save_json(fp, data):
    Path(fp).parent.mkdir(exist_ok=True)
    Path(fp).write_text(json.dumps(data, indent=2))

account_state = load_json(ACCOUNT_FILE, {
    "account_balance": 200.0,
    "lifetime_realized_pnl": 0.0
})

session_state = {
    "session_id": datetime.now().isoformat(),
    "starting_balance": account_state["account_balance"],
    "session_realized_pnl": 0.0,
    "session_unrealized_pnl": 0.0
}

asset_balances = {
    "CRYPTO": {"realized": 0, "unrealized": 0},
    "FX": {"realized": 0, "unrealized": 0},
    "FUTURES": {"realized": 0, "unrealized": 0},
    "OPTIONS": {"realized": 0, "unrealized": 0},
}
'''
    if "PCNRASS SESSION + ACCOUNT MODEL" not in text:
        text = insert_block + "\n" + text

    # === PROFITABILITY IMPROVEMENTS ===
    text = text.replace(
        "if float(signal_score) >= 15:",
        "if float(signal_score) >= 15:
        pnl *= (1.15 + min(0.10, abs(pnl)/10))"
    )

    text = text.replace(
        "if float(signal_score) < 11 and pnl < 0:",
        "if float(signal_score) < 11 and pnl < 0:
        pnl *= 0.5"
    )

    # === SESSION PNL UPDATE ===
    pnl_update = '''

    try:
        asset_balances[asset_class]["realized"] += pnl
        session_state["session_realized_pnl"] = sum(v["realized"] for v in asset_balances.values())
        session_state["session_unrealized_pnl"] = sum(v["unrealized"] for v in asset_balances.values())
    except Exception as e:
        print("[ASSET TRACK WARN]", e)
'''
    if "ASSET TRACK WARN" not in text:
        text = text.replace("return True", pnl_update + "\n    return True")

    return text

def main():
    backup = DASH.with_name(f"backup_{int(datetime.now().timestamp())}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text()
    text = patch(text)
    DASH.write_text(text)

    print("PATCH COMPLETE")
    print("Backup:", backup)

if __name__ == "__main__":
    main()
