import json

import pytest

import backend.app.period_close as period_close
from backend.app.period_snapshot import (
    create_period_snapshot,
    verify_period_snapshot,
)


def setup_function():
    period_close._PERIODS.clear()


def test_month_snapshot_requires_closed_period(tmp_path):
    with pytest.raises(RuntimeError, match="must be CLOSED"):
        create_period_snapshot(
            period_type="MONTH",
            period_value="2026-09",
            created_at="2026-10-01T00:00:00Z",
            created_by="controller",
            journal_digest={"entries": 10, "debits": "100", "credits": "100"},
            gl_balances={"cash": "100"},
            output_dir=tmp_path,
        )


def test_month_snapshot_is_hash_verified_and_printable(tmp_path):
    period_close.close_month(2026, 9, "controller")
    artifact = create_period_snapshot(
        period_type="MONTH",
        period_value="2026-09",
        created_at="2026-10-01T00:00:00Z",
        created_by="controller",
        journal_digest={"entries": 10, "debits": "100", "credits": "100"},
        gl_balances={"cash": "100", "fees": "10"},
        output_dir=tmp_path,
    )

    ok, reason = verify_period_snapshot(
        __import__("pathlib").Path(artifact.snapshot_path)
    )
    assert ok is True
    assert reason == "OK"
    assert artifact.integrity_hash
    assert __import__("pathlib").Path(artifact.printable_path).exists()


def test_year_snapshot_can_include_financial_statements(tmp_path):
    period_close.close_year(2026, "controller")
    artifact = create_period_snapshot(
        period_type="YEAR",
        period_value="2026",
        created_at="2027-01-01T00:00:00Z",
        created_by="controller",
        journal_digest={"entries": 100},
        gl_balances={"assets": "1000", "liabilities": "400"},
        financial_statements={
            "balance_sheet": {"assets": "1000", "liabilities": "400", "equity": "600"},
            "income_statement": {"revenue": "200", "expense": "120", "net_income": "80"},
        },
        output_dir=tmp_path,
    )
    doc = json.loads(
        __import__("pathlib").Path(artifact.snapshot_path).read_text(
            encoding="utf-8"
        )
    )
    assert doc["financial_statements"]["balance_sheet"]["equity"] == "600"


def test_snapshot_tampering_is_detected(tmp_path):
    artifact = create_period_snapshot(
        period_type="DAY",
        period_value="2026-09-16",
        created_at="2026-09-16T23:59:59Z",
        created_by="controller",
        journal_digest={"entries": 4},
        gl_balances={"cash": "50"},
        output_dir=tmp_path,
    )
    path = __import__("pathlib").Path(artifact.snapshot_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["gl_balances"]["cash"] = "5000"
    path.write_text(json.dumps(doc), encoding="utf-8")

    ok, reason = verify_period_snapshot(path)
    assert ok is False
    assert reason == "SNAPSHOT_HASH_MISMATCH"
