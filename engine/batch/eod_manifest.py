"""
Capital Strata Systems
EOD Manifest Generator – Phase 20

Purpose:
- Create immutable metadata index for each EOD batch run
- Record mode (REPORT_ONLY / SOFT_CLOSE / HARD_CLOSE)
- Record actor role
- Record timestamps
- List generated artifacts

Output:
audit/eod/YYYY-MM-DD/manifest.json
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


EOD_ROOT = Path("audit/eod")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_manifest(
    business_date: str,
    mode: str,
    actor_role: str,
    generated_files: List[str],
) -> Dict:

    return {
        "business_date": business_date,
        "mode": mode,
        "actor_role": actor_role,
        "generated_files": generated_files,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "version": "Phase_20_EOD",
    }


def save_manifest(
    business_date: str,
    mode: str,
    actor_role: str,
    generated_files: List[str],
) -> Path:

    target_dir = EOD_ROOT / business_date
    _ensure_dir(target_dir)

    manifest = build_manifest(
        business_date=business_date,
        mode=mode,
        actor_role=actor_role,
        generated_files=generated_files,
    )

    output_file = target_dir / "manifest.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return output_file