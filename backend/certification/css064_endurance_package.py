"""CSS-064 governed endurance-run package: preflight gate and final manifest.

Wraps (does not replace) the OV-002 wall-clock monitor
(``backend/certification/ov002_endurance_monitor.py``). It adds what CSS-064
requires and the monitor does not provide:

- a pre-run gate: exact expected SHA == HEAD, clean worktree, Windows host,
  named operator, interpreter executable SHA-256,
  and *explicitly observed* safety flags (a missing flag fails; nothing is
  assumed safe by default);
- a final manifest: SHA-256 of every evidence file, start/end timestamps,
  counters, invalidation markers, a final flag capture, and a disposition.

The disposition is never "CERTIFIED". The best possible outcome is
``CERTIFICATION_CANDIDATE_INDEPENDENT_REVIEW_REQUIRED``. This module performs
no broker action and never changes execution flags.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

REQUIRED_FLAGS: dict[str, bool] = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}
MIN_TARGET_HOURS = 72.0
PREFLIGHT_FILE = "CSS064_PREFLIGHT.json"
MANIFEST_FILE = "CSS064_FINAL_MANIFEST.json"
INVALIDATION_MARKERS = ("INVALIDATION.json", "INVALIDATION_UNCERTAIN.json", "INVALIDATION_BLOCKED.json")
DISPOSITION_CANDIDATE = "CERTIFICATION_CANDIDATE_INDEPENDENT_REVIEW_REQUIRED"
DISPOSITION_NOT_CERTIFIABLE = "NOT_CERTIFIABLE"
DISPOSITION_OBSERVATION = "OBSERVATION_ONLY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True).stdout
    try:
        return {"head": run("rev-parse", "HEAD").strip(),
                "dirty_paths": [l for l in run("status", "--porcelain").splitlines() if l.strip()]}
    except Exception as exc:  # fail closed: unknown state is not clean
        return {"head": None, "dirty_paths": [f"git_unavailable:{type(exc).__name__}"]}


def _find_flag(payload: Any, name: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key == name:
                found.append(value)
            found.extend(_find_flag(value, name))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_find_flag(item, name))
    return found


def observe_safety_flags(payloads: Mapping[str, Any]) -> dict[str, Any]:
    """Every required flag must be observed, as a real bool, with the safe value, everywhere it appears."""
    flags: dict[str, Any] = {}
    failures: list[str] = []
    for name, required in REQUIRED_FLAGS.items():
        values = [v for payload in payloads.values() for v in _find_flag(payload, name)]
        flags[name] = values
        if not values:
            failures.append(f"{name}:not_observed")
        elif any(type(v) is not bool or v is not required for v in values):
            failures.append(f"{name}:unsafe_or_non_boolean:{values!r}")
    return {"ok": not failures, "observed": flags, "failures": failures, "observed_at_utc": _now()}


def build_preflight(
    *,
    repo_root: Path,
    expected_sha: str,
    operator_id: str,
    target_hours: float,
    flag_payloads: Mapping[str, Any],
    platform_name: str | None = None,
    git: Callable[[Path], dict[str, Any]] = git_state,
) -> dict[str, Any]:
    state = git(repo_root)
    platform_name = platform_name or os.name
    flags = observe_safety_flags(flag_payloads)
    checks = {
        "head_matches_expected_sha": bool(expected_sha) and state.get("head") == expected_sha,
        "worktree_clean": not state.get("dirty_paths"),
        "windows_host": platform_name == "nt",
        "operator_identified": bool(str(operator_id).strip()),
        "target_hours_at_least_72": float(target_hours) >= MIN_TARGET_HOURS,
        "safety_flags_explicit_and_safe": flags["ok"],
    }
    return {
        "css_item": "CSS-064",
        "certifying": all(checks.values()),
        "checks": checks,
        "expected_sha": expected_sha,
        "git": state,
        "host": {"hostname": socket.gethostname(), "platform": platform_name,
                 "python": sys.version.split()[0], "python_executable": sys.executable,
                 "python_executable_sha256": sha256_file(Path(sys.executable))},
        "operator_id": operator_id,
        "target_hours": float(target_hours),
        "safety_flags": flags,
        "preflight_at_utc": _now(),
    }


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_final_manifest(
    *,
    package_dir: Path,
    repo_root: Path,
    flag_payloads: Mapping[str, Any],
    git: Callable[[Path], dict[str, Any]] = git_state,
) -> dict[str, Any]:
    package_dir = Path(package_dir)
    preflight = _read(package_dir / PREFLIGHT_FILE) or {}
    run_status = _read(package_dir / "RUN_STATUS.json") or {}
    run_meta = _read(package_dir / "RUN_META.json") or {}
    files = sorted(p for p in package_dir.rglob("*") if p.is_file() and p.name != MANIFEST_FILE)
    inventory = [{"path": p.relative_to(package_dir).as_posix(), "bytes": p.stat().st_size,
                  "sha256": sha256_file(p)} for p in files]
    final_flags = observe_safety_flags(flag_payloads)
    state = git(repo_root)
    markers = [m for m in INVALIDATION_MARKERS if (package_dir / m).exists()]
    blockers: list[str] = []
    if not preflight:
        blockers.append("preflight_missing")
    elif not preflight.get("certifying"):
        blockers.append("preflight_not_certifying")
    if state.get("head") != preflight.get("expected_sha"):
        blockers.append("head_changed_during_run")
    if markers:
        blockers.append("invalidation_markers:" + ",".join(markers))
    if str(run_status.get("status", "")).upper() != "COMPLETE":
        blockers.append(f"monitor_status:{run_status.get('status')}")
    if not final_flags["ok"]:
        blockers.append("final_safety_flags:" + ";".join(final_flags["failures"]))
    if not preflight:
        disposition = DISPOSITION_OBSERVATION
    else:
        disposition = DISPOSITION_NOT_CERTIFIABLE if blockers else DISPOSITION_CANDIDATE
    manifest = {
        "css_item": "CSS-064",
        "disposition": disposition,
        "blockers": blockers,
        "expected_sha": preflight.get("expected_sha"),
        "head_at_finalize": state.get("head"),
        "run_start_utc": run_meta.get("run_start_utc") or run_meta.get("start_utc"),
        "finalized_at_utc": _now(),
        "monitor_status": run_status,
        "operator_id": preflight.get("operator_id"),
        "supervisor_process_identity": _read(package_dir / "SUPERVISOR_PREFLIGHT.json"),
        "process_identity": _read(package_dir / "PROCESS_IDENTITY.json"),
        "final_safety_flags": final_flags,
        "files": inventory,
        "non_claims": ["not_certified_until_independent_review", "no_live_execution_authorized"],
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return manifest
