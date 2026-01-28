"""
Periodic Batch Runner (v1)
--------------------------
Generates periodic packs (weekly/monthly/custom range) for:

- Branch (Admin/Super Admin)
- Department (Supervisor/Admin/Super Admin)
- Country (Super Admin only; consolidation pack)

Outputs:
- JSON files written into artifacts/

Uses:
- EODSnapshotGenerator.generate_periodic for branch/department
- CountryAggregationManager for country (v1: branch snapshots per date, so periodic = loop dates outside this file later)
"""

import os
from dataclasses import dataclass
from typing import Optional, List

from engine.security.user_directory import UserDirectory
from engine.security.rbac import AccessLevel

from engine.security.eod_snapshot_generator import EODSnapshotGenerator, EODRequest
from engine.security.country_aggregation_manager import CountryAggregationManager, CountryAggregationRequest
from engine.security.report_exporter import ReportExporter


@dataclass
class PeriodicBatchRequest:
    requesting_user_id: str
    start_date: str
    end_date: str

    # scope selectors (choose one)
    branch: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None

    branches_for_country: Optional[List[str]] = None

    currency: Optional[str] = None
    scope_id_for_limits: Optional[str] = None  # BRANCH:..., DEPT:..., COUNTRY:...

    output_dir: str = "artifacts"


class PeriodicBatchRunner:
    def __init__(
        self,
        *,
        users: UserDirectory,
        eod: EODSnapshotGenerator,
        country_agg: CountryAggregationManager,
        exporter: ReportExporter,
    ):
        self.users = users
        self.eod = eod
        self.country_agg = country_agg
        self.exporter = exporter

    def run(self, req: PeriodicBatchRequest) -> None:
        os.makedirs(req.output_dir, exist_ok=True)
        ent = self.users.require(req.requesting_user_id)

        # ─────────────────────────────
        # Branch periodic pack
        # ─────────────────────────────
        if req.branch is not None:
            if ent.access_level != AccessLevel.LEVEL_4_ADMIN and not ent.super_admin:
                raise PermissionError("Branch periodic runner requires Admin or Super Admin")

            eod_req = EODRequest(
                requesting_user_id=req.requesting_user_id,
                business_date=req.start_date,  # placeholder (not used by generate_periodic meta)
                branch=req.branch,
                currency=req.currency,
                scope_id_for_limits=req.scope_id_for_limits,
            )
            snap = self.eod.generate_periodic(req=eod_req, start_date=req.start_date, end_date=req.end_date)

            out_path = os.path.join(req.output_dir, f"branch_periodic_{req.branch}_{req.start_date}_to_{req.end_date}.json")
            self.exporter.export_json(obj=snap, path=out_path)
            return

        # ─────────────────────────────
        # Department periodic pack
        # ─────────────────────────────
        if req.department is not None:
            if ent.access_level not in {AccessLevel.LEVEL_3_SUPERVISOR, AccessLevel.LEVEL_4_ADMIN} and not ent.super_admin:
                raise PermissionError("Department periodic runner requires Supervisor/Admin/Super Admin")

            eod_req = EODRequest(
                requesting_user_id=req.requesting_user_id,
                business_date=req.start_date,
                department=req.department,
                currency=req.currency,
                scope_id_for_limits=req.scope_id_for_limits,
            )
            snap = self.eod.generate_periodic(req=eod_req, start_date=req.start_date, end_date=req.end_date)

            out_path = os.path.join(req.output_dir, f"dept_periodic_{req.department}_{req.start_date}_to_{req.end_date}.json")
            self.exporter.export_json(obj=snap, path=out_path)
            return

        # ─────────────────────────────
        # Country periodic pack (v1 note)
        # ─────────────────────────────
        if req.country is not None:
            if not ent.super_admin:
                raise PermissionError("Country periodic runner requires Super Admin")

            if not req.branches_for_country:
                raise ValueError("branches_for_country is required for country periodic packs in v1")

            # v1 limitation: country aggregation is EOD per business_date.
            # For periodic, we export a "plan" object here; date-looping runner can be added later.
            agg_req = CountryAggregationRequest(
                requesting_user_id=req.requesting_user_id,
                country=req.country,
                business_date=req.start_date,  # v1 placeholder
                branches=req.branches_for_country,
                currency=req.currency or "NA",
                scope_id_for_limits=req.scope_id_for_limits or f"COUNTRY:{req.country}",
            )

            out_path = os.path.join(req.output_dir, f"country_periodic_plan_{req.country}_{req.start_date}_to_{req.end_date}.json")
            self.exporter.export_json(
                obj={
                    "type": "COUNTRY_PERIODIC_PLAN",
                    "country": req.country,
                    "start_date": req.start_date,
                    "end_date": req.end_date,
                    "branches": req.branches_for_country,
                    "note": "v1 requires looping business_date per day and calling country aggregation per day; implement in v2 runner",
                    "template_request": agg_req,
                },
                path=out_path,
            )
            return

        raise ValueError("Must specify one scope: branch OR department OR country")