from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.runtime.live_environment_loader import load_css_runtime_environment
from backend.runtime.operational_compatibility_validator import validate_operational_compatibility


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 170 operational compatibility validation in read-only mode.",
    )
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument(
        "--supervisor-state-path",
        default="runtime/supervisor/css_runtime_supervisor_state.json",
    )
    parser.add_argument("--runtime-endpoint", default=os.getenv("CSS_MISSION_CONTROL_RUNTIME_ENDPOINT", ""))
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--output", default="artifacts/css_phase170_operational_compatibility_report.json")
    return parser.parse_args()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_css_runtime_environment(str(repo_root))

    args = _parse_args()
    report = validate_operational_compatibility(
        artifact_root=args.artifact_root,
        supervisor_state_path=args.supervisor_state_path,
        endpoint_url=args.runtime_endpoint or None,
        allow_mock=bool(args.allow_mock),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nPhase 170 report written to: {output_path}")

    return 0 if report.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
