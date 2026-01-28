"""
Department EOD Batch Runner (v1)
--------------------------------
Supervisor/Dept-head runner to generate a complete EOD batch pack for a department:

Includes:
- Department EOD Snapshot (report pack)
- Department Tickets (ticket pack)
- Exports to artifacts folder as JSON + CSV

Used for departmental EOD review and management reporting.
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
class DepartmentEODBatchRequest:
    requesting_user_id: str
    business_date: str
    department: str

    currency: Optional[str] = None
    scope_id_for_limits: Optional[str] = None  # e.g. DEPT:TREASURY

    output_dir: str = "artifacts"


class DepartmentEODBatchRunner:
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

    def _assert_supervisor_or_higher(self, requesting_user_id: str) -> None:
        ent = self.users.require(requesting_user_id)
        if ent.access_level not in {
            AccessLevel.LEVEL_3_SUPERVISOR,
            AccessLevel.LEVEL_4_ADMIN,
        } and not ent.super_admin:
            raise PermissionError("Department EOD batch runner requires Supervisor/Admin/Super Admin")

    def run(self, req: DepartmentEODBatchRequest) -> None:
        self._assert_supervisor_or_higher(req.requesting_user_id)
        os.makedirs(req.output_dir, exist_ok=True)

        # 1) Generate EOD Snapshot for department
        eod_req = EODRequest(
            requesting_user_id=req.requesting_user_id,
            business_date=req.business_date,
            department=req.department,
            currency=req.currency,
            scope_id_for_limits=req.scope_id_for_limits,
        )
        snapshot = self.eod.generate_eod(eod_req)

        # Export snapshot as JSON
        snap_path = os.path.join(req.output_dir, f"dept_eod_snapshot_{req.department}_{req.business_date}.json")
        self.exporter.export_json(obj=snapshot, path=snap_path)

        # 2) Export tickets for department
        ticket_req = TicketExportRequest(
            business_date=req.business_date,
            requesting_user_id=req.requesting_user_id,
            department=req.department,
            output_dir=req.output_dir,
        )
        self.tickets.export_eod(ticket_req)