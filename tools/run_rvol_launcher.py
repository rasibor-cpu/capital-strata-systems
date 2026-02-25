from pathlib import Path
import tools.run_phase1_portfolio_replay_v5_convexity_trim_rvol as r

r.DATA_DIR = Path("data/history__devslice/2025-02-24__2025-03-24")
r.main()