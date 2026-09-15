from __future__ import annotations

import json
import os
from pathlib import Path

import backend.app.persistence.db as db


def main() -> int:
    os.environ["CSS_FULL_TEST_MODE"] = "1"

    db_path = Path(
        os.getenv(
            "CSS_FULL_TEST_DB",
            "data/css_full_test_rc.db",
        )
    )
    if db_path.resolve() == db.DEFAULT_DB_PATH.resolve():
        raise RuntimeError(
            "full-test DB must never be the production/default runtime DB"
        )

    db.close_connection()
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    db.DEFAULT_DB_PATH = db_path

    from backend.app.persistence.services.persistence_service import (
        PersistenceService,
    )
    from backend.commercialization.full_test_runner import (
        FullTestReadinessRunner,
    )

    validated_sha = os.getenv(
        "CSS_VALIDATED_COMMIT_SHA",
        os.getenv("GITHUB_SHA", "LOCAL-FULL-TEST"),
    )
    test_count = int(
        os.getenv("CSS_VALIDATED_TEST_COUNT", "0")
    )

    service = PersistenceService()
    report = FullTestReadinessRunner(service).run(
        validated_commit_sha=validated_sha,
        test_count=test_count,
    )

    payload = {
        "ready_for_full_testing": report.ready_for_full_testing,
        "production_commercial_ready": (
            report.production_commercial_ready
        ),
        "uat_complete": report.uat_complete,
        "launch_dossier_complete": (
            report.launch_dossier_complete
        ),
        "sandbox_payment_succeeded": (
            report.sandbox_payment_succeeded
        ),
        "sandbox_notification_succeeded": (
            report.sandbox_notification_succeeded
        ),
        "production_block_reason_codes": list(
            report.production_block_reason_codes
        ),
        "trading_execution_authority": (
            report.trading_execution_authority
        ),
        "broker_execution_authority": (
            report.broker_execution_authority
        ),
        "money_movement_to_external_provider": (
            report.money_movement_to_external_provider
        ),
        "full_test_db": str(db_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    expected = (
        payload["ready_for_full_testing"] is True
        and payload["production_commercial_ready"] is False
        and payload["uat_complete"] is True
        and payload["launch_dossier_complete"] is True
        and payload["sandbox_payment_succeeded"] is True
        and payload["sandbox_notification_succeeded"] is True
        and payload["trading_execution_authority"] is False
        and payload["broker_execution_authority"] is False
        and payload["money_movement_to_external_provider"] is False
        and any(
            "PAYMENT_PROVIDER_NOT_PRODUCTION_ENVIRONMENT" in reason
            for reason in payload[
                "production_block_reason_codes"
            ]
        )
    )
    db.close_connection()
    return 0 if expected else 2


if __name__ == "__main__":
    raise SystemExit(main())
