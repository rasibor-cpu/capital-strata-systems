from engine.security.audit_log import AuditLogger
from engine.security.supervisor_alerts import SupervisorAlertService
from engine.security.user_directory import UserDirectory, UserEntitlements
from engine.security.rbac import AccessLevel

from engine.security.country_aggregation_manager import CountryAggregationManager
from engine.security.eod_snapshot_generator import EODSnapshotGenerator
from engine.security.report_exporter import ReportExporter
from engine.security.country_periodic_loop_runner import CountryPeriodicLoopRunner, CountryPeriodicLoopRequest


def main():
    # Minimal wiring for a dry run.
    # NOTE: EODSnapshotGenerator may need additional dependencies in your repo;
    # if so, we will wire them next based on your actual constructor.
    audit = AuditLogger()
    supervisor = SupervisorAlertService(audit=audit)

    users = UserDirectory(audit=audit, supervisor=supervisor)
    users.add_user(
        UserEntitlements(
            user_id="SUPER_ADMIN_01",
            access_level=AccessLevel.LEVEL_4_ADMIN,
            super_admin=True,
            audit_only=False,
        )
    )

    exporter = ReportExporter()

    eod = EODSnapshotGenerator(
        ledger=None,     # wire later
        users=users,     # adjust if constructor differs
        tracker=None,    # wire later
        limits=None,     # wire later
    )

    aggregator = CountryAggregationManager(users=users, eod=eod)

    runner = CountryPeriodicLoopRunner(aggregator=aggregator, exporter=exporter)

    req = CountryPeriodicLoopRequest(
        requesting_user_id="SUPER_ADMIN_01",
        country="NIGERIA",
        start_date="2026-01-01",
        end_date="2026-01-03",
        branches=["BRANCH:LAGOS-1", "BRANCH:ABUJA-1"],
        currency="NGN",
        scope_id_for_limits="COUNTRY:NIGERIA",
        output_dir="artifacts",
    )

    runner.run(req)
    print("DONE: country periodic packs exported into artifacts/country_periodic/NIGERIA/")


if __name__ == "__main__":
    main()