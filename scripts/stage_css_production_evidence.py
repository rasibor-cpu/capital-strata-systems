from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.commercialization.production_evidence_staging import (
    stage_validated_production_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and immutably stage CSS production evidence for human "
            "review. This does not import approvals or authorize production."
        )
    )
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/production/staged"),
    )
    args = parser.parse_args()

    payload = json.loads(args.package.read_text(encoding="utf-8"))
    staged = stage_validated_production_evidence(
        payload=payload,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "package_id": staged.package_id,
                "package_path": staged.package_path,
                "manifest_path": staged.manifest_path,
                "sha256": staged.sha256,
                "production_authorized": False,
                "money_movement_authorized": False,
                "trading_execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
