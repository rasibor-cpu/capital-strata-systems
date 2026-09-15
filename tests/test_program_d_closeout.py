from datetime import datetime, timezone


from backend.operations import (
    AtlasKnowledgeEntry,
    BackupRecoveryEvidence,
    ImprovementItem,
    OperationalIncident,
    ExecutiveCommandInput,
    build_executive_command_snapshot,
    build_improvement_register,
    build_incident_rollup,
    build_program_d_projection,
    build_project_atlas_index,
    summarize_backup_recovery_evidence,
)
from dashboard.runtime.program_d_api import create_program_d_router


NOW = datetime(2026, 9, 15, 18, 30, tzinfo=timezone.utc)


def stable_snapshot():
    return build_executive_command_snapshot(
        ExecutiveCommandInput(
            observed_at_utc=NOW,
            runtime_health="HEALTHY",
            broker_health="HEALTHY",
            data_freshness="HEALTHY",
            governance_status="PASS",
            security_status="PASS",
            reconciliation_status="PASS",
            backup_status="PASS",
            recovery_status="PASS",
            capacity_status="PASS",
        )
    )


def test_backup_recovery_registry_warns_and_preserves_safety():
    result = summarize_backup_recovery_evidence(
        [
            BackupRecoveryEvidence("B1", "BACKUP", "PASS", NOW, "artifact:backup"),
            BackupRecoveryEvidence("R1", "RECOVERY", "WARN", NOW, "artifact:recovery"),
        ]
    )
    assert result["overall_status"] == "WARN"
    assert result["execution_allowed"] is False
    assert result["money_movement_authorized"] is False


def test_incident_rollup_prioritizes_critical_open_incident():
    result = build_incident_rollup(
        [
            OperationalIncident("I1", "SECURITY", "CRITICAL", "OPEN", NOW, "critical issue"),
            OperationalIncident("I2", "GOVERNANCE", "HIGH", "OPEN", NOW, "high issue"),
            OperationalIncident("I3", "RUNTIME", "HIGH", "RESOLVED", NOW, "resolved issue"),
        ]
    )
    assert result["highest_open_severity"] == "CRITICAL"
    assert result["open_incident_count"] == 2
    assert result["attention_required"] is True
    assert result["execution_allowed"] is False


def test_project_atlas_index_is_read_only():
    result = build_project_atlas_index(
        [AtlasKnowledgeEntry("A1", "Security Architecture", "security", "docs/security/CSS_SECURITY_ARCHITECTURE.md")]
    )
    assert result["entry_count"] == 1
    assert result["read_only"] is True
    assert result["execution_allowed"] is False


def test_continuous_improvement_register_tracks_open_items():
    result = build_improvement_register(
        [
            ImprovementItem("C1", "Capacity tuning", "MEDIUM", "QUEUED", "metric:capacity"),
            ImprovementItem("C2", "Close old gap", "LOW", "COMPLETE", "evidence:done"),
        ]
    )
    assert result["total_items"] == 2
    assert result["open_items"] == 1
    assert result["execution_allowed"] is False


def test_program_d_projection_combines_read_only_domains():
    payload = build_program_d_projection(
        stable_snapshot(),
        backup_recovery={"overall_status": "PASS", "items": []},
        incident_rollup={"open_incident_count": 0, "highest_open_severity": "INFO"},
        project_atlas={"entry_count": 1, "entries": [], "read_only": True},
        improvement_register={"total_items": 0, "open_items": 0, "items": []},
    )
    assert payload["executive"]["operating_posture"] == "STABLE"
    assert payload["read_only"] is True
    assert payload["safety"]["execution_allowed"] is False
    assert payload["safety"]["money_movement_authorized"] is False


def test_program_d_api_is_get_only_and_fail_closed():
    router = create_program_d_router()
    matches = [route for route in router.routes if getattr(route, "path", None) == "/api/v1/program-d/executive-command"]
    assert len(matches) == 1
    route = matches[0]
    assert route.methods == {"GET"}

    payload = route.endpoint()
    assert payload["read_only"] is True
    assert payload["safety"]["execution_allowed"] is False
    assert payload["safety"]["live_trading_authorized"] is False
