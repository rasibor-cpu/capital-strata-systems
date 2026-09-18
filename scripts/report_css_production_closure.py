from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.commercialization.production_closure_status import (
    assess_production_closure,
)
from backend.commercialization.production_evidence_handoff import (
    validate_production_evidence_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report CSS production closure status against the Sunday deadline."
    )
    parser.add_argument(
        "--evidence-package",
        type=Path,
        default=None,
        help="Optional production evidence JSON package.",
    )
    parser.add_argument(
        "--internal-engineering-complete",
        action="store_true",
        help="Assert the validated internal engineering baseline is complete.",
    )
    args = parser.parse_args()

    evidence = None
    if args.evidence_package is not None:
        payload = json.loads(args.evidence_package.read_text(encoding="utf-8"))
        evidence = validate_production_evidence_package(payload)

    status = assess_production_closure(
        internal_engineering_complete=args.internal_engineering_complete,
        evidence_validation=evidence,
    )

    print(
        json.dumps(
            {
                "target_deadline": status.target_deadline,
                "work_items_closed": status.work_items_closed,
                "production_authorized": status.production_authorized,
                "internal_engineering_complete": status.internal_engineering_complete,
                "external_evidence_valid_for_review": status.external_evidence_valid_for_review,
                "open_workstreams": list(status.open_workstreams),
                "blocker_reasons": list(status.blocker_reasons),
                "money_movement_authorized": status.money_movement_authorized,
                "trading_execution_authority": status.trading_execution_authority,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status.work_items_closed else 2


if __name__ == "__main__":
    raise SystemExit(main())
