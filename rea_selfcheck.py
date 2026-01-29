"""
REA Self-Check — End-to-End Sanity Validation

Purpose:
- Verify that ALL core modules created so far:
  * import correctly
  * agree on locked assumptions
  * behave consistently
- Catch missing files, broken imports, or silent mismatches
- Provide a clear PASS / FAIL report before wiring anything further

This file MUST pass cleanly before Feb 10.
"""

from __future__ import annotations

import sys
import traceback


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check(condition: bool, ok: str, fail: str) -> None:
    if condition:
        print(f"[OK]   {ok}")
    else:
        raise RuntimeError(f"[FAIL] {fail}")


def main() -> int:
    banner("REA SELF-CHECK — START")

    # -------------------------------------------------
    # 1) Python version sanity
    # -------------------------------------------------
    banner("1) Python Environment")
    check(
        sys.version_info.major == 3 and sys.version_info.minor >= 10,
        f"Python {sys.version_info.major}.{sys.version_info.minor} detected",
        "Python 3.10+ required",
    )

    # -------------------------------------------------
    # 2) Instrument Registry
    # -------------------------------------------------
    banner("2) Instrument Registry")

    try:
        import instrument_registry as ir
    except Exception:
        traceback.print_exc()
        raise RuntimeError("instrument_registry.py failed to import")

    instruments = ir.list_instruments()
    check(
        len(instruments) > 0,
        f"{len(instruments)} instruments registered",
        "No instruments registered",
    )

    for sym in instruments:
        spec = ir.get_instrument(sym)
        eps = ir.epsilon_price(sym)
        check(
            eps > 0,
            f"{sym}: epsilon price computed ({eps})",
            f"{sym}: epsilon computation failed",
        )

    check(
        ir.DEFAULT_TIMEFRAME == "M5",
        "Default timeframe locked to M5",
        "Default timeframe mismatch",
    )

    check(
        ir.DEFAULT_LOOKBACK_BARS == 20,
        "Lookback window locked to 20 bars",
        "Lookback window mismatch",
    )

    banner("Instrument Registry: PASS")

    # -------------------------------------------------
    # 3) Sanity Probe Logic (pure math)
    # -------------------------------------------------
    banner("3) Sanity Probe Logic")

    def sanity_signal(price: float, mean: float, epsilon: float) -> str:
        if abs(price - mean) < epsilon:
            return "NO_TRADE"
        return "BUY" if price < mean else "SELL"

    test_eps = ir.pip_to_price("EURUSD", 10.0)

    check(
        sanity_signal(1.0000, 1.0005, test_eps) == "NO_TRADE",
        "No-trade zone respected",
        "No-trade zone violated",
    )

    check(
        sanity_signal(0.9980, 1.0000, test_eps) == "BUY",
        "BUY signal below mean",
        "BUY logic failed",
    )

    check(
        sanity_signal(1.0025, 1.0000, test_eps) == "SELL",
        "SELL signal above mean",
        "SELL logic failed",
    )

    banner("Sanity Probe Logic: PASS")

    # -------------------------------------------------
    # 4) File layout expectations
    # -------------------------------------------------
    banner("4) File Layout")

    expected_files = [
        "instrument_registry.py",
        "rea_selfcheck.py",
    ]

    for fname in expected_files:
        try:
            open(fname, "r", encoding="utf-8").close()
            print(f"[OK]   {fname} present")
        except FileNotFoundError:
            raise RuntimeError(f"[FAIL] Missing required file: {fname}")

    banner("File Layout: PASS")

    # -------------------------------------------------
    # FINAL
    # -------------------------------------------------
    banner("REA SELF-CHECK — ALL SYSTEMS GREEN")
    print("You may safely continue to wiring and execution layers.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())