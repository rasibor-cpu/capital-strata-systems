"""
Branch EOD Batch Runner (v1)
----------------------------
Admin-only runner to generate a complete EOD batch pack for a branch:

Includes:
- Branch EOD Snapshot (report pack)
- Branch Tickets (ticket pack)
- Exports to artifacts folder as JSON + CSV

This is the operational "end of day" output used by audit for review/printing.
"""

import os
from dataclasses import dataclass
from typing import Optional

from engine.security.user_directory import UserDirectory
from engine.security.rbac import AccessLevel

from engine.security.eod_snapshot_generator import EODSnapshotGenerator, EODRequest
from engine.security.ticket_pack_exporter import TicketPackExporter, TicketExportRequest
from engine.security.report_exporter import ReportExporter


@dataclass
class BranchEODBatchRequest:
    requesting_user_id: str
    business_date: str
    branch: str

    currency: Optional[str] = None
    scope_id_for_limits: Optional[str] = None  # e.g. BRANCH:LAGOS-1

    output_dir: str = "artifacts"


class BranchEODBatchRunner:
    def __init__(
        self,
        *,
        users: UserDirectory,
        eod: EODSnapshotGenerator,
        tickets: TicketPackExporter,
        exporter: ReportExporter,
    ):
        self.users = users
        self.eod = eod
        self.tickets = tickets
        self.exporter = exporter

    def _assert_admin(self, requesting_user_id: str) -> None:
        ent = self.users.require(requesting_user_id)
        if ent.access_level != AccessLevel.LEVEL_4_ADMIN and not ent.super_admin:
            raise PermissionError("Branch EOD batch runner requires Admin or Super Admin")

    def run(self, req: BranchEODBatchRequest) -> None:
        self._assert_admin(req.requesting_user_id)
        os.makedirs(req.output_dir, exist_ok=True)

        # 1) Generate EOD Snapshot for branch
        eod_req = EODRequest(
            requesting_user_id=req.requesting_user_id,
            business_date=req.business_date,
            branch=req.branch,
            currency=req.currency,
            scope_id_for_limits=req.scope_id_for_limits,
        )
        snapshot = self.eod.generate_eod(eod_req)

        # Export snapshot as JSON
        snap_path = os.path.join(req.output_dir, f"branch_eod_snapshot_{req.branch}_{req.business_date}.json")
        self.exporter.export_json(obj=snapshot, path=snap_path)

        # 2) Export tickets for branch
        ticket_req = TicketExportRequest(
            business_date=req.business_date,
            requesting_user_id=req.requesting_user_id,
            branch=req.branch,
            output_dir=req.output_dir,
        )
        self.tickets.export_eod(ticket_req)