"""Metadata-only vault backup manifest support for ESMS governance.

The backup manager exports already-encrypted vault records plus metadata needed
to verify manifest integrity. It never decrypts credential material, never writes
to disk by default, and does not claim restore support.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any

from backend.security.credential_vault import CredentialVault
from backend.security.vault_models import BackupMetadata, utc_now


SCHEMA_VERSION = "css.vault.backup_manifest.v1"


class VaultBackupManager:
    """Create verifiable encrypted-record backup manifests without plaintext."""

    def __init__(self, vault: CredentialVault):
        self.vault = vault

    def create_manifest(self) -> tuple[BackupMetadata, dict[str, Any]]:
        records = sorted(
            (record.as_dict() for record in self.vault.storage.list()),
            key=lambda row: str(row.get("metadata", {}).get("vcid", "")),
        )
        body: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "backup_id": str(uuid.uuid4()),
            "created": utc_now(),
            "record_count": len(records),
            "records": records,
            "encryption_status": "ENCRYPTED_RECORDS_ONLY",
            "contains_plaintext": False,
            "plaintext_export_allowed": False,
            "restore_supported": False,
            "restore_performed": False,
            "advisory_only": True,
            "execution_allowed": False,
        }
        manifest_sha = _manifest_sha(body)
        metadata = BackupMetadata(
            backup_id=body["backup_id"],
            created=body["created"],
            record_count=len(records),
            manifest_sha256=manifest_sha,
            contains_plaintext=False,
        )
        body["backup_metadata"] = asdict(metadata)
        body["manifest_sha256"] = manifest_sha
        return metadata, body

    @staticmethod
    def verify(body: Mapping[str, Any]) -> bool:
        if not isinstance(body, Mapping):
            return False
        if body.get("schema_version") != SCHEMA_VERSION:
            return False
        if body.get("contains_plaintext") is not False:
            return False
        if body.get("plaintext_export_allowed") is not False:
            return False
        if body.get("restore_performed") is not False:
            return False
        records = body.get("records")
        if not isinstance(records, list):
            return False
        if int(body.get("record_count", -1)) != len(records):
            return False
        expected = str(body.get("manifest_sha256") or "")
        if not expected:
            return False
        metadata = body.get("backup_metadata")
        if not isinstance(metadata, Mapping):
            return False
        if str(metadata.get("manifest_sha256") or "") != expected:
            return False
        return _manifest_sha(body) == expected

    @staticmethod
    def restore_manifest(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "status": "UNSUPPORTED",
            "reason": "VAULT_RESTORE_NOT_IMPLEMENTED_IN_FOUNDATION_PHASE",
            "restore_performed": False,
            "production_filesystem_touched": False,
            "advisory_only": True,
            "execution_allowed": False,
        }


def _manifest_sha(body: Mapping[str, Any]) -> str:
    canonical = {
        key: value
        for key, value in dict(body).items()
        if key not in {"manifest_sha256", "backup_metadata"}
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["SCHEMA_VERSION", "VaultBackupManager"]
