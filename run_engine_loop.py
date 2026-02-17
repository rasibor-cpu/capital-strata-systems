"""
run_engine_loop.py
==================

Canonical local runner for EngineLoop.

This file safely drives EngineLoop.step() in a bounded loop
so we can validate boot, environment loading, and provider wiring.

Usage:
    python -u run_engine_loop.py
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


def banner() -> None:
    print("=" * 70)
    print("REA Capital / CSS — EngineLoop Runner")
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
        from engine_loop import EngineLoop  # type: ignore
    except Exception:
        print("[runner] Failed to import EngineLoop:")
        traceback.print_exc()
        return 1

    try:
        loop = EngineLoop()
    except Exception:
        print("[runner] Failed to initialize EngineLoop:")
        traceback.print_exc()
        return 2

    max_steps = int(os.environ.get("ENGINE_MAX_STEPS", "50"))
    sleep_time = float(os.environ.get("ENGINE_STEP_SLEEP", "0.25"))

    print(f"[runner] Starting loop for {max_steps} steps...")
    print("-" * 70)

    for i in range(1, max_steps + 1):
        try:
            result = loop.step()
            print(f"[runner] Step {i}/{max_steps} OK -> {result}")
        except KeyboardInterrupt:
            print("\n[runner] Stopped by user.")
            return 0
        except Exception:
            print(f"[runner] Step {i} FAILED:")
            traceback.print_exc()
            return 3

        time.sleep(sleep_time)

    print("-" * 70)
    print("[runner] Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
