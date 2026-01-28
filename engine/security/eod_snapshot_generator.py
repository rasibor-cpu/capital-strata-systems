"""
EOD Snapshot Generator (v1)
---------------------------
Generates end-of-day (and periodic) snapshots for audit and management review.

Design intent:
- Users can generate personal reports
- Supervisors/Admin can generate for others
- Designated branch admin can generate branch EOD / periodic packs
- Country aggregation is reserved for super admin (policy layer will enforce)

This generator reads from:
- UserActivityLedger (truth of actions)
- ReportPackGenerator (pack composition)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from engine.security.user_directory import UserDirectory
from engine.security.rbac import AccessLevel
from engine.security.report_pack_generator import ReportPackGenerator, ReportPackRequest, ReportPack


@dataclass
class EODRequest:
    requesting_user_id: str
    business_date: str

    # scope
    target_user_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    country: Optional[str] = None

    currency: Optional[str] = None
    scope_id_for_limits: Optional[str] = None  # e.g. BRANCH:LAGOS-1


@dataclass
class EODSnapshot:
    meta: Dict[str, Any]
    pack: ReportPack


class EODSnapshotGenerator:
    def __init__(self, *, users: UserDirectory, packs: ReportPackGenerator):
        self.users = users
        self.packs = packs

    def _assert_eod_scope_allowed(self, req: EODRequest) -> None:
        requester = self.users.require(req.requesting_user_id)

        # Personal EOD always allowed
        if req.target_user_id is None or req.target_user_id == req.requesting_user_id:
            return

        # Reporting on other users requires supervisor+
        if requester.access_level not in {
            AccessLevel.LEVEL_3_SUPERVISOR,
            AccessLevel.LEVEL_4_ADMIN,
        }:
            raise PermissionError("Insufficient privileges for EOD on other users")

        # Branch EOD requires ADMIN or higher
        if req.branch is not None and requester.access_level not in {
            AccessLevel.LEVEL_4_ADMIN,
        }:
            raise PermissionError("Only designated admin can generate branch EOD packs")

        # Country-level reserved for super admin (v1: not enabled here)
        if req.country is not None:
            raise PermissionError("Country aggregation reserved for super admin (not enabled in v1 generator)")

    def generate_eod(self, req: EODRequest) -> EODSnapshot:
        self._assert_eod_scope_allowed(req)

        pack_req = ReportPackRequest(
            requesting_user_id=req.requesting_user_id,
            start_date=req.business_date,
            end_date=req.business_date,
            target_user_id=req.target_user_id,
            department=req.department,
            branch=req.branch,
            country=req.country,
            currency=req.currency,
            scope_id_for_limits=req.scope_id_for_limits,
        )

        pack = self.packs.generate(pack_req)

        return EODSnapshot(
            meta={
                "type": "EOD",
                "business_date": req.business_date,
                "requested_by": req.requesting_user_id,
                "target_user_id": req.target_user_id,
                "department": req.department,
                "branch": req.branch,
                "country": req.country,
                "currency": req.currency,
                "scope_id_for_limits": req.scope_id_for_limits,
            },
            pack=pack,
        )

    def generate_periodic(self, *, req: EODRequest, start_date: str, end_date: str) -> EODSnapshot:
        """
        Periodic snapshot (weekly/monthly/custom range).
        """
        self._assert_eod_scope_allowed(req)

        pack_req = ReportPackRequest(
            requesting_user_id=req.requesting_user_id,
            start_date=start_date,
            end_date=end_date,
            target_user_id=req.target_user_id,
            department=req.department,
            branch=req.branch,
            country=req.country,
            currency=req.currency,
            scope_id_for_limits=req.scope_id_for_limits,
        )

        pack = self.packs.generate(pack_req)

        return EODSnapshot(
            meta={
                "type": "PERIODIC",
                "start_date": start_date,
                "end_date": end_date,
                "requested_by": req.requesting_user_id,
                "target_user_id": req.target_user_id,
                "department": req.department,
                "branch": req.branch,
                "country": req.country,
                "currency": req.currency,
                "scope_id_for_limits": req.scope_id_for_limits,
            },
            pack=pack,
        )