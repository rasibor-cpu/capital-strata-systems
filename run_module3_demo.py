from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from engine_loop import REACapitalEngineLoop, EngineConfig
from replay_csv import CSVReplayConfig, replay


@dataclass
class DemoConfig:
    """
    Module 3 Demo Runner (Prompt-only).
    Uses CSV replay to validate:
      - data controller
      - regime gate
      - signal construction (VWAP + vol normalization)
      - approval queue
    """
    csv_path: str = "sample_spy_1m.csv"
    max_rows: Optional[int] = None
    print_every: int = 5
    print_prompts: bool = True
    print_regime: bool = True


def main() -> None:
    cfg = DemoConfig()

    # Engine is broker-free and prompt-only.
    engine = REACapitalEngineLoop(EngineConfig(symbol="SPY"))

    # Replay runner expects CSV headers: ts_utc,o,h,l,c,v
    replay_cfg = CSVReplayConfig(
        csv_path=cfg.csv_path,
        max_rows=cfg.max_rows,
        print_every=cfg.print_every,
        print_prompts=cfg.print_prompts,
        print_regime=cfg.print_regime,
    )

    print("=== REA Capital – Trading Engine ===")
    print("Module 3 Demo (Prompt-only)")
    print(f"CSV: {cfg.csv_path}")
    print(f"Started: {datetime.utcnow().isoformat()}Z")
    print("NOTE: Sample CSV is small; signals may be blocked due to minimum-history rules.\n")

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
