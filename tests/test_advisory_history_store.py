from __future__ import annotations

import os

from backend.portfolio.advisory_history_store import AdvisoryHistoryStore


def test_advisory_history_store_appends_lists_and_summarizes(tmp_path) -> None:
    store = AdvisoryHistoryStore(str(tmp_path))
    first = store.append_decision({"adaptive_recommendation": "MAINTAIN"})
    second = store.append_decision({"adaptive_recommendation": "REDUCE_RISK"})

    recent = store.list_recent(limit=1)
    summary = store.summarize()

    assert first["status"] == "OK"
    assert second["count"] == 2
    assert recent["decisions"][0]["adaptive_recommendation"] == "REDUCE_RISK"
    assert summary["total_decisions"] == 2
    assert summary["recommendation_counts"]["MAINTAIN"] == 1
    assert summary["recommendation_counts"]["REDUCE_RISK"] == 1


def test_advisory_history_store_handles_missing_and_corrupt_json(tmp_path) -> None:
    store = AdvisoryHistoryStore(str(tmp_path))
    assert store.summarize()["total_decisions"] == 0

    os.makedirs(tmp_path, exist_ok=True)
    with open(store.path, "w", encoding="utf-8") as handle:
        handle.write("{bad json")

    assert store.list_recent()["decisions"] == []
    appended = store.append_decision({"recommendation": "PAUSE_NEW_TRADES"})
    assert appended["count"] == 1


def test_advisory_history_store_malformed_decision_is_safe(tmp_path) -> None:
    result = AdvisoryHistoryStore(str(tmp_path)).append_decision("bad")

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["advisory_only"] is True
