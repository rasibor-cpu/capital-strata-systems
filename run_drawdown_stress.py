"""
run_drawdown_stress.py
======================

Root-level launcher for the drawdown stress test.

Why this exists:
- Running engine\\testing\\run_drawdown_stress.py directly can break imports
  (ModuleNotFoundError: No module named 'engine') due to Python path rules.
- This wrapper forces repo root onto sys.path, then runs the test module.

Usage (from repo root):
    python -u run_drawdown_stress.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def main() -> int:
    _ensure_repo_root_on_path()

    try:
        # Prefer a main() if your test module exposes it.
        from engine.testing import run_drawdown_stress as mod  # type: ignore
    except Exception:
        print("FATAL | could not import engine.testing.run_drawdown_stress")
        traceback.print_exc()
        return 2

    # If module has main(), call it. Otherwise just import side-effects already ran.
    try:
        fn = getattr(mod, "main", None)
        if callable(fn):
            return int(fn())
        print("OK | imported engine.testing.run_drawdown_stress (no main() found).")
        return 0
    except Exception:
        print("FATAL | exception inside drawdown stress test")
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
