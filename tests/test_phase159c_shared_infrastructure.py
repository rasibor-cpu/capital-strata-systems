from __future__ import annotations

import math
from backend.common.status_types import GREEN, AMBER, RED, UNKNOWN, NOT_READY, READY, PASS, FAIL
from backend.common.constants import (
    CONFIDENCE_DEFAULT,
    CONFIDENCE_WARNING_THRESHOLD,
    CONFIDENCE_CRITICAL_THRESHOLD,
    PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD,
    PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD,
)
from backend.common.numeric_utils import safe_float, safe_int, safe_bool, clamp, normalize_percentage
from backend.common.advisory_payload import AdvisoryPayloadBuilder
from backend.portfolio.utils import safe_float as port_safe_float, clamp as port_clamp, advisory_response as port_advisory_response


def test_phase159c_status_constants() -> None:
    assert GREEN == "GREEN"
    assert AMBER == "AMBER"
    assert RED == "RED"
    assert UNKNOWN == "UNKNOWN"
    assert NOT_READY == "NOT_READY"
    assert READY == "READY"
    assert PASS == "PASS"
    assert FAIL == "FAIL"


def test_phase159c_constants() -> None:
    assert CONFIDENCE_DEFAULT == 80.0
    assert CONFIDENCE_WARNING_THRESHOLD == 70.0
    assert CONFIDENCE_CRITICAL_THRESHOLD == 60.0
    assert PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD == 8.0
    assert PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD == 50.0


def test_phase159c_numeric_utils() -> None:
    # safe_float
    assert safe_float("123.45") == 123.45
    assert safe_float("abc", default=7.0) == 7.0
    assert safe_float(None, default=3.0) == 3.0
    assert safe_float(float("inf"), default=-1.0) == -1.0
    assert safe_float(float("nan"), default=-2.0) == -2.0

    # safe_int
    assert safe_int("42") == 42
    assert safe_int("42.7") == 42
    assert safe_int("abc", default=9) == 9

    # safe_bool
    assert safe_bool(True) is True
    assert safe_bool("true") is True
    assert safe_bool("YES") is True
    assert safe_bool("1") is True
    assert safe_bool("on") is True
    assert safe_bool("ok") is True
    assert safe_bool(False) is False
    assert safe_bool("false") is False
    assert safe_bool("0") is False
    assert safe_bool("none") is False
    assert safe_bool("abc", default=True) is True

    # clamp
    assert clamp(50, 0, 100) == 50.0
    assert clamp(150, 0, 100) == 100.0
    assert clamp(-50, 0, 100) == 0.0

    # normalize_percentage
    assert normalize_percentage(85.5) == 85.5
    assert normalize_percentage(120.0) == 100.0
    assert normalize_percentage(-10.0) == 0.0


def test_phase159c_advisory_payload_builder() -> None:
    # Basic construction
    payload = AdvisoryPayloadBuilder.build(
        "OK",
        live_trading_blocked=True,
        broker_execution_armed=False,
        custom_metric=99.9,
    )
    
    assert payload["status"] == "OK"
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False
    assert payload["custom_metric"] == 99.9

    # Anti-override safety check
    override_attempt = AdvisoryPayloadBuilder.build(
        "OK",
        advisory_only=False,
        execution_allowed=True,
        live_trading_blocked=False,
        broker_execution_armed=True,
    )

    assert override_attempt["advisory_only"] is True
    assert override_attempt["execution_allowed"] is False
    assert override_attempt["live_trading_blocked"] is True
    assert override_attempt["broker_execution_armed"] is False


def test_phase159c_behavioral_compatibility_retro_checks() -> None:
    # Ensure portfolio utils exports match exactly their previous behavior
    assert port_safe_float("12.5") == 12.5
    assert port_safe_float("invalid", default=1.2) == 1.2
    
    assert port_clamp(15, 0, 10) == 10.0
    
    resp = port_advisory_response("GREEN", some_key="value")
    assert resp["status"] == "GREEN"
    assert resp["advisory_only"] is True
    assert resp["execution_allowed"] is False
    assert resp["some_key"] == "value"
