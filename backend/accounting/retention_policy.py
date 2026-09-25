from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "artifacts" / "accounting_archive"

MINIMUM_HOT_RETENTION_YEARS = 4
ARCHIVE_RETENTION_POLICY = "INDEFINITE_UNTIL_GOVERNANCE_DISPOSITION"
DISPUTE_HOLD_POLICY = "ARCHIVE_AND_DELETE_BLOCKED_WHILE_HOLD_ACTIVE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        # 29-Feb on a non-leap target year.
        return day.replace(month=2, day=28, year=day.year - years)


def canonical_record_hash(payload: dict[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("record_hash", None)
    encoded = json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RetentionAssessment:
    record_date: str
    hot_until: str
    archive_eligible: bool
    dispute_hold: bool
    action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_date": self.record_date,
            "hot_until": self.hot_until,
            "archive_eligible": self.archive_eligible,
            "dispute_hold": self.dispute_hold,
            "action": self.action,
            "minimum_hot_retention_years": MINIMUM_HOT_RETENTION_YEARS,
            "archive_retention_policy": ARCHIVE_RETENTION_POLICY,
        }


def assess_retention(
    record: dict[str, Any],
    *,
    as_of: date | None = None,
    date_fields: tuple[str, ...] = (
        "settlement_date",
        "value_date",
        "transaction_date",
        "recorded_at",
        "created_at",
    ),
) -> RetentionAssessment:
    record_date = None
    for field in date_fields:
        record_date = _parse_date(record.get(field))
        if record_date is not None:
            break
    if record_date is None:
        return RetentionAssessment(
            record_date="UNAVAILABLE",
            hot_until="UNAVAILABLE",
            archive_eligible=False,
            dispute_hold=bool(record.get("dispute_hold")),
            action="RETAIN_HOT_DATE_UNAVAILABLE",
        )

    current = as_of or datetime.now(timezone.utc).date()
    hot_until = record_date.replace(year=record_date.year + MINIMUM_HOT_RETENTION_YEARS)
    hold = bool(record.get("dispute_hold"))
    eligible = current >= hot_until and not hold
    action = "ARCHIVE_ELIGIBLE" if eligible else ("RETAIN_HOT_DISPUTE_HOLD" if hold else "RETAIN_HOT")
    return RetentionAssessment(
        record_date=record_date.isoformat(),
        hot_until=hot_until.isoformat(),
        archive_eligible=eligible,
        dispute_hold=hold,
        action=action,
    )


class AccountingArchiveService:
    """Non-destructive archive service for transaction/account evidence.

    Records remain in hot storage for at least four years. Archive operations
    preserve the full record, add chain-of-custody metadata, and verify a
    SHA-256 content hash. A dispute hold blocks archival/removal.
    """

    def __init__(self, archive_root: Path = DEFAULT_ARCHIVE_ROOT) -> None:
        self.archive_root = archive_root

    def archive_record(
        self,
        record: dict[str, Any],
        *,
        record_type: str,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        assessment = assess_retention(record, as_of=as_of)
        if not assessment.archive_eligible:
            return {
                "status": "RETAIN_HOT",
                "assessment": assessment.as_dict(),
                "archived": False,
            }

        record_hash = canonical_record_hash(record)
        record_date = date.fromisoformat(assessment.record_date)
        record_id = str(
            record.get("ledger_id")
            or record.get("trade_id")
            or record.get("user_id")
            or record_hash[:16]
        )
        folder = self.archive_root / str(record_date.year) / str(record_type).lower()
        folder.mkdir(parents=True, exist_ok=True)
        archive_file = folder / f"{record_id}.json"
        envelope = {
            "schema_version": "css.accounting.archive.v1",
            "record_type": str(record_type).upper(),
            "archived_at": _utc_now(),
            "minimum_hot_retention_years": MINIMUM_HOT_RETENTION_YEARS,
            "archive_retention_policy": ARCHIVE_RETENTION_POLICY,
            "record_hash_sha256": record_hash,
            "chain_of_custody": {
                "source": "CSS_ACCOUNTING_RETENTION",
                "archive_reason": "MINIMUM_HOT_RETENTION_SATISFIED",
                "dispute_hold_checked": True,
            },
            "record": dict(record),
        }
        archive_file.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")

        verify = json.loads(archive_file.read_text(encoding="utf-8"))
        verified_hash = canonical_record_hash(verify["record"])
        if verified_hash != record_hash:
            archive_file.unlink(missing_ok=True)
            raise RuntimeError("ARCHIVE_HASH_VERIFICATION_FAILED")

        return {
            "status": "ARCHIVED",
            "archived": True,
            "archive_path": str(archive_file),
            "record_hash_sha256": record_hash,
            "assessment": assessment.as_dict(),
        }


def retention_policy_payload() -> dict[str, Any]:
    return {
        "minimum_hot_retention_years": MINIMUM_HOT_RETENTION_YEARS,
        "hot_storage_scope": [
            "transaction_details",
            "account_information",
            "fees_and_commissions",
            "receipts_and_statements",
            "agreement_and_acceptance_records",
            "audit_and_provenance_metadata",
        ],
        "archive_retention_policy": ARCHIVE_RETENTION_POLICY,
        "dispute_hold_policy": DISPUTE_HOLD_POLICY,
        "archive_integrity": "SHA256_VERIFIED",
        "retrieval_required": True,
        "audit_replay_required": True,
        "deletion_by_age_alone": False,
    }


__all__ = [
    "AccountingArchiveService",
    "ARCHIVE_RETENTION_POLICY",
    "DISPUTE_HOLD_POLICY",
    "MINIMUM_HOT_RETENTION_YEARS",
    "RetentionAssessment",
    "assess_retention",
    "canonical_record_hash",
    "retention_policy_payload",
]
