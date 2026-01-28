"""
Ticket Pack Exporter (v1)
-------------------------
Generates and exports EOD ticket packs to:
- JSON
- CSV

Default output folder: ./artifacts/

This module glues:
- TicketPackBuilder  -> ticket rows (dicts)
- ReportExporter     -> file outputs
"""

import os
from dataclasses import dataclass
from typing import Optional

from engine.security.ticket_pack_builder import TicketPackBuilder, TicketRequest
from engine.security.report_exporter import ReportExporter


@dataclass
class TicketExportRequest:
    business_date: str
    requesting_user_id: str

    # optional filters
    target_user_id: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None

    output_dir: str = "artifacts"


class TicketPackExporter:
    def __init__(self, *, builder: TicketPackBuilder, exporter: ReportExporter):
        self.builder = builder
        self.exporter = exporter

    def export_eod(self, req: TicketExportRequest) -> None:
        os.makedirs(req.output_dir, exist_ok=True)

        ticket_req = TicketRequest(
            business_date=req.business_date,
            requesting_user_id=req.requesting_user_id,
            target_user_id=req.target_user_id,
            branch=req.branch,
            department=req.department,
            country=req.country,
        )

        tickets = self.builder.build_eod_ticket_pack(ticket_req)

        json_path = os.path.join(req.output_dir, f"tickets_{req.business_date}.json")
        csv_path = os.path.join(req.output_dir, f"tickets_{req.business_date}.csv")

        self.exporter.export_json(obj=tickets, path=json_path)
        self.exporter.export_csv(rows=tickets, path=csv_path)