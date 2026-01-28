from engine.domain.executions import ExecutionReport
from engine.domain.fees import FeeSchedule


class ExecutionCostModel:
    """
    Applies brokerage commission and taxes to an execution report.

    All rates are percentage-based and must come from
    an authorized FeeSchedule.
    """

    @staticmethod
    def apply_fees(
        report: ExecutionReport,
        fee_schedule: FeeSchedule
    ) -> ExecutionReport:

        # Commission and tax calculations (percentage-based)
        commission = report.gross_amount * (fee_schedule.commission_rate_pct / 100.0)
        tax = report.gross_amount * (fee_schedule.tax_rate_pct / 100.0)

        total_fees = commission + tax

        # Net settlement amount (sign-aware)
        if report.side.upper() == "BUY":
            net_amount = report.gross_amount + total_fees
        else:
            net_amount = report.gross_amount - total_fees

        # Populate report
        report.commission_rate_pct = fee_schedule.commission_rate_pct
        report.brokerage_commission = commission

        report.tax_rate_pct = fee_schedule.tax_rate_pct
        report.tax_amount = tax

        report.total_fees_and_taxes = total_fees
        report.net_amount = net_amount

        report.fee_schedule_id = fee_schedule.fee_schedule_id
        report.fee_schedule_version = fee_schedule.version

        return report