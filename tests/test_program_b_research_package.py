from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from backend.research.research_package import build_research_package, package_to_json


NOW = datetime(2026, 9, 15, 2, 30, tzinfo=timezone.utc)


def test_package_is_deterministic_and_hashed():
    sections = {
        "strategy_certification": {"status": "CERTIFIED_SHADOW", "excess_return": Decimal("0.08")},
        "data_quality": {"status": "PASS", "quality_score": 100},
    }
    a = build_research_package(package_id="pkg-1", generated_at_utc=NOW, sections=sections)
    b = build_research_package(package_id="pkg-1", generated_at_utc=NOW, sections=sections)
    assert a == b
    assert len(a["package_sha256"]) == 64


def test_sensitive_fields_are_redacted_recursively():
    package = build_research_package(
        package_id="pkg-1",
        generated_at_utc=NOW,
        sections={
            "broker": {
                "api_key": "must-not-leak",
                "nested": {"refresh_token": "must-not-leak", "safe": "ok"},
            }
        },
    )
    assert package["sections"]["broker"]["api_key"] == "REDACTED"
    assert package["sections"]["broker"]["nested"]["refresh_token"] == "REDACTED"
    assert package["sections"]["broker"]["nested"]["safe"] == "ok"


def test_package_safety_is_fail_closed():
    package = build_research_package(
        package_id="pkg-1",
        generated_at_utc=NOW,
        sections={"certification": {"status": "CERTIFIED_SHADOW"}},
    )
    assert package["status"] == "RESEARCH_ONLY"
    assert package["safety"]["approved_for_live"] is False
    assert package["safety"]["execution_allowed"] is False
    assert package["safety"]["broker_execution_armed"] is False
    assert package["safety"]["money_movement_authorized"] is False
    assert package["safety"]["human_approval_required"] is True


def test_non_utc_package_time_fails_closed():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_research_package(
            package_id="pkg-1",
            generated_at_utc=datetime(2026, 9, 15, 2, 30),
            sections={"x": 1},
        )


def test_non_utc_nested_datetime_fails_closed():
    with pytest.raises(ValueError, match="datetimes"):
        build_research_package(
            package_id="pkg-1",
            generated_at_utc=NOW,
            sections={"x": {"when": datetime(2026, 9, 15, 2, 30)}},
        )


def test_nonfinite_decimal_fails_closed():
    with pytest.raises(ValueError, match="non-finite"):
        build_research_package(
            package_id="pkg-1",
            generated_at_utc=NOW,
            sections={"x": Decimal("NaN")},
        )


def test_empty_sections_fail_closed():
    with pytest.raises(ValueError, match="evidence section"):
        build_research_package(package_id="pkg-1", generated_at_utc=NOW, sections={})


def test_json_export_is_valid_and_terminated():
    package = build_research_package(
        package_id="pkg-1",
        generated_at_utc=NOW,
        sections={"benchmark": {"status": "OUTPERFORM"}},
    )
    rendered = package_to_json(package)
    assert rendered.endswith("\n")
    assert json.loads(rendered)["package_id"] == "pkg-1"
