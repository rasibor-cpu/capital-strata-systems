# utils/diagnostics.py
# Read-only diagnostic logger for REA Capital Trading Engine
# This module MUST NOT affect trading logic or execution

from datetime import datetime


def log_engine_diagnostics(
    *,
    timestamp=None,
    bars_5m=0,
    min_bars_required=40,
    session_name="UNKNOWN",
    session_open=False,
    regime_state="BLOCK",
    vwap_deviation=None,
    vwap_threshold=None,
    reason="",
):
    """
    Read-only diagnostic logger.
    This function prints WHY the engine is silent or active.
    It does NOT generate signals or trades.
    """

    ts = timestamp or datetime.utcnow().isoformat(timespec="seconds")

    print("\n" + "=" * 60)
    print("REA CAPITAL — ENGINE DIAGNOSTICS")
    print("=" * 60)
    print(f"Timestamp (UTC): {ts}")

    print("\n[DATA READINESS]")
    print(f"5m Bars: {bars_5m} / {min_bars_required}")
    print("Status:", "READY" if bars_5m >= min_bars_required else "NOT READY")

    print("\n[SESSION]")
    print(f"Session Name: {session_name}")
    print(f"Session Open: {session_open}")

    print("\n[REGIME GATE]")
    print(f"Regime State: {regime_state}")

    print("\n[VWAP]")
    if vwap_deviation is None:
        print("VWAP Deviation: N/A")
    else:
        print(f"VWAP Deviation: {vwap_deviation:.4f}")

    if vwap_threshold is None:
        print("VWAP Threshold: N/A")
    else:
        print(f"VWAP Threshold: {vwap_threshold:.4f}")

    print("\n[DECISION]")
    print(f"Outcome: NO SIGNAL")
    if reason:
        print(f"Reason: {reason}")
    else:
        print("Reason: Diagnostic only — no execution allowed")

    print("=" * 60 + "\n")
