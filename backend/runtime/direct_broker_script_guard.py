"""CSS-118: standalone scripts that post orders straight to a broker bypass every CSS gate.

`run_live_manual.py` and `backend/app/oanda_trade_smoketest.py` call the OANDA REST API
directly (no consent, personality, capital governor, AntiBleed, R7/R14F, kill switch or
pilot governance). They are closed in code. Re-opening one requires a reviewed source change
and explicit owner approval; no environment variable or configuration can re-open them.
"""
from __future__ import annotations

import sys

DIRECT_BROKER_SCRIPTS_PERMITTED = False
REFUSAL_EXIT_CODE = 3


def refuse_direct_broker_script(name: str) -> int | None:
    """Return an exit code when the script must not run (always, unless permitted in code)."""
    if DIRECT_BROKER_SCRIPTS_PERMITTED:
        return None
    print(f"[{name}] REFUSED: direct broker order scripts bypass the CSS governed router and are disabled "
          "(CSS-118). No order was sent.", file=sys.stderr)
    return REFUSAL_EXIT_CODE
