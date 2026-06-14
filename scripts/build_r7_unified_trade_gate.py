"""NON-CANONICAL RETIREMENT CANDIDATE.

ARP-011 quarantine marker: this build/insertion script contains a historical
CSSUnifiedTradeGate definition. The canonical backend authority is
backend/governance/css_unified_trade_gate.py, and the active dashboard-local
support gate lives in scripts/css_live_dashboard.py.
"""

from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R6_AUTH_HARDENED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R7_UNIFIED_GATE.py")

ANCHOR = "class AdaptiveConcurrencyEnvelopeController:"
INSERT = r'''
# === R7 PCNRASS UNIFIED TRADE GATE ===
class CSSUnifiedTradeGate:
    """
    Single pre-position authority for paper and broker-routed trade openings.
    This does not replace broker-specific live gates; it sits before any
    position registration so blocked trades do not enter MTM/PnL state.
    """

    def approve_trade(self, *, candidate: dict, session: dict, role_profile: dict) -> dict:
        symbol = str(candidate.get("symbol", "UNKNOWN"))
        asset_class = str(candidate.get("asset_class", "UNKNOWN")).upper()

        if not isinstance(session, dict) or not session.get("session_id"):
            return {"approved": False, "reason": "NO_VALID_SESSION"}

        if not session.get("session_status", {}).get("active", True):
            return {"approved": False, "reason": "SESSION_NOT_ACTIVE"}

        if is_session_locked():
            return {"approved": False, "reason": "SESSION_LOCKED_DEFENSIVE_MODE"}

        if asset_class not in {"CRYPTO", "FX", "FUTURES", "OPTIONS"}:
            return {"approved": False, "reason": f"UNSUPPORTED_ASSET_CLASS_{asset_class}"}

        broker_mode = str(candidate.get("broker_mode", "paper")).lower()
        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_LIVE_MODE"}
            if not role_profile.get("can_execute_live_trading", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_LIVE_EXECUTION"}
        else:
            if not role_profile.get("can_execute_paper_trading", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_PAPER_EXECUTION"}

        if ENGINE_MODE == "SAFE" and broker_mode == "live":
            return {"approved": False, "reason": "SAFE_MODE_BLOCKS_LIVE_EXECUTION"}

        return {"approved": True, "reason": "UNIFIED_GATE_APPROVED"}


css_unified_trade_gate = CSSUnifiedTradeGate()


def approve_trade_before_register(asset_class: str, symbol: str, sig: float, prob: float) -> tuple[bool, str]:
    decision = css_unified_trade_gate.approve_trade(
        candidate={
            "asset_class": asset_class,
            "symbol": symbol,
            "signal_score": sig,
            "prob_positive": prob,
            "selected_broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "engine_mode": ENGINE_MODE,
        },
        session=SESSION_USER_CTX,
        role_profile=SESSION_USER_CTX.get("role_profile", {}),
    )

    if not decision.get("approved", False):
        try:
            audit_ledger.record(
                "unified_trade_gate_reject",
                str(SESSION_USER_CTX.get("user_id")),
                {
                    "session_id": SESSION_USER_CTX.get("session_id"),
                    "asset_class": asset_class,
                    "symbol": symbol,
                    "reason": decision.get("reason"),
                    "selected_broker": SELECTED_BROKER,
                    "broker_mode": SELECTED_BROKER_MODE,
                    "engine_mode": ENGINE_MODE,
                },
            )
        except Exception:
            pass

        print(f"[UNIFIED GATE BLOCKED] {asset_class} {symbol} | {decision.get('reason')}")
        return False, str(decision.get("reason"))

    return True, str(decision.get("reason"))
'''

TARGET = '''                    position = mtm_engine.register_position(
                        asset_class,
                        symbol,
                        sig,
                        prob,
                        allow_live_funding=allow_broker_test,
                    )
'''

REPLACEMENT = '''                    gate_ok, gate_reason = approve_trade_before_register(
                        asset_class=asset_class,
                        symbol=symbol,
                        sig=sig,
                        prob=prob,
                    )

                    if not gate_ok:
                        last_trade = f"{symbol} UNIFIED_GATE_BLOCKED {gate_reason}"
                        continue

                    position = mtm_engine.register_position(
                        asset_class,
                        symbol,
                        sig,
                        prob,
                        allow_live_funding=allow_broker_test,
                    )
'''


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    if "class CSSUnifiedTradeGate:" not in text:
        if ANCHOR not in text:
            raise RuntimeError("Anchor not found for inserting CSSUnifiedTradeGate")
        text = text.replace(ANCHOR, INSERT + "\n\n" + ANCHOR, 1)

    if TARGET not in text:
        raise RuntimeError("Target register_position block not found; no output written")

    text = text.replace(TARGET, REPLACEMENT, 1)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R7 UNIFIED TRADE GATE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
