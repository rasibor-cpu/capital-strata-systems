"""
run_engine_loop.py
==================

Canonical local runner for engine_loop.py.

Reality check (your repo):
- engine_loop.py exports `main` (not `EngineLoop` class)

So this runner:
- loads .env (best-effort)
- imports engine_loop
- calls engine_loop.main() if present
- prints clean diagnostics if something is missing

Usage:
    python -u run_engine_loop.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def banner() -> None:
    print("=" * 70)
    print("REA Capital / CSS — Engine Loop Runner")
    print(f"Working directory: {Path.cwd()}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Virtualenv: {os.environ.get('VIRTUAL_ENV', 'None')}")
    print("=" * 70)


def load_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        print("[runner] .env not found.")
        return

    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(dotenv_path=str(env_path), override=False)
        print("[runner] .env loaded.")
    except Exception:
        print("[runner] python-dotenv not installed; skipping .env load.")


def main() -> int:
    banner()
    load_env()

    try:
        import engine_loop as el  # type: ignore
    except Exception:
        print("[runner] Failed to import engine_loop:")
        traceback.print_exc()
        return 1

    # Prefer canonical entrypoint: engine_loop.main()
    if hasattr(el, "main") and callable(getattr(el, "main")):
        try:
            rc = el.main()  # type: ignore[call-arg]
            # engine_loop.main may return None; treat None as success
            if rc is None:
                rc = 0
            print(f"[runner] engine_loop.main() finished with code: {rc}")
            return int(rc)
        except KeyboardInterrupt:
            print("\n[runner] Stopped by user.")
            return 0
        except Exception:
            print("[runner] engine_loop.main() raised an exception:")
            traceback.print_exc()
            return 2

    # Fallback: print exports so we can align naming quickly
    exports = [n for n in dir(el) if not n.startswith("_")]
    print("[runner] engine_loop has no callable main().")
    print("[runner] Public exports:", exports)
    print("[runner] ACTION: ensure engine_loop.py defines a `main()` function.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
