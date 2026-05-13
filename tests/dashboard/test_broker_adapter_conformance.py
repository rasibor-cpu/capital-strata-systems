from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_broker_adapter_conformance_payload,
)
from dashboard.runtime.broker_adapter_conformance import (
    BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION,
    BROKER_ADAPTER_CONFORMANT,
    BROKER_ADAPTER_PARTIAL,
    certify_broker_adapter_conformance,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from engine.brokers.capabilities import BROKER_CAPABILITIES, validate_order


class NonConformingAdapter:
    name = "BAD_PAPER"

    def submit_order(self, **_kwargs):
        return {"status": "FILLED"}


def test_registered_paper_adapters_are_conformant() -> None:
    payload = get_broker_adapter_conformance_payload()
    brokers = {result["broker"] for result in payload["results"]}
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["payload_version"] == BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION
    assert payload["status"] == BROKER_ADAPTER_CONFORMANT
    assert {"OANDA_PAPER", "ALPACA_PAPER", "IBKR_PAPER", "BINANCE_PAPER"} <= brokers
    assert payload["failed_adapter_count"] == 0
    assert "secret" not in encoded.lower()


def test_capability_registry_covers_existing_paper_adapters() -> None:
    assert {"OANDA_PAPER", "ALPACA_PAPER", "IBKR_PAPER", "BINANCE_PAPER"} <= set(
        BROKER_CAPABILITIES
    )

    validate_order(
        broker_name="IBKR_PAPER",
        instrument="ES",
        order_type="MARKET",
        quantity=1,
        side="BUY",
    )
    validate_order(
        broker_name="BINANCE_PAPER",
        instrument="BTCUSDT",
        order_type="LIMIT",
        quantity=1,
        side="BUY",
    )


def test_conformance_report_fails_closed_for_bad_adapter() -> None:
    report = certify_broker_adapter_conformance({"BAD_PAPER": NonConformingAdapter})
    payload = report.as_dict()
    failed_codes = {
        check["code"]
        for result in payload["results"]
        for check in result["checks"]
        if not check["passed"]
    }

    assert payload["status"] == BROKER_ADAPTER_PARTIAL or payload["failed_adapter_count"] == 1
    assert "adapter_subclasses_base_broker" in failed_codes
    assert "capabilities_registered" in failed_codes
    assert "denied_envelope_refused" in failed_codes


def test_broker_adapter_conformance_api_exposes_read_only_payload() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_broker_adapter_conformance_payload()

    assert "/api/v1/broker-adapter-conformance" in routes
    assert payload["payload_version"] == BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION
    assert payload["status"] == BROKER_ADAPTER_CONFORMANT
