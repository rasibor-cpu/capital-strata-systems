from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.brokers.broker_registry import (
    broker_supports_mode,
    get_adapter,
    get_broker_spec,
    list_supported_brokers,
)


ACCOUNT_METHODS = ("get_account_summary", "get_account_balance", "get_account")
POSITION_METHODS = ("get_open_positions", "get_positions", "get_position_snapshot")
ORDER_VALIDATION_METHODS = ("validate_order_intent", "validate_order", "build_order_request")


@dataclass(frozen=True)
class BrokerAdapterConformanceReport:
    broker: str
    registered: bool
    adapter_available: bool
    paper_mode_supported: bool
    live_mode_supported: bool
    asset_classes_present: bool
    account_snapshot_contract: bool
    position_snapshot_contract: bool
    order_intent_validation_contract: bool

    @property
    def status(self) -> str:
        required = (
            self.registered,
            self.adapter_available,
            self.paper_mode_supported,
            self.asset_classes_present,
            self.account_snapshot_contract,
        )
        return "PASS" if all(required) else "FAIL_CLOSED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": "css.broker_adapter_conformance.v1",
            "broker": self.broker,
            "status": self.status,
            "registered": self.registered,
            "adapter_available": self.adapter_available,
            "paper_mode_supported": self.paper_mode_supported,
            "live_mode_supported": self.live_mode_supported,
            "asset_classes_present": self.asset_classes_present,
            "account_snapshot_contract": self.account_snapshot_contract,
            "position_snapshot_contract": self.position_snapshot_contract,
            "order_intent_validation_contract": self.order_intent_validation_contract,
            "execution_allowed": False,
            "read_only": True,
        }


def certify_broker_adapter_conformance(broker_name: str) -> BrokerAdapterConformanceReport:
    broker = str(broker_name or "").strip().lower()
    try:
        spec = get_broker_spec(broker)
    except Exception:
        return BrokerAdapterConformanceReport(
            broker=broker or "unknown",
            registered=False,
            adapter_available=False,
            paper_mode_supported=False,
            live_mode_supported=False,
            asset_classes_present=False,
            account_snapshot_contract=False,
            position_snapshot_contract=False,
            order_intent_validation_contract=False,
        )

    adapter_cls = None
    try:
        adapter_cls = get_adapter(broker)
    except Exception:
        adapter_cls = None

    return BrokerAdapterConformanceReport(
        broker=broker,
        registered=True,
        adapter_available=adapter_cls is not None,
        paper_mode_supported=broker_supports_mode(broker, "paper"),
        live_mode_supported=broker_supports_mode(broker, "live"),
        asset_classes_present=bool(spec.supported_asset_classes),
        account_snapshot_contract=bool(
            adapter_cls and any(hasattr(adapter_cls, name) for name in ACCOUNT_METHODS)
        ),
        position_snapshot_contract=bool(
            adapter_cls and any(hasattr(adapter_cls, name) for name in POSITION_METHODS)
        ),
        order_intent_validation_contract=bool(
            adapter_cls and any(hasattr(adapter_cls, name) for name in ORDER_VALIDATION_METHODS)
        ),
    )


def build_broker_adapter_conformance_payload() -> dict[str, Any]:
    reports = [certify_broker_adapter_conformance(name).as_dict() for name in list_supported_brokers()]
    return {
        "payload_version": "css.broker_adapter_conformance_collection.v1",
        "status": "PASS" if reports and all(row["status"] == "PASS" for row in reports) else "REVIEW_REQUIRED",
        "reports": reports,
        "execution_allowed": False,
        "read_only": True,
    }


__all__ = [
    "BrokerAdapterConformanceReport",
    "build_broker_adapter_conformance_payload",
    "certify_broker_adapter_conformance",
]
