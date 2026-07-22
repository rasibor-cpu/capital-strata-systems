"""CLI entrypoint for Wave 3 Evidence Machine package assembly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.certification.evidence_machine import assemble_wave3_package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble Wave 3 evidence package")
    parser.add_argument(
        "--with-regression",
        action="store_true",
        help="Run bounded regression suite and attach REGRESSION_EVIDENCE",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory (default: runtime_reports/wave3_evidence_machine_<stamp>)",
    )
    parser.add_argument(
        "--endurance-sample-seconds",
        type=float,
        default=2.0,
        help="Wall-clock endurance sample duration in seconds",
    )
    args = parser.parse_args(argv)
    result = assemble_wave3_package(
        output_dir=args.output_dir,
        run_regression=bool(args.with_regression),
        endurance_sample_seconds=float(args.endurance_sample_seconds),
    )
    print(json.dumps({"summary_path": result.get("summary_path"), "package_dir": result.get("package_dir")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
