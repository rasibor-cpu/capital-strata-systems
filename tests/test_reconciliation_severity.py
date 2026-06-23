from backend.reconciliation.reconciliation_severity import (
    INFO,
    WARNING,
    CRITICAL,
    classify_mismatch_severity,
)


def test_zero_difference_is_info():
    assert classify_mismatch_severity(2, 2) == INFO


def test_one_position_difference_is_warning():
    assert classify_mismatch_severity(2, 1) == WARNING


def test_two_or_more_position_difference_is_critical():
    assert classify_mismatch_severity(4, 1) == CRITICAL


def test_difference_is_absolute():
    assert classify_mismatch_severity(1, 4) == CRITICAL