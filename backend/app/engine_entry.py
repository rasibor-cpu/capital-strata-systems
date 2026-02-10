"""
engine_entry.py – Phase 2 (safe stub)

Purpose:
- Single entrypoint the guard can call
- DRY_RUN only (no execution)
- Prints deterministic banner + exits
"""

from __future__ import annotations
import os
import time
from typing import Dict, Any


def start_engine(*, mode: str, identity: Dict[str, Any], dry_run: bool = True) -> int:
    print("[ENGINE] Entry invoked.")
    print(f"[ENGINE] MODE={mode}")
    print(f"[ENGINE] DRY_RUN={dry_run}")
    print(f"[ENGINE] IDENTITY={identity}")
    print(f"[ENGINE] ENGINE_RUN_ID={os.getenv('ENGINE_RUN_ID','')}")
    # simulate init
    time.sleep(0.5)
    print("[ENGINE] Init OK. No trades executed (DRY_RUN).")
    return 0
