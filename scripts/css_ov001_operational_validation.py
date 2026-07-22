"""CLI: OV-001 OAT completion + controlled broker read-only validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.certification.ov001_operational_validation import assemble_ov001_package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OV-001 Operational Validation package")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--skip-brokers",
        action="store_true",
        help="Skip Coinbase/OANDA live read-only probes (not for production OV-001)",
    )
    parser.add_argument("--shutdown-cycles", type=int, default=2)
    args = parser.parse_args(argv)
    result = assemble_ov001_package(
        output_dir=args.output_dir,
        run_broker_validation=not bool(args.skip_brokers),
        shutdown_cycles=int(args.shutdown_cycles),
    )
    print(
        json.dumps(
            {
                "decision": result.get("decision"),
                "package_dir": result.get("package_dir"),
                "summary_path": result.get("summary_path"),
                "oat_percentage": (result.get("summary") or {}).get("oat_percentage"),
                "oat_complete": (result.get("summary") or {}).get("oat_complete"),
                "execution_allowed": False,
                "endurance_started": False,
            },
            indent=2,
        )
    )
    return 0 if result.get("decision") == "OV-001 COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
