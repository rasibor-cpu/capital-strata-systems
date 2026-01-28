"""
Country EOD Batch Runner (v1)
-----------------------------
Super Admin only runner to generate a complete EOD batch pack for a country:

Includes:
- Country consolidation result (list of branch EOD snapshots)
- Export to artifacts folder as JSON

Note:
- Ticket packs remain branch-level in v1.
- This runner consolidates branch snapshots for country-level management + audit review.
"""

import os
from dataclasses import dataclass
from typing import List

from engine.security.country_aggregation_manager import (
    CountryAggregationManager,
    CountryAggregationRequest,
)
from engine.security.report_exporter import ReportExporter


@dataclass
class CountryEODBatchRequest:
    requesting_user_id: str
    country: str
    business_date: str
    branches: List[str]
    currency: str
    scope_id_for_limits: str  # e.g. COUNTRY:NIGERIA

    output_dir: str = "artifacts"


class CountryEODBatchRunner:
    def __init__(
        self,
        *,
        aggregator: CountryAggregationManager,
        exporter: ReportExporter,
    ):
        self.aggregator = aggregator
        self.exporter = exporter

    def run(self, req: CountryEODBatchRequest) -> None:
        os.makedirs(req.output_dir, exist_ok=True)

        agg_req = CountryAggregationRequest(
            requesting_user_id=req.requesting_user_id,
            country=req.country,
            business_date=req.business_date,
            branches=req.branches,
            currency=req.currency,
            scope_id_for_limits=req.scope_id_for_limits,
        )

        result = self.aggregator.generate_country_eod(agg_req)

        out_path = os.path.join(
            req.output_dir,
            f"country_eod_pack_{req.country}_{req.business_date}.json",
        )
        self.exporter.export_json(obj=result, path=out_path)