"""
Capital Strata Systems
EOD Archive Utilities – Phase 20

Purpose:
- Centralize EOD output paths
- Provide safe write helpers for text/JSON outputs
- Ensure deterministic audit directory structure:
    audit/eod/YYYY-MM-DD/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


EOD_ROOT = Path("audit/eod")


def eod_dir(business_date: str) -> Path:
    d = EOD_ROOT / str(business_date)
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_text(business_date: str, filename: str, content: str) -> Path:
    out = eod_dir(business_date) / filename
    out.write_text(content, encoding="utf-8")
    return out


def write_json(business_date: str, filename: str, payload: Dict[str, Any]) -> Path:
    out = eod_dir(business_date) / filename
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out


def safe_relpath(path: Path) -> str:
    """
    Return a portable relative path string for manifest storage.
    """
    try:
        return str(path.as_posix())
    except Exception:
        return str(path)