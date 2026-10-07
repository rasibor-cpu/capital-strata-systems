"""CLI: CSS-064 governed endurance-run preflight and final manifest (real Windows host).

Usage (see docs/governance/CSS064_ENDURANCE_RUN_PACKAGE.md):
  python scripts/css064_endurance_package.py preflight --package-dir DIR --expected-sha SHA --operator-id ID
  python scripts/css064_endurance_package.py finalize  --package-dir DIR

Read-only toward the runtime: it only issues GET requests to the local
runtime endpoints and never changes execution or broker flags.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.certification.css064_endurance_package import (  # noqa: E402
    MANIFEST_FILE, MIN_TARGET_HOURS, PREFLIGHT_FILE, build_final_manifest, build_preflight,
)

FLAG_ENDPOINTS = ("/api/runtime-mode", "/api/v1/live-execution-authority", "/health")


def fetch_flag_payloads(base_url: str) -> dict:
    payloads = {}
    for path in FLAG_ENDPOINTS:
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=8) as response:
                payloads[path] = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # unreachable endpoint contributes no flags -> fails closed
            payloads[path] = {"_unreachable": type(exc).__name__}
    return payloads


def _write_new(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:  # never overwrite evidence
        json.dump(payload, handle, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSS-064 endurance package")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-dir", required=True)
    pre.add_argument("--expected-sha", required=True)
    pre.add_argument("--operator-id", required=True)
    pre.add_argument("--target-hours", type=float, default=MIN_TARGET_HOURS)
    pre.add_argument("--base-url", default="http://127.0.0.1:8765")
    fin = sub.add_parser("finalize")
    fin.add_argument("--package-dir", required=True)
    fin.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args(argv)

    package_dir = Path(args.package_dir)
    payloads = fetch_flag_payloads(args.base_url)
    if args.command == "preflight":
        result = build_preflight(repo_root=REPO_ROOT, expected_sha=args.expected_sha,
                                 operator_id=args.operator_id, target_hours=args.target_hours,
                                 flag_payloads=payloads)
        _write_new(package_dir / PREFLIGHT_FILE, result)
        print(json.dumps({"certifying": result["certifying"], "checks": result["checks"],
                          "flag_failures": result["safety_flags"]["failures"]}, indent=2))
        return 0 if result["certifying"] else 2
    manifest = build_final_manifest(package_dir=package_dir, repo_root=REPO_ROOT, flag_payloads=payloads)
    _write_new(package_dir / MANIFEST_FILE, manifest)
    print(json.dumps({"disposition": manifest["disposition"], "blockers": manifest["blockers"],
                      "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
    return 0 if not manifest["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
