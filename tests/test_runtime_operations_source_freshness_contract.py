from __future__ import annotations

from dashboard.mission_control.pages.runtime_operations import render


def test_runtime_operations_exposes_stale_authority_diagnostics():
    state = {
        "runtime": {
            "runtime_status": "OFFLINE",
            "heartbeat_status": "STALE",
            "runtime_mode": "DISABLED",
            "engine_mode": "UNAVAILABLE",
            "cycle": "UNAVAILABLE",
            "heartbeat": "2026-09-25T05:02:58Z",
            "source": "RUNTIME_ARTIFACT",
            "selected_source": "RUNTIME_ARTIFACT",
            "authoritative_source": "RUNTIME_ARTIFACT",
            "fallback_source": "UNAVAILABLE",
            "available_sources": ["RUNTIME_ARTIFACT"],
            "source_freshness": "STALE",
            "source_confidence": "LOW",
            "source_status": "AMBER",
            "source_disagreement": False,
            "supervisor_state": "STOPPED",
            "heartbeat_age_seconds": 1000,
            "subsystem_health": {},
            "controls": {"restart": "DISABLED_MC001", "shutdown": "DISABLED_MC001"},
        },
        "operations_timeline": {},
        "event_stream": {},
        "system_metrics": {},
        "source_consistency": {},
    }

    html = render(state)
    assert "AUTHORITATIVE RUNTIME EVIDENCE IS STALE OR UNAVAILABLE" in html
    assert "Runtime Source &amp; Freshness" in html or "Runtime Source & Freshness" in html
    assert "RUNTIME_ARTIFACT" in html
    assert "STALE" in html
    assert "LOW" in html
    assert "STOPPED" in html
