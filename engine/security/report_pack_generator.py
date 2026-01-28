"""
Report Pack Generator (v1)
--------------------------
Generates audit-ready reporting packs with permission enforcement.

Outputs include (where available in v1 data):
- executed trades
- outstanding trades (open positions)
- open vs closed positions
- running balances per currency (activity-derived)
- exposure utilization vs limits (via tracker)
- aggregations by user/department/branch/country (v1: meta-driven)

Permission rules:
- user can generate own reports
- supervisors/admins can generate for other users
- designated admins can generate EOD/periodic reports for their branch
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Any

from engine.security.user_activity_ledger import UserActivityLedger, UserActivityRecord
from engine.security.user_directory import UserDirectory
from engine.security.rbac import AccessLevel
from engine.security.trade_exposure_tracker import TradeExposureTracker
from engine.security.institutional_limit_controller import InstitutionalLimitController


@dataclass
class ReportPackRequest:
    requesting_user_id: str
    start_date: str
    end_date: str

    # scope selection (choose one or combine as needed)
    target_user_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    country: Optional[str] = None

    currency: Optional[str] = None
    scope_id_for_limits: Optional[str] = None  # e.g. "BRANCH:LAGOS-1" or "DEPT:TREASURY"


@dataclass
class ReportPack:
    meta: Dict[str, Any]

    executed_trades: List[UserActivityRecord]
    outstanding_trades: List[UserActivityRecord]
    open_positions: List[UserActivityRecord]
    closed_positions: List[UserActivityRecord]

    running_balances_by_currency: Dict[str, Decimal]

    exposure_snapshot: Optional[Dict[str, str]] = None  # stringified decimals for safe export


class ReportPackGenerator:
    def __init__(
        self,
        *,
        ledger: UserActivityLedger,
        users: UserDirectory,
        tracker: TradeExposureTracker,
        limits: InstitutionalLimitController,
    ):
        self.ledger = ledger
        self.users = users
        self.tracker = tracker
        self.limits = limits

    # ─────────────────────────────
    # Permission enforcement
    # ─────────────────────────────
    def _assert_scope_allowed(self, req: ReportPackRequest) -> None:
        requester = self.users.require(req.requesting_user_id)

        # Self reports always allowed
        if req.target_user_id is None or req.target_user_id == req.requesting_user_id:
            return

        # Reporting on others requires supervisor+
        if requester.access_level not in {
            AccessLevel.LEVEL_3_SUPERVISOR,
            AccessLevel.LEVEL_4_ADMIN,
        }:
            raise PermissionError("Insufficient privileges to generate reports for other users")

    # ─────────────────────────────
    # Filtering helpers
    # ─────────────────────────────
    def _in_period(self, r: UserActivityRecord, start: str, end: str) -> bool:
        return start <= r.business_date <= end

    def _matches_scope(self, r: UserActivityRecord, req: ReportPackRequest) -> bool:
        # v1: scope filters use meta tags when present
        if req.target_user_id and r.user_id != req.target_user_id:
            return False

        if req.currency and r.currency and r.currency != req.currency:
            return False

        if req.department and (not r.meta or r.meta.get("department") != req.department):
            return False

        if req.branch and (not r.meta or r.meta.get("branch") != req.branch):
            return False

        if req.country and (not r.meta or r.meta.get("country") != req.country):
            return False

        return True

    # ─────────────────────────────
    # Core generator
    # ─────────────────────────────
    def generate(self, req: ReportPackRequest) -> ReportPack:
        self._assert_scope_allowed(req)

        # Collect filtered records
        records = [
            r for r in self.ledger.all()
            if self._in_period(r, req.start_date, req.end_date)
            and self._matches_scope(r, req)
        ]

        executed = [r for r in records if r.action == "EXECUTE_TRADE" and r.success]
        outstanding = [r for r in records if r.action in {"OPEN_POSITION", "ORDER_SUBMITTED"} and r.success]

        open_pos = [r for r in records if r.action == "OPEN_POSITION" and r.success]
        closed_pos = [r for r in records if r.action == "CLOSE_POSITION" and r.success]

        # Running balances per currency (activity-derived v1)
        balances: Dict[str, Decimal] = {}
        for r in records:
            if r.amount is None or not r.currency:
                continue
            balances.setdefault(r.currency, Decimal("0"))

            if r.action in {"BUY", "CREDIT", "EXECUTE_TRADE", "OPEN_POSITION"}:
                balances[r.currency] += Decimal(str(r.amount))
            elif r.action in {"SELL", "DEBIT", "CLOSE_POSITION"}:
                balances[r.currency] -= Decimal(str(r.amount))

        # Optional exposure snapshot (if limits scope + currency provided)
        exposure_snapshot = None
        if req.scope_id_for_limits and req.currency:
            # Determine which user to snapshot exposure for:
            # - if target_user_id specified, use that
            # - else use requester (self)
            uid = req.target_user_id or req.requesting_user_id

            # We require trader_limit input; v1 assumes "trader_limit" comes from trader limit registry
            # Here we simply read trader max_limit if present; otherwise skip.
            try:
                trader_lim = self.limits.get_trader_limit(uid).max_limit
                snap = self.tracker.trader_snapshot(
                    scope_id=req.scope_id_for_limits,
                    user_id=uid,
                    currency=req.currency,
                    trader_limit=trader_lim,
                    start_date=req.start_date,
                    end_date=req.end_date,
                )
                exposure_snapshot = {
                    "trader_used": str(snap.trader_used),
                    "trader_limit": str(snap.trader_limit),
                    "trader_remaining": str(snap.trader_remaining),
                    "aggregate_used": str(snap.aggregate_used),
                    "institutional_cap": str(snap.institutional_cap),
                    "institutional_remaining": str(snap.institutional_remaining),
                }
            except Exception:
                exposure_snapshot = None

        return ReportPack(
            meta={
                "requested_by": req.requesting_user_id,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "target_user_id": req.target_user_id,
                "department": req.department,
                "branch": req.branch,
                "country": req.country,
                "currency": req.currency,
                "scope_id_for_limits": req.scope_id_for_limits,
            },
            executed_trades=executed,
            outstanding_trades=outstanding,
            open_positions=open_pos,
            closed_positions=closed_pos,
            running_balances_by_currency=balances,
            exposure_snapshot=exposure_snapshot,
        )