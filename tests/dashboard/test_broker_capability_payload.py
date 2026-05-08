from __future__ import annotations

import json

from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.runtime.payload_validator import FrontendPayloadValidator
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from engine.instruments import CANONICAL_IBKR_PRODUCT_CODES


def test_broker_payload_exposes_capability_fields_without_credentials() -> None:
    payloads = build_smoke_payloads()
    payloads["broker_payload"] = {
        "selected_broker": "IBKR",
        "broker_mode": "paper",
        "connected": True,
        "live_trading_enabled": False,
        "last_heartbeat": "2026-05-08T18:00:00+00:00",
        "api_health": "DEGRADED",
        "reconnect_state": "RETRYING",
        "supported_assets": list(CANONICAL_IBKR_PRODUCT_CODES),
        "account_readiness": "PAPER_READY",
        "missing_credentials": True,
        "latency_ms": 42.5,
        "api_key": "SHOULD_NOT_LEAK",
        "secret": "SHOULD_NOT_LEAK_EITHER",
    }
    state = DashboardHydrationCoordinator().hydrate(**payloads)
    frontend_payload = build_frontend_payload(state)
    broker = frontend_payload["sections"]["broker"]
    encoded = json.dumps(frontend_payload)

    assert FrontendPayloadValidator().validate(frontend_payload) is True
    assert broker["selected_broker"] == "IBKR"
    assert broker["api_health"] == "DEGRADED"
    assert broker["reconnect_state"] == "RETRYING"
    assert broker["account_readiness"] == "PAPER_READY"
    assert broker["missing_credentials"] is True
    assert broker["latency_ms"] == 42.5
    assert set(broker["supported_assets"]) == set(CANONICAL_IBKR_PRODUCT_CODES)
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "SHOULD_NOT_LEAK_EITHER" not in encoded


def test_default_broker_payload_registers_full_ibkr_style_asset_catalog() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    broker = build_frontend_payload(state)["sections"]["broker"]

    assert set(broker["supported_assets"]) == set(CANONICAL_IBKR_PRODUCT_CODES)
    assert broker["api_health"] == "UNKNOWN"
    assert broker["account_readiness"] == "UNKNOWN"
    assert broker["missing_credentials"] is False
