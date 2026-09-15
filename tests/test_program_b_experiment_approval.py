from datetime import datetime, timedelta, timezone

import pytest

from backend.research.experiment_registry import (
    approval_allows_live_trading,
    approval_allows_shadow_research,
    create_experiment,
    record_research_approval,
)


NOW = datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc)


def experiment():
    return create_experiment(
        experiment_id="exp-001",
        strategy_id="strategy-alpha",
        hypothesis="risk-adjusted expectancy improves under filter X",
        owner_id="researcher-1",
        dataset_id="dataset-001",
        parameters={"lookback": 20, "threshold": "0.7"},
        created_at_utc=NOW,
        code_reference="commit:abc123",
    )


def test_experiment_parameters_are_deterministically_normalized():
    exp = experiment()
    assert exp.parameters == (("lookback", "20"), ("threshold", "0.7"))


def test_experiment_requires_utc():
    with pytest.raises(ValueError):
        create_experiment(
            experiment_id="exp-1",
            strategy_id="s",
            hypothesis="h",
            owner_id="o",
            dataset_id="d",
            parameters={},
            created_at_utc=datetime(2026, 9, 15, 2, 0),
            code_reference="commit:x",
        )


def test_authorized_reviewer_can_approve_shadow_research():
    approval = record_research_approval(
        experiment(),
        approval_id="approval-1",
        approver_id="reviewer-1",
        approver_role="RESEARCH_REVIEWER",
        approved_at_utc=NOW + timedelta(minutes=5),
        decision="APPROVED_SHADOW",
        rationale="evidence package reviewed",
    )
    assert approval_allows_shadow_research(approval) is True
    assert approval_allows_live_trading(approval) is False


def test_unapproved_decision_does_not_allow_shadow():
    approval = record_research_approval(
        experiment(),
        approval_id="approval-1",
        approver_id="reviewer-1",
        approver_role="RISK_REVIEWER",
        approved_at_utc=NOW + timedelta(minutes=5),
        decision="CHANGES_REQUIRED",
        rationale="more out-of-sample evidence required",
    )
    assert approval_allows_shadow_research(approval) is False


def test_unauthorized_role_fails_closed():
    with pytest.raises(ValueError, match="not authorized"):
        record_research_approval(
            experiment(),
            approval_id="approval-1",
            approver_id="reviewer-1",
            approver_role="TRADER",
            approved_at_utc=NOW + timedelta(minutes=5),
            decision="APPROVED_SHADOW",
            rationale="attempt",
        )


def test_approval_cannot_predate_experiment():
    with pytest.raises(ValueError, match="predate"):
        record_research_approval(
            experiment(),
            approval_id="approval-1",
            approver_id="reviewer-1",
            approver_role="ADMIN",
            approved_at_utc=NOW - timedelta(minutes=1),
            decision="APPROVED_SHADOW",
            rationale="invalid time",
        )


def test_research_approval_can_never_authorize_live_trading():
    assert approval_allows_live_trading(None) is False
    approval = record_research_approval(
        experiment(),
        approval_id="approval-1",
        approver_id="reviewer-1",
        approver_role="ADMIN",
        approved_at_utc=NOW + timedelta(minutes=1),
        decision="APPROVED_SHADOW",
        rationale="approved for research",
    )
    assert approval_allows_live_trading(approval) is False
