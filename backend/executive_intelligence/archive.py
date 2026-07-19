"""Immutable dated archive for ExecutiveMorningBrief (Phase 173B/174)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import (
    ARCHIVE_SCHEMA_VERSION,
    BRIEF_SCHEMA_VERSION,
    DEFAULT_ARCHIVE_RELATIVE,
    SAFETY_LOCKS,
)
from backend.executive_intelligence.markdown import render_markdown
from backend.executive_intelligence.sanitizer import sanitize_payload
from backend.executive_intelligence.utils import utc_now_iso


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_RE = re.compile(r"^v(\d{3})$")


class MorningBriefArchiveStore:
    """Filesystem archive with version dirs, manifest, and no silent overwrite."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = Path.cwd() / DEFAULT_ARCHIVE_RELATIVE
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        brief: Mapping[str, Any],
        validation: Mapping[str, Any],
        *,
        created_by: str = "executive_intelligence_engine",
        created_reason: str = "scheduled_cutover",
        readiness: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Persist DRAFT→FINAL or FAILED.

        FINAL only when validation.finalization_allowed is true.
        Never overwrites an existing version directory.
        """
        report_date = str(brief.get("report_date") or "")
        if not _DATE_RE.match(report_date):
            raise ValueError(f"invalid_report_date:{report_date}")

        year, month, _ = report_date.split("-")
        date_dir = self.root / year / month / report_date
        date_dir.mkdir(parents=True, exist_ok=True)

        version = self._next_version(date_dir)
        sanitized = sanitize_payload(dict(brief))
        sanitized["report_version"] = version
        sanitized["version"] = version
        if readiness:
            sanitized["readiness_orchestration"] = dict(readiness)
            sanitized["readiness_audit"] = readiness.get("audit_phrase")

        final_ok = bool(validation.get("finalization_allowed") or validation.get("pass"))
        if final_ok:
            sanitized["report_status"] = "FINAL"
            sanitized["is_current_for_date"] = True
            sanitized["validation"] = dict(validation)
            sanitized["validation_status"] = "PASS"
            # Hash excludes report_hash itself
            sanitized["report_hash"] = None
            report_hash = self._hash_brief(sanitized)
            sanitized["report_hash"] = report_hash
            target = date_dir / version
            self._write_version_dir(
                target,
                sanitized,
                validation,
                created_by=created_by,
                created_reason=created_reason,
                readiness=readiness,
            )
            self._mark_prior_superseded(date_dir, version)
            self._atomic_write_json(
                date_dir / "current.json",
                {
                    "report_date": report_date,
                    "version": version,
                    "report_status": "FINAL",
                    "report_id": sanitized.get("report_id"),
                    "path": f"{year}/{month}/{report_date}/{version}/executive_morning_brief.json",
                    "state_hash": sanitized.get("state_hash"),
                    "report_hash": report_hash,
                    "generated_at_utc": sanitized.get("generated_at_utc"),
                    "readiness_audit": sanitized.get("readiness_audit"),
                    **SAFETY_LOCKS,
                },
            )
            self._update_root_pointers(sanitized, relative_path=f"{year}/{month}/{report_date}/{version}")
            self._rebuild_manifest()
            return {
                "status": "FINAL",
                "version": version,
                "path": str(target / "executive_morning_brief.json"),
                "report_id": sanitized.get("report_id"),
                "report_hash": report_hash,
                "brief": sanitized,
            }

        # FAILED path
        sanitized["report_status"] = "FAILED"
        sanitized["is_current_for_date"] = False
        sanitized["validation"] = dict(validation)
        sanitized["validation_status"] = "FAIL"
        sanitized["report_hash"] = self._hash_brief({**sanitized, "report_hash": None})
        failed_name = utc_now_iso().replace(":", "").replace("-", "") + "_FAILED"
        target = date_dir / "failed" / failed_name
        self._write_version_dir(
            target,
            sanitized,
            validation,
            created_by=created_by,
            created_reason=created_reason,
            readiness=readiness,
        )
        self._rebuild_manifest()
        return {
            "status": "FAILED",
            "version": version,
            "path": str(target / "executive_morning_brief.json"),
            "report_id": sanitized.get("report_id"),
            "report_hash": sanitized.get("report_hash"),
            "brief": sanitized,
            "blockers": list(validation.get("blockers") or []),
        }

    def _next_version(self, date_dir: Path) -> str:
        max_n = 0
        if date_dir.is_dir():
            for child in date_dir.iterdir():
                if child.is_dir() and _VERSION_RE.match(child.name):
                    max_n = max(max_n, int(child.name[1:]))
        return f"v{max_n + 1:03d}"

    def _write_version_dir(
        self,
        target: Path,
        brief: Mapping[str, Any],
        validation: Mapping[str, Any],
        *,
        created_by: str,
        created_reason: str,
        readiness: Mapping[str, Any] | None = None,
    ) -> None:
        if target.exists():
            raise RuntimeError(f"refusing_overwrite:{target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_parent = Path(tempfile.mkdtemp(prefix="emb_", dir=str(target.parent)))
        try:
            stage = tmp_parent / "stage"
            stage.mkdir(parents=True, exist_ok=True)
            md = render_markdown(brief)
            self._atomic_write_json(stage / "executive_morning_brief.json", brief)
            (stage / "executive_morning_brief.md").write_text(md, encoding="utf-8")
            self._atomic_write_json(stage / "validation.json", validation)
            pdf_meta: dict[str, Any] = {"status": "NOT_GENERATED"}
            try:
                from backend.executive_intelligence.print_report import pdf_sha256, render_printable_pdf

                if str(brief.get("report_status")).upper() == "FINAL":
                    pdf_bytes = render_printable_pdf(brief, printed_by="executive_intelligence_archive")
                    pdf_path = stage / "executive_morning_brief.pdf"
                    if pdf_path.exists():
                        raise RuntimeError("refusing_pdf_overwrite")
                    pdf_path.write_bytes(pdf_bytes)
                    pdf_meta = {
                        "status": "OK",
                        "sha256": pdf_sha256(pdf_bytes),
                        "bytes": len(pdf_bytes),
                        "file": "executive_morning_brief.pdf",
                    }
            except Exception as exc:
                if str(brief.get("report_status")).upper() == "FINAL":
                    pdf_meta = {
                        "status": "FAILED",
                        "reason": str(exc),
                        "file": None,
                    }
                    # Do not fail FINAL JSON/MD publish — printable is PARTIAL
            version_manifest = {
                "report_id": brief.get("report_id"),
                "report_date": brief.get("report_date"),
                "version": brief.get("report_version") or brief.get("version"),
                "report_status": brief.get("report_status"),
                "report_hash": brief.get("report_hash"),
                "schema_version": brief.get("schema_version") or BRIEF_SCHEMA_VERSION,
                "archive_version": brief.get("archive_version") or ARCHIVE_SCHEMA_VERSION,
                "created_by": created_by,
                "created_reason": created_reason,
                "created_at_utc": utc_now_iso(),
                "files": {
                    "json": "executive_morning_brief.json",
                    "markdown": "executive_morning_brief.md",
                    "validation": "validation.json",
                    "pdf": "executive_morning_brief.pdf" if pdf_meta.get("status") == "OK" else None,
                },
                "pdf": pdf_meta,
                "printable_status": "OK" if pdf_meta.get("status") == "OK" else ("PARTIAL" if str(brief.get("report_status")).upper() == "FINAL" else "N/A"),
                "readiness": dict(readiness) if readiness else brief.get("readiness_orchestration"),
                "readiness_audit": (readiness or {}).get("audit_phrase") or brief.get("readiness_audit"),
                **SAFETY_LOCKS,
            }
            self._atomic_write_json(stage / "manifest.json", version_manifest)
            if readiness:
                self._atomic_write_json(stage / "readiness.json", readiness)
            # Atomic directory publish: replace into place via rename of stage
            os.replace(str(stage), str(target))
        finally:
            # cleanup temp parent if empty leftovers
            try:
                if tmp_parent.exists():
                    for child in list(tmp_parent.iterdir()):
                        if child.is_dir():
                            continue
                        child.unlink(missing_ok=True)
                    tmp_parent.rmdir()
            except OSError:
                pass

    def _mark_prior_superseded(self, date_dir: Path, current_version: str) -> None:
        """Record supersession in index layer only (do not mutate FINAL brief JSON)."""
        status_path = date_dir / "supersession.json"
        prior = []
        if status_path.is_file():
            try:
                prior = json.loads(status_path.read_text(encoding="utf-8")).get("superseded_versions") or []
            except Exception:
                prior = []
        for child in date_dir.iterdir():
            if child.is_dir() and _VERSION_RE.match(child.name) and child.name != current_version:
                if child.name not in prior:
                    prior.append(child.name)
        self._atomic_write_json(
            status_path,
            {
                "current_version": current_version,
                "superseded_versions": sorted(prior),
                "updated_at_utc": utc_now_iso(),
                "note": "FINAL brief JSON bytes are immutable; supersession tracked here only.",
            },
        )

    def _update_root_pointers(self, brief: Mapping[str, Any], *, relative_path: str) -> None:
        latest = {
            "report_date": brief.get("report_date"),
            "version": brief.get("report_version") or brief.get("version"),
            "report_status": "FINAL",
            "report_id": brief.get("report_id"),
            "path": f"{relative_path}/executive_morning_brief.json",
            "state_hash": brief.get("state_hash"),
            "report_hash": brief.get("report_hash"),
            "generated_at_utc": brief.get("generated_at_utc"),
            **SAFETY_LOCKS,
        }
        self._atomic_write_json(self.root / "latest.json", latest)

    def _rebuild_manifest(self) -> None:
        available_dates: list[str] = []
        current_version_by_date: dict[str, str] = {}
        status_by_date: dict[str, str] = {}
        paths_by_date: dict[str, str] = {}
        failed_attempt_count = 0

        if self.root.is_dir():
            for year_dir in sorted(p for p in self.root.iterdir() if p.is_dir() and p.name.isdigit()):
                for month_dir in sorted(p for p in year_dir.iterdir() if p.is_dir() and p.name.isdigit()):
                    for date_dir in sorted(p for p in month_dir.iterdir() if p.is_dir() and _DATE_RE.match(p.name)):
                        date = date_dir.name
                        current = date_dir / "current.json"
                        if current.is_file():
                            try:
                                pointer = json.loads(current.read_text(encoding="utf-8"))
                            except Exception:
                                pointer = {}
                            available_dates.append(date)
                            current_version_by_date[date] = str(pointer.get("version") or "")
                            status_by_date[date] = str(pointer.get("report_status") or "FINAL")
                            paths_by_date[date] = str(pointer.get("path") or "")
                        failed_root = date_dir / "failed"
                        if failed_root.is_dir():
                            failed_attempt_count += sum(1 for _ in failed_root.iterdir() if _.is_dir())
                            if date not in available_dates:
                                available_dates.append(date)
                                status_by_date[date] = "FAILED"

        available_dates = sorted(set(available_dates))
        latest_report_date = None
        latest_path = self.root / "latest.json"
        if latest_path.is_file():
            try:
                latest_report_date = json.loads(latest_path.read_text(encoding="utf-8")).get("report_date")
            except Exception:
                latest_report_date = available_dates[-1] if available_dates else None
        elif available_dates:
            latest_report_date = available_dates[-1]

        manifest = {
            "archive_schema_version": "css.morning_brief_manifest.v1",
            "archive_version": ARCHIVE_SCHEMA_VERSION,
            "archive_last_updated_at": utc_now_iso(),
            "available_dates": available_dates,
            "latest_report_date": latest_report_date,
            "report_count": len([d for d, s in status_by_date.items() if s == "FINAL"]),
            "failed_attempt_count": failed_attempt_count,
            "missing_expected_dates": [],
            "current_version_by_date": current_version_by_date,
            "status_by_date": status_by_date,
            "paths_by_date": paths_by_date,
            "expected_calendar_policy": {"business_days": "Mon-Fri", "timezone": "operator_configured"},
            **SAFETY_LOCKS,
        }
        self._atomic_write_json(self.root / "manifest.json", manifest)

    @staticmethod
    def _hash_brief(brief: Mapping[str, Any]) -> str:
        payload = dict(brief)
        payload["report_hash"] = None
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, indent=2, sort_keys=True, default=str)
                handle.write("\n")
            os.replace(tmp_name, str(path))
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
