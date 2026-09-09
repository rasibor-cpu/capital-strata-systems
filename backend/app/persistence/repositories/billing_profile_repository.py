from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.billing_profile import (
    CommercialBillingProfile,
)


class BillingProfileRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002I commercial
    billing profiles.

    Deliberately exposes no update or delete method.

    Duplicate insertion for the same billing_profile_id fails at the
    primary-key constraint rather than rewriting commercial billing
    context.
    """

    def create_profile(
        self,
        profile: CommercialBillingProfile,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.billing_profile_id,
                profile.terms_id,
                profile.party_type.value,
                profile.bill_to_name,
                profile.bill_to_reference,
                profile.seller_reference,
                profile.tax_treatment_status.value,
                profile.payment_terms_status.value,
                profile.effective_from,
                json.dumps(
                    list(profile.evidence_refs),
                    separators=(",", ":"),
                ),
                profile.effective_to,
            ),
        )

    def get_by_profile_id(
        self,
        billing_profile_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_billing_profiles
            WHERE billing_profile_id = ?
            """,
            (billing_profile_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_terms_id(
        self,
        terms_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_billing_profiles
            WHERE terms_id = ?
            ORDER BY created_at ASC, billing_profile_id ASC
            """,
            (terms_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_billing_profiles
            ORDER BY created_at ASC, billing_profile_id ASC
            """
        )

        return [dict(row) for row in rows]
