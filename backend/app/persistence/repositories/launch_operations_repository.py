from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
    CustomerNotificationPolicy,
)
from backend.commercialization.launch_evidence_dossier import LaunchEvidenceItem
from backend.commercialization.notification_delivery_provider import (
    NotificationProviderConfiguration,
)


class LaunchOperationsRepository(BaseRepository):
    def create_notification_provider_configuration(
        self,
        record: NotificationProviderConfiguration,
    ) -> None:
        self.execute(
            """
            INSERT INTO notification_delivery_provider_configurations (
                provider_id, channel, status, environment,
                provider_account_reference, approval_reference,
                evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.provider_id,
                record.channel.value,
                record.status.value,
                record.environment,
                record.provider_account_reference,
                record.approval_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_notification_provider_configuration(
        self,
        provider_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM notification_delivery_provider_configurations
            WHERE provider_id = ?
            """,
            (provider_id,),
        )
        return dict(row) if row is not None else None

    def create_notification_policy(
        self,
        policy: CustomerNotificationPolicy,
    ) -> None:
        self.execute(
            """
            INSERT INTO customer_notification_policies (
                policy_id, jurisdiction_code, notification_type,
                lead_time_hours, approved_for_production,
                approval_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy.policy_id,
                policy.jurisdiction_code,
                policy.notification_type.value,
                policy.lead_time_hours,
                int(policy.approved_for_production),
                policy.approval_reference,
                json.dumps(list(policy.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_notification_intent(
        self,
        intent: CustomerNotificationIntent,
    ) -> None:
        self.execute(
            """
            INSERT INTO customer_notification_intents (
                notification_id, customer_id, account_reference,
                notification_type, scheduled_for, policy_id,
                evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent.notification_id,
                intent.customer_id,
                intent.account_reference,
                intent.notification_type.value,
                intent.scheduled_for,
                intent.policy_id,
                json.dumps(list(intent.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_launch_evidence_item(
        self,
        dossier_id: str,
        item: LaunchEvidenceItem,
    ) -> None:
        self.execute(
            """
            INSERT INTO launch_evidence_items (
                dossier_id, category, evidence_reference, approved
            ) VALUES (?, ?, ?, ?)
            """,
            (
                dossier_id,
                item.category.value,
                item.evidence_reference,
                int(item.approved),
            ),
        )

    def list_launch_evidence(
        self,
        dossier_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM launch_evidence_items
            WHERE dossier_id = ?
            ORDER BY category ASC
            """,
            (dossier_id,),
        )
        return [dict(row) for row in rows]

    def get_notification_intent(
        self,
        notification_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM customer_notification_intents
            WHERE notification_id = ?
            """,
            (notification_id,),
        )
        return dict(row) if row is not None else None

    def list_notification_intents(
        self,
        customer_id: str,
        account_reference: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM customer_notification_intents
            WHERE customer_id = ? AND account_reference = ?
            ORDER BY scheduled_for ASC, notification_id ASC
            """,
            (customer_id, account_reference),
        )
        return [dict(row) for row in rows]
