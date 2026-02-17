"""
run_engine_loop.py
==================

Canonical local runner for the EngineLoop module.

Why this exists:
- engine_loop.py is primarily a library/module (EngineLoop exposes .step()).
- Running engine_loop.py directly may do nothing if it has no __main__ entrypoint.
- This runner drives EngineLoop.step() in a controlled loop and prints diagnostics.

Safety:
- Runs a bounded number of steps by default (safe boot validation).
- Use CTRL+C to stop any time.

Usage:
  python -u run_engine_loop.py
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


def _banner() -> None:
    print("=" * 72)
    print("REA Capital / CSS — EngineLoop Runner")
    print(f"cwd: {Path.cwd()}")
    print(f"python: {sys.version.split()[0]}")
    print(f"venv: {os.environ.get('VIRTUAL_ENV', '')}")
    print("=" * 72)


def _load_env_if_needed() -> None:
    """
    Best-effort load .env via python-dotenv if installed.
    If not installed, we assume the environment is already set.
    """
    env_path = Path(".env")
    if not env_path.exists():
        print("[runner] .env not found in repo root. (This may be OK if env is set elsewhere.)")
        return

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        print("[runner] python-dotenv not installed; skipping .env autoload.")
        return

    loaded = load_dotenv(dotenv_path=str(env_path), override=False)
    print(f"[runner] .env load attempted: loaded={loaded}")


def main() -> int:
    _banner()
    _load_env_if_needed()

    # Import AFTER env load so providers can read environment variables
    try:
        import engine_loop  # noqa: F401
        from engine_loop import EngineLoop  # type: ignore
    except Exception:
        print("[runner] failed to import engine_loop / EngineLoop:")
        traceback.print_exc()
        return 2

    # Construct loop
    try:
        loop = EngineLoop()  # type: ignore[call-arg]
    except Exception:
        print("[runner] failed to construct EngineLoop():")
        traceback.print_exc()
        return 3

    # Controlled loop (safe defaults)
    max_steps = int(os.environ.get("ENGINE_MAX_STEPS", "50"))
    sleep_seconds = float(os.environ.get("ENGINE_STEP_SLEEP", "0.25"))

    print(f"[runner] driving EngineLoop.step() | max_steps={max_steps} | sleep={sleep_seconds}s")
    print("[runner] press CTRL+C to stop.")
    print("-" * 72)

    for i in range(1, max_steps + 1):
        try:
            out = loop.step()
            print(f"[runner] step {i}/{max_steps} OK | out={out}")
        except KeyboardInterrupt:
            print("\n[runner] stopped by user (CTRL+C).")
            return 0
        except Exception:
            print(f"[runner] step {i} FAILED:")
            traceback.print_exc()
            return 4

        time.sleep(sleep_seconds)

    print("-" * 72)
    print("[runner] completed bounded run successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
