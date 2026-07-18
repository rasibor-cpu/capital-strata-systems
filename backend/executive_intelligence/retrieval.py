"""Historical retrieval for morning briefings archive."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import DEFAULT_ARCHIVE_RELATIVE, SAFETY_LOCKS


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MorningBriefRetrieval:
    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = Path.cwd() / DEFAULT_ARCHIVE_RELATIVE
        self.root = Path(root)

    def manifest(self) -> dict[str, Any]:
        path = self.root / "manifest.json"
        if not path.is_file():
            return {
                "archive_schema_version": "css.morning_brief_manifest.v1",
                "available_dates": [],
                "latest_report_date": None,
                "report_count": 0,
                "missing_expected_dates": [],
                "current_version_by_date": {},
                **SAFETY_LOCKS,
            }
        return json.loads(path.read_text(encoding="utf-8"))

    def latest(self) -> dict[str, Any] | None:
        pointer = self.root / "latest.json"
        if not pointer.is_file():
            return None
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        rel = meta.get("path")
        if not rel:
            return None
        path = self.root / rel
        if not path.is_file():
            return None
        brief = json.loads(path.read_text(encoding="utf-8"))
        brief["_archive_pointer"] = meta
        return brief

    def by_date(self, report_date: str, *, version: str | None = None) -> dict[str, Any] | None:
        if not _DATE_RE.match(report_date):
            raise ValueError("invalid_report_date")
        year, month, _ = report_date.split("-")
        date_dir = self.root / year / month / report_date
        if version:
            path = date_dir / version / "executive_morning_brief.json"
        else:
            current = date_dir / "current.json"
            if not current.is_file():
                return None
            meta = json.loads(current.read_text(encoding="utf-8"))
            ver = meta.get("version")
            path = date_dir / str(ver) / "executive_morning_brief.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def versions(self, report_date: str) -> list[dict[str, Any]]:
        if not _DATE_RE.match(report_date):
            raise ValueError("invalid_report_date")
        year, month, _ = report_date.split("-")
        date_dir = self.root / year / month / report_date
        if not date_dir.is_dir():
            return []
        rows = []
        current_version = None
        current = date_dir / "current.json"
        if current.is_file():
            current_version = json.loads(current.read_text(encoding="utf-8")).get("version")
        for child in sorted(date_dir.iterdir()):
            if not child.is_dir() or not re.match(r"^v\d{3}$", child.name):
                continue
            man = child / "manifest.json"
            meta = json.loads(man.read_text(encoding="utf-8")) if man.is_file() else {"version": child.name}
            meta["is_current"] = child.name == current_version
            rows.append(meta)
        return rows

    def list_summaries(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        include_failed: bool = False,
    ) -> list[dict[str, Any]]:
        man = self.manifest()
        dates = list(man.get("available_dates") or [])
        if date_from:
            dates = [d for d in dates if d >= date_from]
        if date_to:
            dates = [d for d in dates if d <= date_to]
        out = []
        status_by_date = man.get("status_by_date") or {}
        versions = man.get("current_version_by_date") or {}
        for date in dates:
            status = status_by_date.get(date, "FINAL")
            if status == "FAILED" and not include_failed:
                # Still list if only failed? skip unless include_failed
                if date not in versions:
                    continue
            brief = self.by_date(date) if date in versions else None
            out.append(
                {
                    "report_date": date,
                    "version": versions.get(date),
                    "report_status": status if not brief else brief.get("report_status", status),
                    "overall_status": None if not brief else brief.get("overall_status"),
                    "data_freshness_status": None if not brief else brief.get("data_freshness_status"),
                    "report_id": None if not brief else brief.get("report_id"),
                    **SAFETY_LOCKS,
                }
            )
        return out

    def previous(self, report_date: str) -> dict[str, Any] | None:
        dates = [d for d in (self.manifest().get("available_dates") or []) if d < report_date]
        # prefer dates with current FINAL
        versions = self.manifest().get("current_version_by_date") or {}
        dates = [d for d in dates if d in versions]
        if not dates:
            return None
        return self.by_date(dates[-1])

    def next(self, report_date: str) -> dict[str, Any] | None:
        dates = [d for d in (self.manifest().get("available_dates") or []) if d > report_date]
        versions = self.manifest().get("current_version_by_date") or {}
        dates = [d for d in dates if d in versions]
        if not dates:
            return None
        return self.by_date(dates[0])

    def compare_stub(self, date_from: str, date_to: str) -> dict[str, Any]:
        """Phase 174 stub — full compare engine is Phase 176."""
        left = self.by_date(date_from)
        right = self.by_date(date_to)
        return {
            "stub": True,
            "phase": "174",
            "message": "Full comparison engine scheduled for Phase 176",
            "from": date_from,
            "to": date_to,
            "from_present": left is not None,
            "to_present": right is not None,
            "from_overall_status": None if left is None else left.get("overall_status"),
            "to_overall_status": None if right is None else right.get("overall_status"),
            "from_report_id": None if left is None else left.get("report_id"),
            "to_report_id": None if right is None else right.get("report_id"),
            **SAFETY_LOCKS,
        }

    def previous_business_day(self, report_date: str) -> str | None:
        if not _DATE_RE.match(report_date):
            return None
        dt = datetime.strptime(report_date, "%Y-%m-%d")
        for _ in range(7):
            dt = dt - timedelta(days=1)
            if dt.weekday() < 5:
                candidate = dt.strftime("%Y-%m-%d")
                if candidate in (self.manifest().get("current_version_by_date") or {}):
                    return candidate
                # still return calendar previous business day even if missing
                return candidate
        return None
