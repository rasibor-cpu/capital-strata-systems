from __future__ import annotations

# PCNRASS PROFITABILITY + SESSION/ASSET BALANCE PATCH v2
#
# Run from project root:
#   python pcnrass_profitability_patch_v2.py

import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"


SESSION_MODEL_BLOCK = """
# ===== PCNRASS SESSION + ACCOUNT + ASSET BALANCE MODEL =====
ACCOUNT_STATE_FILE = ARTIFACTS_DIR / "css_account_state_pcnrass.json"
SESSION_STATE_FILE = ARTIFACTS_DIR / "css_session_state_pcnrass.json"

def _pcnrass_read_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _pcnrass_write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

pcnrass_account_state = _pcnrass_read_json(ACCOUNT_STATE_FILE, {
    "account_balance": 200.0,
    "lifetime_realized_pnl": 0.0,
    "last_session_close": None,
})

pcnrass_session_state = {
    "session_id": datetime.now().isoformat(timespec="seconds"),
    "starting_account_balance": float(pcnrass_account_state.get("account_balance", 200.0)),
    "session_realized_pnl": 0.0,
    "session_unrealized_pnl": 0.0,
    "session_equity": float(pcnrass_account_state.get("account_balance", 200.0)),
}

pcnrass_asset_balances = {
    "CRYPTO": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FX": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FUTURES": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "OPTIONS": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
}

def pcnrass_refresh_balances(realized_by_asset, floating_by_asset):
    for asset in pcnrass_asset_balances:
        realized = float(realized_by_asset.get(asset, 0.0))
        unrealized = float(floating_by_asset.get(asset, 0.0))
        pcnrass_asset_balances[asset]["realized"] = round(realized, 4)
        pcnrass_asset_balances[asset]["unrealized"] = round(unrealized, 4)
        pcnrass_asset_balances[asset]["equity"] = round(realized + unrealized, 4)

    pcnrass_session_state["session_realized_pnl"] = round(
        sum(v["realized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_unrealized_pnl"] = round(
        sum(v["unrealized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_equity"] = round(
        float(pcnrass_session_state["starting_account_balance"])
        + float(pcnrass_session_state["session_realized_pnl"])
        + float(pcnrass_session_state["session_unrealized_pnl"]),
        4,
    )

    _pcnrass_write_json(SESSION_STATE_FILE, {
        "session": pcnrass_session_state,
        "assets": pcnrass_asset_balances,
        "account_balance_pending_close": pcnrass_session_state["session_equity"],
    })

def pcnrass_close_session_to_account():
    pcnrass_account_state["account_balance"] = round(float(pcnrass_session_state["session_equity"]), 4)
    pcnrass_account_state["lifetime_realized_pnl"] = round(
        float(pcnrass_account_state.get("lifetime_realized_pnl", 0.0))
        + float(pcnrass_session_state.get("session_realized_pnl", 0.0)),
        4,
    )
    pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")
    _pcnrass_write_json(ACCOUNT_STATE_FILE, pcnrass_account_state)

def pcnrass_print_balance_panel():
    print("\\n--- PCNRASS CAPITAL BALANCES ---")
    print(f"ACCOUNT BALANCE (SESSION START): ${float(pcnrass_session_state['starting_account_balance']):,.2f}")
    print(f"SESSION REALIZED PNL: {float(pcnrass_session_state['session_realized_pnl']):+.4f}")
    print(f"SESSION UNREALIZED PNL: {float(pcnrass_session_state['session_unrealized_pnl']):+.4f}")
    print(f"SESSION EQUITY: ${float(pcnrass_session_state['session_equity']):,.2f}")
    print("ASSET BALANCES:")
    for asset, bal in pcnrass_asset_balances.items():
        print(
            f"  {asset:<8} realized={bal['realized']:+.4f} "
            f"unrealized={bal['unrealized']:+.4f} equity={bal['equity']:+.4f}"
        )
"""


def replace_once(text, old, new, label):
    if old not in text:
        print(f"[SKIP] {label}: target not found or already patched.")
        return text
    return text.replace(old, new, 1)


def insert_session_model(text):
    if "PCNRASS SESSION + ACCOUNT + ASSET BALANCE MODEL" in text:
        return text

    marker = 'STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"'
    if marker not in text:
        raise RuntimeError("STATE_FILE marker not found.")
    return text.replace(marker, marker + "\n" + SESSION_MODEL_BLOCK, 1)


def fix_destroy_session(text):
    old = "session_manager.destroy_session(str(session_id), reason=reason)"
    new = """try:
        session_manager.destroy_session(str(session_id), reason=reason)
    except TypeError:
        try:
            session_manager.destroy_session(str(session_id))
        except TypeError:
            pass"""
    return replace_once(text, old, new, "destroy_session compatibility")


def add_balance_refresh(text):
    if "pcnrass_refresh_balances(realized_by_asset, display_by_asset)" in text:
        return text

    old = """        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
        broker_test_positions = mtm_engine.count_open_broker_test_positions()
        mtm_unrealized = round(sum(display_by_asset.values()), 4)
        open_positions = mtm_engine.count_open_positions()

        mtm_realized = total_realized_pnl()
"""
    new = """        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
        broker_test_positions = mtm_engine.count_open_broker_test_positions()
        mtm_unrealized = round(sum(display_by_asset.values()), 4)
        open_positions = mtm_engine.count_open_positions()

        mtm_realized = total_realized_pnl()

        realized_by_asset = {
            "CRYPTO": sum(crypto_pnl.values()),
            "FX": sum(fx_pnl.values()),
            "OPTIONS": sum(options_pnl.values()),
            "FUTURES": sum(futures_pnl.values()),
        }
        pcnrass_refresh_balances(realized_by_asset, display_by_asset)
"""
    return replace_once(text, old, new, "balance refresh")


def add_balance_display(text):
    if "pcnrass_print_balance_panel()" in text:
        return text

    old = """        print(f"LAST TRADE: {last_trade}")
        print("-" * 60)
"""
    new = """        print(f"LAST TRADE: {last_trade}")
        pcnrass_print_balance_panel()
        print("-" * 60)
"""
    return replace_once(text, old, new, "balance display")


def add_session_settlement(text):
    if "pcnrass_close_session_to_account()" in text:
        return text

    old = """            close_active_session(
                "operator_requested_stop",
                extra={
"""
    new = """            try:
                pcnrass_close_session_to_account()
            except Exception as e:
                print(f"[SESSION SETTLEMENT WARN] {e}")

            close_active_session(
                "operator_requested_stop",
                extra={
"""
    return replace_once(text, old, new, "session settlement")


def add_profitability_guardrail(text):
    if "if sig < 10.0:" in text:
        return text

    old = """                    min_sig, min_prob = mode_filter.get(ENGINE_MODE, (11.5, 0.65))

                    if sig < min_sig or prob < min_prob:
                        continue
"""
    new = """                    min_sig, min_prob = mode_filter.get(ENGINE_MODE, (11.5, 0.65))

                    # PCNRASS profitability guardrail:
                    # avoid very weak/noisy entries while preserving existing mode behavior.
                    if sig < min_sig or prob < min_prob:
                        continue

                    if sig < 10.0:
                        continue
"""
    return replace_once(text, old, new, "profitability guardrail")


def main():
    if not DASH.exists():
        raise SystemExit(f"Dashboard not found: {DASH}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASH.with_name(f"css_live_dashboard_BACKUP_BEFORE_PROFITABILITY_V2_{ts}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")
    text = insert_session_model(text)
    text = fix_destroy_session(text)
    text = add_balance_refresh(text)
    text = add_balance_display(text)
    text = add_session_settlement(text)
    text = add_profitability_guardrail(text)

    DASH.write_text(text, encoding="utf-8")

    print("[PCNRASS PROFITABILITY PATCH v2 COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("Added: session/account/asset balances")
    print("Fixed: destroy_session compatibility if target existed")
    print("Added: profitability weak-signal guardrail")
    print("Account balance settles only when operator stops session.")


if __name__ == "__main__":
    main()
