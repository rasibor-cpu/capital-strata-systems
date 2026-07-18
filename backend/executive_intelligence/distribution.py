"""Controlled email distribution + print/email audit for Daily Executive Briefs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.print_report import assert_final_printable, pdf_sha256, render_printable_pdf
from backend.executive_intelligence.rbac_grants import (
    ACTION_EMAIL,
    ACTION_PRINT,
    ExecutiveBriefAccessControl,
)
from backend.executive_intelligence.recipients import (
    RECIPIENT_ROLE_NOT_AUTHORIZED,
    RecipientDirectory,
)
from backend.executive_intelligence.utils import utc_now_iso


DEFAULT_DIST_RELATIVE = Path("artifacts/runtime_reports/executive_intelligence_archive/distribution")


class EmailTransport(Protocol):
    def send(
        self,
        *,
        subject: str,
        html_body: str,
        recipients: list[str],
        attachment_name: str | None,
        attachment_bytes: bytes | None,
    ) -> dict[str, Any]:
        ...


class NotConfiguredEmailTransport:
    def send(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "NOT_CONFIGURED",
            "provider_message_id": None,
            "reason": "email_transport_not_configured",
            "dry_run": True,
        }


class MockEmailTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict[str, Any]] = []

    def send(
        self,
        *,
        subject: str,
        html_body: str,
        recipients: list[str],
        attachment_name: str | None,
        attachment_bytes: bytes | None,
    ) -> dict[str, Any]:
        if self.fail:
            return {"status": "FAILED", "provider_message_id": None, "reason": "mock_failure", "dry_run": True}
        msg_id = f"mock-{hashlib.sha256(subject.encode()).hexdigest()[:12]}"
        record = {
            "status": "SENT",
            "provider_message_id": msg_id,
            "recipient_count": len(recipients),
            "attachment_name": attachment_name,
            "attachment_sha256": hashlib.sha256(attachment_bytes).hexdigest() if attachment_bytes else None,
            "dry_run": True,
        }
        self.sent.append(record)
        return record


class ExecutiveBriefDistributionService:
    def __init__(
        self,
        *,
        root: Path | str | None = None,
        access: ExecutiveBriefAccessControl | None = None,
        transport: EmailTransport | None = None,
        recipient_directory: RecipientDirectory | None = None,
    ) -> None:
        self.root = Path(root) if root else Path.cwd() / DEFAULT_DIST_RELATIVE
        self.root.mkdir(parents=True, exist_ok=True)
        self.access = access or ExecutiveBriefAccessControl()
        self.transport = transport or _load_transport_from_env()
        self.recipients = recipient_directory or RecipientDirectory()
        self.lists_path = self.root / "recipient_lists.json"
        self.print_audit_path = self.root / "print_audit.jsonl"
        self.email_audit_path = self.root / "email_audit.jsonl"

    # ── Recipient governance ──────────────────────────────────────────
    def upsert_recipient_list(
        self,
        *,
        admin_role: str,
        admin_user_id: str,
        list_id: str,
        recipient_ids: list[str],
    ) -> dict[str, Any]:
        auth = self.access.authorize(role=admin_role, user_id=admin_user_id, action="manage_executive_brief_grants")
        if not auth["allowed"]:
            return {"status": "DENIED", "reason": auth["reason"]}

        validation = self.recipients.validate_recipients([str(r) for r in recipient_ids])
        if not validation["ok"]:
            return {
                "status": "DENIED",
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "eligible_count": validation["eligible_count"],
                "rejected_count": validation["rejected_count"],
                "rejected": validation["rejected"],
            }

        data = self._load_lists()
        # Store opaque CSS user ids only (never raw external addresses)
        data["lists"][list_id] = {
            "recipient_ids": list(validation["delivery_recipient_ids"]),
            "updated_by": admin_user_id,
            "updated_at_utc": utc_now_iso(),
            "approved": True,
        }
        self._save_json(self.lists_path, data)
        return {
            "status": "OK",
            "list_id": list_id,
            "recipient_count": len(data["lists"][list_id]["recipient_ids"]),
            "eligible_count": validation["eligible_count"],
        }

    def _load_lists(self) -> dict[str, Any]:
        if not self.lists_path.is_file():
            return {"schema_version": "css.executive_brief_recipient_lists.v1", "lists": {}}
        try:
            data = json.loads(self.lists_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("lists", {})
                return data
        except Exception:
            pass
        return {"schema_version": "css.executive_brief_recipient_lists.v1", "lists": {}}

    # ── Print audit / authorization ───────────────────────────────────
    def authorization_status(self, *, role: str, user_id: str) -> dict[str, Any]:
        print_auth = self.access.authorize(role=role, user_id=user_id, action=ACTION_PRINT)
        email_auth = self.access.authorize(role=role, user_id=user_id, action=ACTION_EMAIL)
        return {
            "print_allowed": bool(print_auth["allowed"]),
            "email_allowed": bool(email_auth["allowed"]),
            "print_permission": print_auth.get("permission_used"),
            "email_permission": email_auth.get("permission_used"),
            "print_reason": print_auth.get("reason"),
            "email_reason": email_auth.get("reason"),
            **SAFETY_LOCKS,
        }

    def record_print_audit(
        self,
        *,
        brief: Mapping[str, Any],
        role: str,
        user_id: str,
        destination: str,
        outcome: str,
        failure_reason: str | None = None,
        permission_used: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event": "PRINT_OR_PDF_EXPORT",
            "report_id": brief.get("report_id"),
            "report_date": brief.get("report_date"),
            "report_version": brief.get("report_version") or brief.get("version"),
            "report_hash": brief.get("report_hash"),
            "requested_by": user_id,
            "user_role": str(role).upper(),
            "permission_used": permission_used,
            "requested_at_utc": utc_now_iso(),
            "printer_or_export_destination": destination,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "advisory_only": True,
            **SAFETY_LOCKS,
        }
        self._append_jsonl(self.print_audit_path, event)
        return event

    def authorize_and_render_pdf(
        self,
        *,
        brief: Mapping[str, Any],
        role: str,
        user_id: str,
        destination: str = "pdf_export",
    ) -> dict[str, Any]:
        auth = self.access.authorize(role=role, user_id=user_id, action=ACTION_PRINT)
        if not auth["allowed"]:
            event = self.record_print_audit(
                brief=brief,
                role=role,
                user_id=user_id,
                destination=destination,
                outcome="DENIED",
                failure_reason=auth["reason"],
                permission_used=None,
            )
            return {"status": "DENIED", "audit": event, "reason": auth["reason"]}
        try:
            assert_final_printable(brief)
            pdf = render_printable_pdf(brief, printed_by=user_id)
        except PermissionError as exc:
            event = self.record_print_audit(
                brief=brief,
                role=role,
                user_id=user_id,
                destination=destination,
                outcome="DENIED",
                failure_reason=str(exc),
                permission_used=auth.get("permission_used"),
            )
            return {"status": "DENIED", "audit": event, "reason": str(exc)}
        except Exception as exc:
            event = self.record_print_audit(
                brief=brief,
                role=role,
                user_id=user_id,
                destination=destination,
                outcome="FAILED",
                failure_reason=str(exc),
                permission_used=auth.get("permission_used"),
            )
            return {"status": "FAILED", "audit": event, "reason": str(exc)}

        event = self.record_print_audit(
            brief=brief,
            role=role,
            user_id=user_id,
            destination=destination,
            outcome="OK",
            permission_used=auth.get("permission_used"),
        )
        return {
            "status": "OK",
            "pdf_bytes": pdf,
            "pdf_sha256": pdf_sha256(pdf),
            "audit": event,
            **SAFETY_LOCKS,
        }

    def send_email(
        self,
        *,
        brief: Mapping[str, Any],
        role: str,
        user_id: str,
        list_id: str,
        bypass_recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Send FINAL brief to an approved recipient list.

        ``bypass_recipients`` is accepted only to explicitly reject API payload
        bypass attempts — any non-empty value fails closed.
        """
        if bypass_recipients:
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=None,
                list_id=list_id,
                eligible_count=0,
                rejected_count=len(bypass_recipients),
                result="DENIED",
                failure_reason=RECIPIENT_ROLE_NOT_AUTHORIZED,
            )
            return {
                "status": "DENIED",
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "direct_recipient_payload_not_allowed",
                "audit": event,
            }

        auth = self.access.authorize(role=role, user_id=user_id, action=ACTION_EMAIL)
        if not auth["allowed"]:
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=None,
                list_id=list_id,
                eligible_count=0,
                rejected_count=0,
                result="DENIED",
                failure_reason=auth["reason"],
            )
            return {"status": "DENIED", "audit": event, "reason": auth["reason"]}

        try:
            assert_final_printable(brief)
        except PermissionError as exc:
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=auth.get("permission_used"),
                list_id=list_id,
                eligible_count=0,
                rejected_count=0,
                result="DENIED",
                failure_reason=str(exc),
            )
            return {"status": "DENIED", "audit": event, "reason": str(exc)}

        lists = self._load_lists().get("lists") or {}
        entry = lists.get(list_id)
        if not isinstance(entry, Mapping) or not entry.get("approved"):
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=auth.get("permission_used"),
                list_id=list_id,
                eligible_count=0,
                rejected_count=0,
                result="DENIED",
                failure_reason="unapproved_or_missing_recipient_list",
            )
            return {"status": "DENIED", "audit": event, "reason": "unapproved_or_missing_recipient_list"}

        recipients = list(entry.get("recipient_ids") or [])
        if not recipients:
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=auth.get("permission_used"),
                list_id=list_id,
                eligible_count=0,
                rejected_count=0,
                result="DENIED",
                failure_reason="empty_recipient_list",
            )
            return {"status": "DENIED", "audit": event, "reason": "empty_recipient_list"}

        # Server-side revalidation at send time (even if list was previously approved)
        validation = self.recipients.validate_recipients(recipients)
        if not validation["ok"]:
            event = self._email_audit(
                brief=brief,
                sender=user_id,
                role=role,
                permission_used=auth.get("permission_used"),
                list_id=list_id,
                eligible_count=validation["eligible_count"],
                rejected_count=validation["rejected_count"],
                result="DENIED",
                failure_reason=RECIPIENT_ROLE_NOT_AUTHORIZED,
            )
            return {
                "status": "DENIED",
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "eligible_count": validation["eligible_count"],
                "rejected_count": validation["rejected_count"],
                "audit": event,
                **SAFETY_LOCKS,
            }

        delivery_ids = list(validation["delivery_recipient_ids"])
        pdf = render_printable_pdf(brief, printed_by=user_id)
        attachment_hash = pdf_sha256(pdf)
        subject = (
            f"[CSS ADVISORY] Daily Executive Brief {brief.get('report_date')} "
            f"{brief.get('report_version')} hash={str(brief.get('report_hash'))[:12]}"
        )
        html_body = (
            f"<p><strong>ADVISORY ONLY</strong> — execution blocked.</p>"
            f"<p>Report ID: {brief.get('report_id')}<br/>"
            f"Date: {brief.get('report_date')}<br/>"
            f"Version: {brief.get('report_version')}<br/>"
            f"Hash: {brief.get('report_hash')}</p>"
            f"<p>PDF attachment is the official printable FINAL brief.</p>"
        )
        result = self.transport.send(
            subject=subject,
            html_body=html_body,
            recipients=delivery_ids,
            attachment_name=f"executive_morning_brief_{brief.get('report_date')}.pdf",
            attachment_bytes=pdf,
        )
        status = str(result.get("status") or "FAILED")
        event = self._email_audit(
            brief=brief,
            sender=user_id,
            role=role,
            permission_used=auth.get("permission_used"),
            list_id=list_id,
            eligible_count=validation["eligible_count"],
            rejected_count=0,
            result=status,
            failure_reason=result.get("reason"),
            provider_message_id=result.get("provider_message_id"),
            attachment_hash=attachment_hash,
        )
        return {
            "status": status,
            "audit": event,
            "transport": {k: v for k, v in result.items() if k != "raw"},
            "attachment_sha256": attachment_hash,
            "eligible_count": validation["eligible_count"],
            **SAFETY_LOCKS,
        }

    def _email_audit(self, **kwargs: Any) -> dict[str, Any]:
        event = {
            "event": "EMAIL_DISTRIBUTION",
            "report_id": kwargs["brief"].get("report_id"),
            "report_date": kwargs["brief"].get("report_date"),
            "report_version": kwargs["brief"].get("report_version") or kwargs["brief"].get("version"),
            "report_hash": kwargs["brief"].get("report_hash"),
            "sender_identity": kwargs.get("sender"),
            "user_role": str(kwargs.get("role") or "").upper(),
            "permission_used": kwargs.get("permission_used"),
            "approved_recipient_list_id": kwargs.get("list_id"),
            "eligible_recipient_count": kwargs.get("eligible_count", kwargs.get("recipient_count")),
            "rejected_recipient_count": kwargs.get("rejected_count", 0),
            "sent_at_utc": utc_now_iso(),
            "attachment_hash": kwargs.get("attachment_hash"),
            "result": kwargs.get("result"),
            "provider_message_identifier": kwargs.get("provider_message_id"),
            "failure_reason": kwargs.get("failure_reason"),
            "advisory_only": True,
            **SAFETY_LOCKS,
        }
        self._append_jsonl(self.email_audit_path, event)
        return event

    def print_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._read_jsonl(self.print_audit_path, limit=limit)

    def email_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._read_jsonl(self.email_audit_path, limit=limit)

    @staticmethod
    def _append_jsonl(path: Path, event: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(event), sort_keys=True, default=str) + "\n")

    @staticmethod
    def _read_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]

    @staticmethod
    def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, str(path))
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def _load_transport_from_env() -> EmailTransport:
    # Disabled by default — never send real email unless explicitly configured later.
    # CSS_EXEC_BRIEF_EMAIL_TRANSPORT=mock enables mock; otherwise NOT_CONFIGURED.
    mode = str(os.environ.get("CSS_EXEC_BRIEF_EMAIL_TRANSPORT", "disabled")).strip().lower()
    if mode == "mock":
        return MockEmailTransport()
    return NotConfiguredEmailTransport()
