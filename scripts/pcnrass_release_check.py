from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "artifacts" / "pcnrass_release_summary.json"


CHECKS = (
    ("py_compile", [sys.executable, "-m", "py_compile", "dashboard/runtime/runtime_smoke_test.py", "dashboard/web/web_smoke_test.py", "dashboard/mobile/mobile_smoke_test.py", "dashboard/auth/css_sign_on_smoke_test.py"]),
    ("dashboard_engine_pytest", [sys.executable, "-m", "pytest", "tests/dashboard", "tests/engine", "-q"]),
    ("runtime_smoke", [sys.executable, "dashboard/runtime/runtime_smoke_test.py"]),
    ("web_smoke", [sys.executable, "dashboard/web/web_smoke_test.py"]),
    ("auth_smoke", [sys.executable, "dashboard/auth/css_sign_on_smoke_test.py"]),
    ("mobile_smoke", [sys.executable, "dashboard/mobile/mobile_smoke_test.py"]),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CSS PCNRASS release checks.")
    parser.add_argument("--list", action="store_true", help="List checks without running them.")
    parser.add_argument("--summary", default=str(SUMMARY_PATH), help="Write JSON summary to this path.")
    args = parser.parse_args(argv)

    if args.list:
        for name, command in CHECKS:
            print(f"{name}: {' '.join(command)}")
        return 0

    results = []
    ok = True
    for name, command in CHECKS:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        passed = result.returncode == 0
        ok = ok and passed
        results.append(
            {
                "name": name,
                "passed": passed,
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
            }
        )
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
        if not passed:
            break

    summary = {
        "payload_version": "css.pcnrass.release_check.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": ok,
        "results": results,
    }
    _write_summary(Path(args.summary), summary)
    return 0 if ok else 1


def _write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
