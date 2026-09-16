import json

import pytest
from fastapi import HTTPException

from backend.app.reporting.export_service import export_payload
from dashboard.runtime.report_export_router import create_report_export_router


def test_export_service_supports_all_required_formats():
    payload = {"account": {"cash": 100, "status": "OK"}}

    json_artifact = export_payload(
        title="Test",
        payload=payload,
        format_name="json",
        filename_stem="test",
    )
    assert json.loads(json_artifact.content)["account"]["cash"] == 100

    csv_artifact = export_payload(
        title="Test",
        payload=payload,
        format_name="csv",
        filename_stem="test",
    )
    assert "account.cash" in csv_artifact.content

    html_artifact = export_payload(
        title="Test",
        payload=payload,
        format_name="html",
        filename_stem="test",
    )
    assert "<h1>Test</h1>" in html_artifact.content
    assert "account.cash" in html_artifact.content

    text_artifact = export_payload(
        title="Test",
        payload=payload,
        format_name="text",
        filename_stem="test",
    )
    assert "account.cash: 100" in text_artifact.content


def test_export_service_rejects_unknown_format():
    with pytest.raises(ValueError, match="format must be"):
        export_payload(
            title="Test",
            payload={},
            format_name="pdf",
            filename_stem="test",
        )


def test_report_export_router_is_get_only():
    router = create_report_export_router()
    routes = {
        getattr(route, "path", ""): set(
            getattr(route, "methods", set()) or set()
        )
        for route in router.routes
    }
    assert routes["/api/v1/report-export"] == {"GET"}
