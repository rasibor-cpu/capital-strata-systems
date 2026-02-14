"""
REA Capital – Phase 1 Smoke Test
--------------------------------

Purpose:
- Load .env reliably
- Validate OANDA adapter import
- Validate configuration
- Perform OANDA account summary handshake
- Display balance + NAV cleanly
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path


def _load_env() -> str:
    """
    Loads .env using python-dotenv.
    Returns the path used (or '' if not loaded).
    """
    try:
        from dotenv import load_dotenv
    except Exception:
        return ""

    # Try common locations:
    # 1) current working dir
    # 2) repo root inferred from this file location (backend/app -> repo root)
    candidates = []

    cwd_env = Path.cwd() / ".env"
    candidates.append(cwd_env)

    repo_root = Path(__file__).resolve().parents[2]  # .../backend/app -> repo root
    candidates.append(repo_root / ".env")

    for p in candidates:
        if p.exists():
            load_dotenv(dotenv_path=p, override=True)
            return str(p)

    # fallback: try default behavior (looks in cwd)
    load_dotenv(override=True)
    return ""


def run_smoke_test() -> None:
    env_path = _load_env()

    print("=" * 70)
    print("REA CAPITAL – PHASE 1 SMOKE TEST")
    print("=" * 70)
    print(f"dotenv_loaded_from: {env_path or '(default/unknown)'}")
    print(f"OANDA_API_KEY set?     {'YES' if os.getenv('OANDA_API_KEY') else 'NO'}")
    print(f"OANDA_ACCOUNT_ID set?  {'YES' if os.getenv('OANDA_ACCOUNT_ID') else 'NO'}")
    print(f"OANDA_BASE_URL:        {os.getenv('OANDA_BASE_URL', '(not set)')}")
    print()

    # -------------------------------------------------------------
    # Import Adapter
    # -------------------------------------------------------------
    try:
        from backend.app.brokers.oanda_adapter import OandaAdapter
        print("OANDA ADAPTER IMPORT: OK")
    except Exception as e:
        print("OANDA ADAPTER IMPORT: FAILED")
        print("Reason:", e)
        return

    # -------------------------------------------------------------
    # Instantiate Adapter
    # -------------------------------------------------------------
    try:
        adapter = OandaAdapter()
        print("OANDA CONFIG:", "OK" if adapter.is_configured() else "MISSING CREDS")
    except Exception as e:
        print("OANDA INIT FAILED")
        print("Reason:", e)
        return

    print()

    # -------------------------------------------------------------
    # Account Summary Handshake
    # -------------------------------------------------------------
    try:
        summary = adapter.get_account_summary()
        account = summary.get("account", {})

        balance = account.get("balance")
        nav = account.get("NAV")

        print("OANDA ACCOUNT SUMMARY")
        print("-" * 30)
        print(f"Balance: {balance}")
        print(f"NAV    : {nav}")

    except Exception as e:
        print("OANDA HANDSHAKE FAILED")
        print("Reason:", e)
        traceback.print_exc()

    print()
    print("=" * 70)
    print("PHASE 1 SMOKE TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_smoke_test()
