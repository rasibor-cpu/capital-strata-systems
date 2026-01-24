from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from engine_loop import REACapitalEngineLoop, EngineConfig
from replay_csv import CSVReplayConfig, replay


@dataclass
class DemoConfig:
    # Use the long CSV so the regime gate can pass the minimum 5m history check
    csv_path: str = "sample_spy_1m_long.csv"

    # Leave None to run the full file
    max_rows: int | None = None

    # Print progress every N 1m bars
    print_every: int = 25

    # Replay will simulate on-time arrivals (see replay_csv.py)
    arrival_delay_seconds: int = 20


def main() -> None:
    cfg = DemoConfig()

    engine = REACapitalEngineLoop(EngineConfig(symbol="SPY"))

    replay_cfg = CSVReplayConfig(
        csv_path=cfg.csv_path,
        max_rows=cfg.max_rows,
        print_every=cfg.print_every,
        print_prompts=True,
        print_regime=True,
        arrival_delay_seconds=cfg.arrival_delay_seconds,
    )

    print("=== REA Capital – Trading Engine ===")
    print("Module 3 Demo (Prompt-only)")
    print(f"CSV: {cfg.csv_path}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}Z")
    print("NOTE: This run is PROMPT-ONLY. No trades are executed.\n")

    results = replay(replay_cfg, engine)

    print("\n=== MODULE 3 DEMO SUMMARY ===")
    for k, v in results.items():
        print(f"{k}: {v}")

    pending = engine.queue.list_pending()
    print(f"\nPending approvals in queue: {len(pending)}")
    for i, item in enumerate(engine.queue.top_n(5)):
        print(f"\n--- TOP {i+1} ---")
        print(item.prompt.summary())


if __name__ == "__main__":
    main()
