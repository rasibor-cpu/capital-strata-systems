from __future__ import annotations

import logging

from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def test_runtime_logging_hooks_emit_safe_stage_metadata(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    payloads = build_smoke_payloads()
    payloads["account_payload"]["api_key"] = "SHOULD_NOT_LEAK"
    payloads["account_payload"]["secret"] = "SHOULD_NOT_LEAK_EITHER"

    output = DashboardRuntimeBootstrap().run(**payloads)

    messages = "\n".join(record.getMessage() for record in caplog.records)

    assert "CAPITAL STRATA SYSTEMS DASHBOARD" in output
    assert "Dashboard runtime bootstrap started" in messages
    assert "Dashboard hydration coordinator started" in messages
    assert "Dashboard hydration coordinator completed" in messages
    assert "Dashboard state factory builder stage=account" in messages
    assert "Dashboard state factory builder stage=execution_summary" in messages
    assert "Dashboard state factory completed" in messages
    assert "Dashboard renderer stage=account" in messages
    assert "Dashboard renderer stage=diagnostics" in messages
    assert "Dashboard renderer completed" in messages
    assert "SHOULD_NOT_LEAK" not in messages
    assert "SHOULD_NOT_LEAK_EITHER" not in messages
    assert "api_key" not in messages
    assert "secret" not in messages
