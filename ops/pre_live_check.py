"""
ops/pre_live_check.py

REA Capital Trading Engine — Pre-Live Checklist
Outputs a deterministic GREEN/AMBER/RED readiness summary.

Run:
  python ops/pre_live_check.py

Optional env:
  REA_ENGINE_ENTRYPOINT="engine.run_engine:main"
  REA_ASSET_CLASS="fx" | "crypto" | ...
  REA_KILL_SWITCH=1
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

# Observability modules (must be present)
from backend.app.observability.logger import init_logging, get_logger, with_trace
from backend.app.observability.kill_switch import check_kill_switch
from backend.app.observability.session_time import assert_session_allowed
from backend.app.observability.config_drift import DEFAULT_CONFIG_GUARD


log = get_logger("ops.pre_live_check")


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: str   # GREEN | AMBER | RED
    detail: str


def _ok(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "GREEN", detail)


def _amber(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "AMBER", detail)


def _red(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "RED", detail)


def _print_results(results: List[CheckResult]) -> None:
    # Plain stdout (works even if logging is disabled)
    print("\n=== PRE-LIVE CHECK RESULTS ===")
    for r in results:
        print(f"{r.state:5} | {r.name:22} | {r.detail}")
    print("==============================\n")


def _final_state(results: List[CheckResult]) -> str:
    if any(r.state == "RED" for r in results):
        return "RED"
    if any(r.state == "AMBER" for r in results):
        return "AMBER"
    return "GREEN"


def check_python() -> CheckResult:
    v = sys.version.split()[0]
    major = sys.version_info.major
    minor = sys.version_info.minor
    if major < 3 or (major == 3 and minor < 10):
        return _red("python_version", f"{v} (need >= 3.10)")
    return _ok("python_version", v)


def check_repo_layout() -> CheckResult:
    must = [
        Path("run_live_guarded.py"),
        Path("engine/run_engine.py"),
        Path("backend/app/observability/logger.py"),
        Path("backend/app/observability/kill_switch.py"),
        Path("backend/app/observability/session_time.py"),
    ]
    missing = [str(p) for p in must if not p.exists()]
    if missing:
        return _red("repo_layout", f"missing: {', '.join(missing)}")
    return _ok("repo_layout", "ok")


def check_runtime_controls() -> CheckResult:
    rt = Path("runtime")
    if not rt.exists():
        return _amber("runtime_dir", "missing (ok; will be created on demand)")
    return _ok("runtime_dir", "present")


def check_kill() -> CheckResult:
    d = check_kill_switch(pair="GLOBAL")
    if d.killed:
        return _red("kill_switch", f"ACTIVE | scope={d.scope} | reason={d.reason}")
    return _ok("kill_switch", "not active")


def check_session() -> CheckResult:
    asset_class = os.getenv("REA_ASSET_CLASS", "fx")
    decision = assert_session_allowed(asset_class=asset_class, hard_fail=False)
    if decision.allowed:
        return _ok("session_gate", f"ALLOW | {asset_class} | {decision.reason}")
    # Session blocked can be expected (e.g., weekend). That’s AMBER, not RED.
    return _amber("session_gate", f"BLOCK | {asset_class} | {decision.reason} ({decision.state})")


def check_config_hash() -> CheckResult:
    fp = DEFAULT_CONFIG_GUARD.fingerprint()
    return _ok("config_hash", fp.hash)


def check_entrypoint_import() -> CheckResult:
    spec = os.getenv("REA_ENGINE_ENTRYPOINT", "engine.run_engine:main").strip()
    if ":" not in spec:
        return _red("entrypoint", f"invalid format: {spec}")

    mod_path, func_name = spec.split(":", 1)
    mod_path = mod_path.strip()
    func_name = func_name.strip()

    try:
        __import__(mod_path)
        mod = sys.modules[mod_path]
    except Exception as e:
        return _red("entrypoint", f"import failed: {mod_path} | {e}")

    fn = getattr(mod, func_name, None)
    if fn is None or not callable(fn):
        return _red("entrypoint", f"callable not found: {spec}")

    return _ok("entrypoint", f"ok: {spec}")


def main() -> int:
    # Minimal logging initialization
    init_logging(os.getenv("LOG_LEVEL", "INFO"))
    adapter = with_trace(log, "CHECK")

    adapter.info("PRE_LIVE_CHECK_START")

    results: List[CheckResult] = []
    results.append(check_python())
    results.append(check_repo_layout())
    results.append(check_runtime_controls())
    results.append(check_kill())
    results.append(check_session())
    results.append(check_config_hash())
    results.append(check_entrypoint_import())

    _print_results(results)

    final = _final_state(results)
    print(f"FINAL_STATE: {final}")

    adapter.info("PRE_LIVE_CHECK_DONE | final=%s", final)
    return 0 if final != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
