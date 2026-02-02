"""
diagnose_regime_gate.py — REA Capital
Goal: Diagnose why RegimeGate is BLOCKing (without editing engine files).

What it does:
- Attempts to import RegimeGate from regime.gate
- Calls common methods (allow/allows/evaluate/check/on_bar) safely
- Prints returned structure and inferred allow/blocked state
- Writes a lightweight audit event if AccessAuditLogger is available
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_json(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False, default=str)
    except Exception:
        return str(x)


def main() -> int:
    # Optional audit logger
    audit = None
    try:
        from engine.security.access_audit_log import AccessAuditLogger  # type: ignore
        audit = AccessAuditLogger()
        audit.write("diagnostics_start", {"tool": "diagnose_regime_gate", "ts": utc_now_iso()})
    except Exception:
        audit = None

    try:
        from regime.gate import RegimeGate  # type: ignore
    except Exception as e:
        print("[ERROR] Could not import RegimeGate from regime.gate")
        print("Reason:", repr(e))
        if audit:
            audit.write("diagnostics_error", {"reason": "import_failed", "error": repr(e)})
        return 2

    try:
        gate = RegimeGate()
    except Exception as e:
        print("[ERROR] RegimeGate() constructor failed:", repr(e))
        if audit:
            audit.write("diagnostics_error", {"reason": "ctor_failed", "error": repr(e)})
        return 3

    print("=" * 70)
    print("REA — RegimeGate Diagnostics")
    print("UTC Now:", utc_now_iso())
    print("CWD:", os.getcwd())
    print("Python:", sys.version.split()[0])
    print("=" * 70)

    # Try to expose gate state/attributes
    attrs = {}
    for k in ("state", "mode", "status", "last", "last_result", "debug", "reason", "block_reason"):
        if hasattr(gate, k):
            try:
                attrs[k] = getattr(gate, k)
            except Exception:
                pass

    if attrs:
        print("\n[Gate Attributes]")
        for k, v in attrs.items():
            print(f"- {k}: {v}")

    methods = ("allow", "allows", "evaluate", "check", "on_bar")

    results: Dict[str, Any] = {}
    inferred_allow: Optional[bool] = None

    for m in methods:
        if not hasattr(gate, m):
            continue
        fn = getattr(gate, m)
        try:
            r = fn()  # call with no args (your gate currently supports that)
            results[m] = r

            # Infer allow if possible
            if isinstance(r, bool):
                inferred_allow = r
            elif isinstance(r, dict) and "allow" in r:
                inferred_allow = bool(r.get("allow"))

        except TypeError as te:
            results[m] = {"error": f"TypeError calling {m}(): {te}"}
        except Exception as e:
            results[m] = {"error": f"Exception calling {m}(): {repr(e)}"}

    print("\n[Method Results]")
    for m, r in results.items():
        print(f"\n- {m}() -> {safe_json(r)}")

    # Final inference
    print("\n[Inference]")
    if inferred_allow is None:
        print("Could not infer allow/deny from gate return values.")
    else:
        print("ALLOW =", inferred_allow)

    if audit:
        audit.write(
            "diagnostics_result",
            {
                "tool": "diagnose_regime_gate",
                "inferred_allow": inferred_allow,
                "results": results,
            },
        )

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())