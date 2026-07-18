"""Cross-report archive store (immutable FINAL, FAILED separation)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.reports_center.constants import ARCHIVE_SCHEMA, DEFAULT_ARCHIVE_RELATIVE, SAFETY_LOCKS

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{3,128}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


class ReportArchiveStore:
    """Canonical path: artifacts/runtime_reports/reports/<family>/<type>/YYYY/MM/YYYY-MM-DD/vNNN/"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else Path.cwd() / DEFAULT_ARCHIVE_RELATIVE

    def publish(
        self,
        *,
        family: str,
        report_type: str,
        report_date: str,
        payload: dict[str, Any],
        validation: dict[str, Any] | None = None,
        markdown: str = "",
        html: str = "",
        csv_text: str = "",
        created_by: str = "reports_center",
        created_reason: str = "generate",
    ) -> dict[str, Any]:
        if not _DATE.match(report_date):
            raise ValueError("invalid_report_date")
        family = self._safe_segment(family)
        report_type = self._safe_segment(report_type)
        validation = validation or {}
        final_ok = bool(validation.get("finalization_allowed", True)) and str(
            payload.get("report_status") or validation.get("report_status") or "FINAL"
        ).upper() in {"FINAL", "DRAFT"}
        # Determine lifecycle
        status = str(payload.get("report_status") or ("FINAL" if final_ok else "FAILED")).upper()
        if status not in {"FINAL", "FAILED", "DRAFT", "SUPERSEDED"}:
            status = "FAILED" if not final_ok else "FINAL"
        payload = {**payload, "report_status": status, **SAFETY_LOCKS}

        day_dir = self.root / family / report_type / report_date[:4] / report_date[5:7] / report_date
        day_dir.mkdir(parents=True, exist_ok=True)
        version = self._next_version(day_dir)
        ver_name = f"v{version:03d}"
        if status == "FAILED":
            target = day_dir / "FAILED" / ver_name
        else:
            target = day_dir / ver_name
        if target.exists():
            raise RuntimeError("archive_version_collision")
        target.mkdir(parents=True, exist_ok=False)

        report_id = f"cssrpt_{family}_{report_type}_{report_date}_{ver_name}"
        body = {
            **payload,
            "report_id": report_id,
            "report_type": report_type,
            "report_family": family,
            "report_date": report_date,
            "report_version": ver_name,
            "version_number": version,
            "generated_at": payload.get("generated_at") or _utc_now(),
            "schema_version": payload.get("schema_version") or ARCHIVE_SCHEMA,
        }
        json_text = json.dumps(body, indent=2, sort_keys=True, default=str)
        report_hash = _sha256_text(json_text)
        body["report_hash"] = report_hash
        json_text = json.dumps(body, indent=2, sort_keys=True, default=str)

        (target / "report.json").write_text(json_text, encoding="utf-8")
        if markdown:
            (target / "report.md").write_text(markdown, encoding="utf-8")
        if html:
            (target / "report.html").write_text(html, encoding="utf-8")
        if csv_text:
            (target / "report.csv").write_text(csv_text, encoding="utf-8")
        validation_path = target / "validation.json"
        validation_path.write_text(json.dumps(validation or {}, indent=2, sort_keys=True), encoding="utf-8")
        provenance = {
            "created_by": created_by,
            "created_reason": created_reason,
            "created_at": _utc_now(),
            "report_id": report_id,
            "report_hash": report_hash,
        }
        (target / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
        manifest = {
            "schema_version": ARCHIVE_SCHEMA,
            "report_id": report_id,
            "report_type": report_type,
            "report_family": family,
            "report_date": report_date,
            "report_version": ver_name,
            "report_status": status,
            "report_hash": report_hash,
            "files": sorted(p.name for p in target.iterdir() if p.is_file()),
            "official_report": bool(body.get("official_report")),
            "advisory_only": True,
            **SAFETY_LOCKS,
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        # latest pointer for non-FAILED only; never overwrite FINAL content — pointer is metadata
        if status == "FINAL":
            latest = day_dir / "latest.json"
            latest.write_text(
                json.dumps(
                    {
                        "report_id": report_id,
                        "report_version": ver_name,
                        "report_hash": report_hash,
                        "path_ref": f"{family}/{report_type}/{report_date[:4]}/{report_date[5:7]}/{report_date}/{ver_name}",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        return {
            "report_id": report_id,
            "report_version": ver_name,
            "report_hash": report_hash,
            "report_status": status,
            "archive_ref": f"{family}/{report_type}/{report_date[:4]}/{report_date[5:7]}/{report_date}/{('FAILED/' + ver_name) if status == 'FAILED' else ver_name}",
            "path_ref": str(target.relative_to(self.root)).replace("\\", "/"),
        }

    def retrieve(self, report_id: str) -> dict[str, Any] | None:
        meta = self._locate(report_id)
        if meta is None:
            return None
        path = meta["dir"] / "report.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_archive_ref"] = meta["archive_ref"]
        return data

    def versions(self, family: str, report_type: str, report_date: str) -> list[dict[str, Any]]:
        day_dir = self.root / self._safe_segment(family) / self._safe_segment(report_type) / report_date[:4] / report_date[5:7] / report_date
        if not day_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for child in sorted(day_dir.iterdir()):
            if child.name == "FAILED":
                for failed in sorted(child.iterdir()):
                    man = failed / "manifest.json"
                    if man.is_file():
                        out.append(json.loads(man.read_text(encoding="utf-8")))
            elif child.name.startswith("v") and child.is_dir():
                man = child / "manifest.json"
                if man.is_file():
                    out.append(json.loads(man.read_text(encoding="utf-8")))
        return out

    def list_recent(self, *, limit: int = 25) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        manifests: list[tuple[float, dict[str, Any]]] = []
        for man in self.root.rglob("manifest.json"):
            try:
                data = json.loads(man.read_text(encoding="utf-8"))
                manifests.append((man.stat().st_mtime, data))
            except Exception:
                continue
        manifests.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in manifests[:limit]]

    def list_failed(self, *, limit: int = 25) -> list[dict[str, Any]]:
        return [m for m in self.list_recent(limit=limit * 3) if str(m.get("report_status")).upper() == "FAILED"][:limit]

    def verify_integrity(self, report_id: str) -> dict[str, Any]:
        meta = self._locate(report_id)
        if meta is None:
            return {"status": "NOT_FOUND", "report_id": report_id}
        path = meta["dir"] / "report.json"
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        stored = str(data.get("report_hash") or "")
        # Recompute excluding mutable verification of stored hash: hash the body without report_hash then compare
        clone = dict(data)
        expected = clone.pop("report_hash", None)
        recomputed = _sha256_text(json.dumps(clone, indent=2, sort_keys=True, default=str))
        # Also accept hash of file as written (includes report_hash) matching stored
        file_hash = _sha256_text(raw)
        ok = stored and (stored == recomputed or stored == file_hash or stored == expected)
        # Practical: re-serialize with hash and compare to stored content hash field
        body_for_hash = {k: v for k, v in data.items() if k != "report_hash"}
        alt = _sha256_text(json.dumps(body_for_hash, indent=2, sort_keys=True, default=str))
        ok = bool(stored) and stored in {alt, recomputed, file_hash}
        return {
            "status": "OK" if ok else "MISMATCH",
            "report_id": report_id,
            "stored_hash": stored,
            "computed_hash": alt,
            "outcome": "PASS" if ok else "FAIL",
            **SAFETY_LOCKS,
        }

    def _locate(self, report_id: str) -> dict[str, Any] | None:
        # Prefer index via report_id embedded in manifests
        if not self.root.is_dir():
            return None
        for man in self.root.rglob("manifest.json"):
            try:
                data = json.loads(man.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("report_id") == report_id:
                return {"dir": man.parent, "archive_ref": data.get("report_id"), "manifest": data}
        # Fallback parse cssrpt_family_type_date_vNNN (family/type may contain underscores — use known split)
        if report_id.startswith("cssrpt_") and "_v" in report_id:
            # scan already done
            pass
        return None

    def _next_version(self, day_dir: Path) -> int:
        nums = []
        for child in day_dir.iterdir() if day_dir.exists() else []:
            if child.name.startswith("v") and child.is_dir():
                try:
                    nums.append(int(child.name[1:]))
                except ValueError:
                    continue
            if child.name == "FAILED" and child.is_dir():
                for failed in child.iterdir():
                    if failed.name.startswith("v"):
                        try:
                            nums.append(int(failed.name[1:]))
                        except ValueError:
                            continue
        return (max(nums) + 1) if nums else 1

    @staticmethod
    def _safe_segment(value: str) -> str:
        v = str(value or "").strip().replace(" ", "_").lower()
        if not re.match(r"^[a-z0-9_]{1,64}$", v):
            raise ValueError("invalid_path_segment")
        return v
