"""
Report Exporter (v1)
--------------------
Exports report objects to JSON or CSV for:
- Audit review packs
- EOD batch printing workflows (future)
- External archival

This module exports:
- ReportPack
- EODSnapshot
- CountryAggregationResult (branch snapshots)

V1: file-based exports only.
Later: PDF rendering, printers, S3/Blob, encrypted archives.
"""

import csv
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional


def _to_dict(obj: Any) -> Any:
    """
    Best-effort conversion to dict for export.
    """
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    return obj


class ReportExporter:
    def export_json(self, *, obj: Any, path: str) -> None:
        payload = _to_dict(obj)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def export_csv(
        self,
        *,
        rows: List[Dict[str, Any]],
        path: str,
        fieldnames: Optional[List[str]] = None,
    ) -> None:
        if not rows:
            # write an empty file with no headers
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("")
            return

        if fieldnames is None:
            # union of keys across rows (stable order by first row)
            keys = list(rows[0].keys())
            for r in rows[1:]:
                for k in r.keys():
                    if k not in keys:
                        keys.append(k)
            fieldnames = keys

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k) for k in fieldnames})