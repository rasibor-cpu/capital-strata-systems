"""CLI: Final Close-Out Batch 2 certification evidence package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.certification.batch2_certification_assessment import assemble_batch2_package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble Batch 2 Production Certification evidence (no fabrication)"
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--skip-regression",
        action="store_true",
        help="Skip bounded regression capture inside the package",
    )
    parser.add_argument(
        "--endurance-sample-seconds",
        type=float,
        default=2.0,
        help="Short wall-clock sample only; does not claim 72h",
    )
    args = parser.parse_args(argv)
    result = assemble_batch2_package(
        output_dir=args.output_dir,
        run_regression=not bool(args.skip_regression),
        endurance_sample_seconds=float(args.endurance_sample_seconds),
    )
    print(
        json.dumps(
            {
                "summary_path": result.get("summary_path"),
                "package_dir": result.get("package_dir"),
                "executive_certification_decision": result.get(
                    "executive_certification_decision"
                ),
                "phase181_engine_status": (result.get("phase181_evaluation") or {}).get(
                    "status"
                ),
                "certification_claimed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
