import pytest
from scripts.run_ai_governance_sweep import run_sweep

def test_sweep_executes_successfully():
    """
    Test that the governance sweep completes successfully with structurally valid data.
    """
    report = run_sweep(fail_mode=False)
    assert report.governance_status == "READY"
    assert report.readiness_score == 100
    assert len(report.critical_findings) == 0

def test_sweep_fail_closed_behavior():
    """
    Test that the governance sweep inherently fails closed when provided missing inputs.
    """
    report = run_sweep(fail_mode=True)
    assert report.governance_status == "FAIL_CLOSED"
    assert report.readiness_score == 0
    assert len(report.critical_findings) > 0

def test_sweep_no_execution_authority():
    """
    Test that the script explicitly possesses no execution authority.
    """
    import scripts.run_ai_governance_sweep
    assert not hasattr(scripts.run_ai_governance_sweep, "execute_trade")
    assert not hasattr(scripts.run_ai_governance_sweep, "mutate_file")
    assert not hasattr(scripts.run_ai_governance_sweep, "call_broker")
