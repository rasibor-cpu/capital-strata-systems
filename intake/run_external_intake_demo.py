"""
run_external_intake_demo.py — quick test runner
Creates a demo Finelo intake event and writes it to JSONL.

Usage (from repo root: source/REA-capital-trading-engine):
  python intake/run_external_intake_demo.py
"""

from intake.external_intake import finelo_intake, write_signal_jsonl


def main() -> None:
    sig = finelo_intake(
        symbol="AAPL",
        timeframe="1d",
        setup_type="trend_pullback",
        bias="long",
        notes="Demo intake from phone-created module. Should write finelo.jsonl.",
        source_url="https://quiz.finelo.com/",
        raw_text="Trend pullback idea, wait for confirmation candle.",
    )
    out_path = write_signal_jsonl(sig)
    print("OK — wrote:", out_path)
    print("Signal:", sig.symbol, sig.asset_class, sig.timeframe, sig.setup_type, sig.bias)


if __name__ == "__main__":
    main()
