from backend.commercialization.commercialization_uat import (
    CommercializationUatResult,
    CommercializationUatScenario,
    REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS,
    UatResultStatus,
    assess_commercialization_uat,
)


def _result(scenario, status=UatResultStatus.PASSED):
    return CommercializationUatResult(
        run_id="UAT-1",
        scenario=scenario,
        status=status,
        executed_at="2026-09-15T21:00:00Z",
        environment_reference="env:production-like",
        evidence_refs=(f"evidence:{scenario.value}",),
    )


def test_all_required_scenarios_must_pass():
    results = tuple(_result(s) for s in REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS)
    assessment = assess_commercialization_uat(results)
    assert assessment.complete is True
    assert assessment.missing_scenarios == ()


def test_missing_scenario_blocks_uat_completion():
    results = tuple(
        _result(s)
        for s in REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS
        if s != CommercializationUatScenario.DISPUTE_REFUND
    )
    assessment = assess_commercialization_uat(results)
    assert assessment.complete is False
    assert CommercializationUatScenario.DISPUTE_REFUND in assessment.missing_scenarios


def test_failed_or_blocked_scenario_blocks_completion():
    results = []
    for scenario in REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS:
        status = (
            UatResultStatus.FAILED
            if scenario == CommercializationUatScenario.FX_CONVERSION
            else UatResultStatus.PASSED
        )
        results.append(_result(scenario, status))
    assessment = assess_commercialization_uat(tuple(results))
    assert assessment.complete is False
    assert CommercializationUatScenario.FX_CONVERSION in assessment.failed_scenarios
