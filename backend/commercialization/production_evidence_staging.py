from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.commercialization.production_evidence_handoff import (
    validate_production_evidence_package,
)


@dataclass(frozen=True, slots=True)
class StagedEvidencePackage:
    package_path: str
    manifest_path: str
    sha256: str
    package_id: str


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def stage_validated_production_evidence(
    *,
    payload: Mapping[str, Any],
    output_dir: Path,
) -> StagedEvidencePackage:
    validation = validate_production_evidence_package(payload)
    if not validation.valid_for_review:
        raise ValueError(
            "production evidence package is not valid for review: "
            + "; ".join(
                [
                    *(
                        f"MISSING:{item}"
                        for item in validation.missing_categories
                    ),
                    *validation.invalid_reasons,
                ]
            )
        )

    package_id = validation.package_id or ""
    if not package_id:
        raise ValueError("validated package has no package_id")

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical = _canonical_bytes(payload)
    sha = hashlib.sha256(canonical).hexdigest()

    safe_id = "".join(
        ch if ch.isalnum() or ch in "-_." else "_"
        for ch in package_id
    )
    package_path = output_dir / f"{safe_id}.json"
    manifest_path = output_dir / f"{safe_id}.manifest.json"

    if package_path.exists() or manifest_path.exists():
        raise FileExistsError(
            "evidence package or manifest already exists; immutable staging "
            "does not overwrite prior evidence"
        )

    package_path.write_bytes(canonical)
    manifest = {
        "package_id": package_id,
        "package_sha256": sha,
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "jurisdiction_code": validation.jurisdiction_code,
        "agreement_id": validation.agreement_id,
        "agreement_version": validation.agreement_version,
        "valid_for_review": True,
        "production_authorized": False,
        "money_movement_authorized": False,
        "trading_execution_authority": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return StagedEvidencePackage(
        package_path=str(package_path),
        manifest_path=str(manifest_path),
        sha256=sha,
        package_id=package_id,
    )
