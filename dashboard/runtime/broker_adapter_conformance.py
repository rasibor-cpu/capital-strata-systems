from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from engine.brokers.alpaca_paper_broker import AlpacaPaperBroker
from engine.brokers.base_broker import BaseBroker
from engine.brokers.binance_paper_broker import BinancePaperBroker
from engine.brokers.capabilities import BROKER_CAPABILITIES
from engine.brokers.ibkr_paper_broker import IbkrPaperBroker
from engine.brokers.oanda_paper_broker import OandaPaperBroker


BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION = "css.broker_adapter_conformance.v1"
BROKER_ADAPTER_CONFORMANT = "BROKER_ADAPTER_CONFORMANT"
BROKER_ADAPTER_PARTIAL = "BROKER_ADAPTER_PARTIAL"
BROKER_ADAPTER_BLOCKED = "BROKER_ADAPTER_BLOCKED"

PAPER_ADAPTERS: Mapping[str, type[BaseBroker]] = {
    "OANDA_PAPER": OandaPaperBroker,
    "ALPACA_PAPER": AlpacaPaperBroker,
    "IBKR_PAPER": IbkrPaperBroker,
    "BINANCE_PAPER": BinancePaperBroker,
}


@dataclass(frozen=True)
class AdapterConformanceCheck:
    code: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class AdapterConformanceResult:
    broker: str
    adapter_class: str
    status: str
    checks: tuple[AdapterConformanceCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "adapter_class": self.adapter_class,
            "status": self.status,
            "checks": [check.as_dict() for check in self.checks],
            "failed_check_count": sum(1 for check in self.checks if not check.passed),
        }


@dataclass(frozen=True)
class BrokerAdapterConformanceReport:
    status: str
    results: tuple[AdapterConformanceResult, ...]
    generated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION,
            "generated_utc": self.generated_utc,
            "status": self.status,
            "adapter_count": len(self.results),
            "failed_adapter_count": sum(
                1 for result in self.results if result.status != BROKER_ADAPTER_CONFORMANT
            ),
            "results": [result.as_dict() for result in self.results],
        }


def certify_broker_adapter_conformance(
    adapters: Mapping[str, type[BaseBroker]] | None = None,
) -> BrokerAdapterConformanceReport:
    adapter_map = adapters or PAPER_ADAPTERS
    results = tuple(
        _certify_adapter(name, adapter_cls)
        for name, adapter_cls in sorted(adapter_map.items())
    )
    return BrokerAdapterConformanceReport(
        status=_report_status(results),
        results=results,
    )


def build_broker_adapter_conformance_payload() -> dict[str, Any]:
    return certify_broker_adapter_conformance().as_dict()


def _certify_adapter(
    broker_name: str,
    adapter_cls: type[BaseBroker],
) -> AdapterConformanceResult:
    checks: list[AdapterConformanceCheck] = []
    capabilities = BROKER_CAPABILITIES.get(broker_name)
    adapter_class_name = getattr(adapter_cls, "__name__", str(adapter_cls))

    _add_check(
        checks,
        "adapter_subclasses_base_broker",
        isinstance(adapter_cls, type) and issubclass(adapter_cls, BaseBroker),
        "error",
        f"{broker_name} adapter must subclass BaseBroker.",
    )
    _add_check(
        checks,
        "capabilities_registered",
        capabilities is not None,
        "error",
        f"{broker_name} must have a BrokerCapabilities entry.",
    )

    if capabilities is not None:
        _add_check(
            checks,
            "capabilities_name_matches_adapter",
            capabilities.name == broker_name,
            "error",
            "BrokerCapabilities.name must match the adapter registry key.",
        )
        _add_check(
            checks,
            "instruments_declared",
            bool(capabilities.instruments),
            "error",
            "Broker capabilities must declare supported instruments.",
        )
        _add_check(
            checks,
            "order_types_declared",
            bool(capabilities.order_types),
            "error",
            "Broker capabilities must declare supported order types.",
        )
        _add_check(
            checks,
            "paper_adapter_marked_paper_only",
            bool(capabilities.paper_only),
            "error",
            "Paper adapters must be marked paper_only in capabilities.",
        )
        _add_check(
            checks,
            "market_order_flag_matches_types",
            ("MARKET" in capabilities.order_types)
            == bool(capabilities.supports_market_orders),
            "error",
            "supports_market_orders must align with order_types.",
        )
        _add_check(
            checks,
            "limit_order_flag_matches_types",
            ("LIMIT" in capabilities.order_types)
            == bool(capabilities.supports_limit_orders),
            "error",
            "supports_limit_orders must align with order_types.",
        )

    _add_check(
        checks,
        "denied_envelope_refused",
        _adapter_refuses_denied_envelope(adapter_cls),
        "error",
        "Adapter must refuse a non-ALLOW decision envelope.",
    )

    status = (
        BROKER_ADAPTER_CONFORMANT
        if all(check.passed for check in checks)
        else BROKER_ADAPTER_BLOCKED
    )
    return AdapterConformanceResult(
        broker=broker_name,
        adapter_class=adapter_class_name,
        status=status,
        checks=tuple(checks),
    )


def _adapter_refuses_denied_envelope(adapter_cls: type[BaseBroker]) -> bool:
    try:
        adapter = adapter_cls()
        adapter.submit_order(
            instrument="CSS_TEST",
            side="BUY",
            quantity=1,
            order_type="MARKET",
            price=1.0,
            decision_envelope={"final_decision": "BLOCK"},
        )
    except Exception:
        return True
    return False


def _report_status(results: tuple[AdapterConformanceResult, ...]) -> str:
    if not results:
        return BROKER_ADAPTER_BLOCKED
    if all(result.status == BROKER_ADAPTER_CONFORMANT for result in results):
        return BROKER_ADAPTER_CONFORMANT
    if any(result.status == BROKER_ADAPTER_CONFORMANT for result in results):
        return BROKER_ADAPTER_PARTIAL
    return BROKER_ADAPTER_BLOCKED


def _add_check(
    checks: list[AdapterConformanceCheck],
    code: str,
    passed: bool,
    severity: str,
    message: str,
) -> None:
    checks.append(
        AdapterConformanceCheck(
            code=code,
            passed=bool(passed),
            severity=severity,
            message=message,
        )
    )


__all__ = [
    "BROKER_ADAPTER_BLOCKED",
    "BROKER_ADAPTER_CONFORMANCE_PAYLOAD_VERSION",
    "BROKER_ADAPTER_CONFORMANT",
    "BROKER_ADAPTER_PARTIAL",
    "BrokerAdapterConformanceReport",
    "AdapterConformanceCheck",
    "AdapterConformanceResult",
    "build_broker_adapter_conformance_payload",
    "certify_broker_adapter_conformance",
]
