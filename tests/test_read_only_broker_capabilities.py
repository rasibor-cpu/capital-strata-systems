from backend.app.brokers.read_only_capabilities import (
    get_read_only_broker_candidate, list_read_only_broker_candidates,
)


def test_all_candidates_are_execution_disabled():
    candidates = list_read_only_broker_candidates()
    assert len(candidates) >= 6
    assert all(candidate.execution_allowed is False for candidate in candidates)


def test_questrade_is_not_marked_complete():
    questrade = get_read_only_broker_candidate("questrade")
    assert questrade.account_data_candidate
    assert questrade.integration_status == "integration_incomplete"
