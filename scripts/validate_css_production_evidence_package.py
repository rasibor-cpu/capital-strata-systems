from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.commercialization.production_evidence_handoff import (
    validate_production_evidence_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a CSS production evidence package without importing "
            "or authorizing it."
        )
    )
    parser.add_argument("package", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.package.read_text(encoding="utf-8"))
    result = validate_production_evidence_package(payload)
    output = {
        "valid_for_review": result.valid_for_review,
        "missing_categories": list(result.missing_categories),
        "invalid_reasons": list(result.invalid_reasons),
        "package_id": result.package_id,
        "jurisdiction_code": result.jurisdiction_code,
        "agreement_id": result.agreement_id,
        "agreement_version": result.agreement_version,
        "production_authorized": result.production_authorized,
        "money_movement_authorized": result.money_movement_authorized,
        "trading_execution_authority": (
            result.trading_execution_authority
        ),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if result.valid_for_review else 2


if __name__ == "__main__":
    raise SystemExit(main())
