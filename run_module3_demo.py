from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from engine_loop import EngineLoop, EngineConfig
from replay_csv import CSVReplayConfig, replay


# ==================================================
# MODULE 3 — PROMPT-ONLY DEMO (SAFE)
# ==================================================
@dataclass
class DemoConfig:
    csv_path: str = "sample_spy_1m_long.csv"
    max_rows: int | None = None
    print_every: int = 25   # set to 0 for silent runs


def main() -> None:
    cfg = DemoConfig()

    print("Module 3 Demo (PROMPT-ONLY)")
    print(f"CSV: {cfg.csv_path}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("NOTE: No trades. No execution. Engine logic unchanged.")
    print("-" * 60)

    replay_cfg = CSVReplayConfig(
        csv_path=cfg.csv_path,
        max_rows=cfg.max_rows,
        print_every=cfg.print_every,
    )

    engine = EngineLoop(
        EngineConfig(
            symbol="SPY")
    )

    results = replay(replay_cfg, engine)

    print("-" * 60)
    print("[DONE] Replay complete")
    print(f"bars_1m={results.get('bars_1m')}")
    print(f"last_snap_type={type(results.get('last_snap')).__name__}")


if __name__ == "__main__":
    main()