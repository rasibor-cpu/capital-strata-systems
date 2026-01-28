"""
Country Aggregation Manager (v1)
--------------------------------
Country-level reporting and aggregation is reserved for Super Admin.

This module:
- Enforces privilege for country aggregation
- Produces consolidated periodic/EOD report packs for a country
- Relies on existing generators (EODSnapshotGenerator / ReportPackGenerator)

NOTE:
- v1 only enforces "super admin" via user_directory flag
- v2 can enforce via RBAC + named permissions + approval workflow
"""

from dataclasses import dataclass
from typing import List, Dict, Any

from engine.security.user_directory import UserDirectory
from engine.security.eod_snapshot_generator import EODSnapshotGenerator, EODRequest, EODSnapshot


@dataclass
class CountryAggregationRequest:
    requesting_user_id: str
    country: str
    business_date: str

    # optional: list of branches to include; if empty, include all (v1: caller supplies)
    branches: List[str]
    currency: str
    scope_id_for_limits: str  # e.g. "COUNTRY:NIGERIA"


@dataclass
class CountryAggregationResult:
    meta: Dict[str, Any]
    branch_snapshots: List[EODSnapshot]


class CountryAggregationManager:
    def __init__(self, *, users: UserDirectory, eod: EODSnapshotGenerator):
        self.users = users
        self.eod = eod

    def _assert_super_admin(self, requesting_user_id: str) -> None:
        ent = self.users.require(requesting_user_id)
        if not ent.super_admin:
            raise PermissionError("Country aggregation requires Super Admin privileges")

    def generate_country_eod(self, req: CountryAggregationRequest) -> CountryAggregationResult:
        """
        Generates a set of branch EOD snapshots that represent a country consolidation pack.
        """
        self._assert_super_admin(req.requesting_user_id)

        snapshots: List[EODSnapshot] = []
        for br in req.branches:
            eod_req = EODRequest(
                requesting_user_id=req.requesting_user_id,
                business_date=req.business_date,
                branch=br,
                country=req.country,
                currency=req.currency,
                scope_id_for_limits=req.scope_id_for_limits,
            )
            snapshots.append(self.eod.generate_eod(eod_req))

        return CountryAggregationResult(
            meta={
                "type": "COUNTRY_EOD",
                "country": req.country,
                "business_date": req.business_date,
                "requested_by": req.requesting_user_id,
                "branches": req.branches,
                "currency": req.currency,
                "scope_id_for_limits": req.scope_id_for_limits,
            },
            branch_snapshots=snapshots,
        )