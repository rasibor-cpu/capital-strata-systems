from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.performance_compensation_terms_repository import (
    PerformanceCompensationTermsRepository,
)
from backend.app.persistence.repositories.shadow_compensation_entitlement_repository import (
    ShadowCompensationEntitlementRepository,
)
from backend.commercialization.performance_accounting import (
    PerformanceAccountState,
    PerformanceAccountingTransition,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms,
    ShadowCompensationEntitlement,
    build_shadow_compensation_entitlement,
)


MIGRATION = Path(
    "backend/app/persistence/migrations/sql/"
    "008_performance_compensation.sql"
)


@pytest.fixture
def db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE performance_accounting_transitions (
            trade_id TEXT PRIMARY KEY
        );
        """
    )

    connection.executescript(
        MIGRATION.read_text(encoding="utf-8-sig")
    )

    monkeypatch.setattr(
        base_repository,
        "get_connection",
        lambda: connection,
    )

    yield connection

    connection.close()


def _terms(
    *,
    terms_id: str = "TERMS-001",
    rate: Decimal = Decimal("0.20"),
    currency: str = "CAD",
    accepted: bool = True,
    evidence_refs: tuple[str, ...] = ("agreement:TERMS-001",),
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
) -> PerformanceCompensationTerms:
    return PerformanceCompensationTerms(
        terms_id=terms_id,
        currency=currency,
        performance_compensation_rate=rate,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        accepted=accepted,
        effective_to=effective_to,
    )


def _transition(
    *,
    trade_id: str = "TRADE-001",
    currency: str = "CAD",
    attributable_realized_pnl: Decimal = Decimal("15"),
    recovered_loss: Decimal = Decimal("10"),
    new_economic_gain: Decimal = Decimal("5"),
    previous_cumulative: Decimal = Decimal("90"),
    previous_hwm: Decimal = Decimal("100"),
    new_cumulative: Decimal = Decimal("105"),
    new_hwm: Decimal = Decimal("105"),
) -> PerformanceAccountingTransition:
    previous_state = PerformanceAccountState(
        currency=currency,
        cumulative_attributable_pnl=previous_cumulative,
        high_water_mark=previous_hwm,
        loss_carryforward=max(
            previous_hwm - previous_cumulative,
            Decimal("0"),
        ),
    )
    new_state = PerformanceAccountState(
        currency=currency,
        cumulative_attributable_pnl=new_cumulative,
        high_water_mark=new_hwm,
        loss_carryforward=max(
            new_hwm - new_cumulative,
            Decimal("0"),
        ),
    )
    return PerformanceAccountingTransition(
        trade_id=trade_id,
        previous_state=previous_state,
        new_state=new_state,
        attributable_realized_pnl=attributable_realized_pnl,
        recovered_loss=recovered_loss,
        new_economic_gain=new_economic_gain,
    )


def _create_transition_row(
    connection: sqlite3.Connection,
    trade_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO performance_accounting_transitions (trade_id)
        VALUES (?)
        """,
        (trade_id,),
    )


def _persist_terms(
    terms: PerformanceCompensationTerms | None = None,
) -> PerformanceCompensationTerms:
    terms = terms or _terms()
    PerformanceCompensationTermsRepository().create_terms(terms)
    return terms


def _persist_entitlement(
    connection: sqlite3.Connection,
    *,
    trade_id: str = "TRADE-001",
    terms: PerformanceCompensationTerms | None = None,
) -> ShadowCompensationEntitlement:
    terms = terms or _persist_terms()
    _create_transition_row(connection, trade_id)
    entitlement = build_shadow_compensation_entitlement(
        _transition(trade_id=trade_id),
        terms,
        "2026-09-08T19:00:00Z",
    )
    ShadowCompensationEntitlementRepository().create_entitlement(
        entitlement
    )
    return entitlement


def _terms_from_row(row: dict) -> PerformanceCompensationTerms:
    return PerformanceCompensationTerms(
        terms_id=row["terms_id"],
        currency=row["currency"],
        performance_compensation_rate=Decimal(
            row["performance_compensation_rate"]
        ),
        effective_from=row["effective_from"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        accepted=bool(row["accepted"]),
        effective_to=row["effective_to"],
    )


def _entitlement_from_row(row: dict) -> ShadowCompensationEntitlement:
    return ShadowCompensationEntitlement(
        trade_id=row["trade_id"],
        terms_id=row["terms_id"],
        currency=row["currency"],
        new_economic_gain=Decimal(row["new_economic_gain"]),
        compensation_rate=Decimal(row["compensation_rate"]),
        shadow_compensation_amount=Decimal(
            row["shadow_compensation_amount"]
        ),
        calculation_timestamp=row["calculation_timestamp"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
    )


def test_insert_and_read_compensation_terms(db):
    terms = _terms(effective_to="2026-12-31")
    repo = PerformanceCompensationTermsRepository()
    repo.create_terms(terms)

    row = repo.get_by_terms_id("TERMS-001")

    assert row is not None
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["effective_from"] == "2026-01-01"
    assert row["effective_to"] == "2026-12-31"
    assert row["accepted"] == 1


def test_terms_rate_decimal_serialization_is_exact(db):
    terms = _terms(rate=Decimal("0.2000"))
    repo = PerformanceCompensationTermsRepository()
    repo.create_terms(terms)

    row = repo.get_by_terms_id("TERMS-001")

    assert row is not None
    assert row["performance_compensation_rate"] == "0.2000"
    assert Decimal(row["performance_compensation_rate"]) == Decimal(
        "0.2000"
    )


def test_terms_evidence_json_round_trip(db):
    terms = _terms(
        evidence_refs=(
            "agreement:TERMS-001",
            "acceptance:USER-1",
        )
    )
    repo = PerformanceCompensationTermsRepository()
    repo.create_terms(terms)

    row = repo.get_by_terms_id("TERMS-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["agreement:TERMS-001","acceptance:USER-1"]'
    )
    assert json.loads(row["evidence_refs_json"]) == [
        "agreement:TERMS-001",
        "acceptance:USER-1",
    ]


def test_duplicate_terms_are_rejected(db):
    repo = PerformanceCompensationTermsRepository()
    repo.create_terms(_terms())

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_terms(_terms())


def test_lowercase_currency_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO performance_compensation_terms (
                terms_id,
                currency,
                performance_compensation_rate,
                effective_from,
                evidence_refs_json,
                accepted
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "TERMS-LC",
                "cad",
                "0.20",
                "2026-01-01",
                '["agreement:TERMS-LC"]',
                1,
            ),
        )


def test_missing_required_evidence_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO performance_compensation_terms (
                terms_id,
                currency,
                performance_compensation_rate,
                effective_from,
                evidence_refs_json,
                accepted
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "TERMS-EMPTY",
                "CAD",
                "0.20",
                "2026-01-01",
                "[]",
                1,
            ),
        )


def test_terms_repository_has_no_mutation_api():
    assert not hasattr(
        PerformanceCompensationTermsRepository,
        "update_terms",
    )
    assert not hasattr(
        PerformanceCompensationTermsRepository,
        "delete_terms",
    )
    assert not hasattr(
        PerformanceCompensationTermsRepository,
        "update",
    )
    assert not hasattr(
        PerformanceCompensationTermsRepository,
        "delete",
    )


def test_insert_and_read_shadow_entitlement(db):
    entitlement = _persist_entitlement(db)
    repo = ShadowCompensationEntitlementRepository()
    row = repo.get_by_trade_id("TRADE-001")

    assert row is not None
    assert row["trade_id"] == "TRADE-001"
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["calculation_timestamp"] == "2026-09-08T19:00:00Z"
    assert row["new_economic_gain"] == str(
        entitlement.new_economic_gain
    )


def test_entitlement_decimal_serialization_is_exact(db):
    entitlement = _persist_entitlement(db)
    row = ShadowCompensationEntitlementRepository().get_by_trade_id(
        "TRADE-001"
    )

    assert row is not None
    assert row["new_economic_gain"] == "5"
    assert row["compensation_rate"] == "0.20"
    assert row["shadow_compensation_amount"] == str(
        entitlement.shadow_compensation_amount
    )
    assert Decimal(row["shadow_compensation_amount"]) == Decimal("1")
    assert row["new_economic_gain"] != "15"
    assert Decimal(row["new_economic_gain"]) != Decimal("15")


def test_semantic_example_persists_new_economic_gain_only(db):
    terms = _persist_terms(_terms(rate=Decimal("0.20")))
    _create_transition_row(db, "TRADE-001")
    entitlement = build_shadow_compensation_entitlement(
        _transition(
            attributable_realized_pnl=Decimal("15"),
            recovered_loss=Decimal("10"),
            new_economic_gain=Decimal("5"),
            previous_cumulative=Decimal("90"),
            previous_hwm=Decimal("100"),
            new_cumulative=Decimal("105"),
            new_hwm=Decimal("105"),
        ),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert entitlement.shadow_compensation_amount == Decimal("1")
    assert entitlement.shadow_compensation_amount != Decimal("3")

    ShadowCompensationEntitlementRepository().create_entitlement(
        entitlement
    )
    row = ShadowCompensationEntitlementRepository().get_by_trade_id(
        "TRADE-001"
    )

    assert row is not None
    assert row["new_economic_gain"] == "5"
    assert row["compensation_rate"] == "0.20"
    assert Decimal(row["shadow_compensation_amount"]) == Decimal("1")
    assert row["new_economic_gain"] != "15"


def test_entitlement_rejected_without_terms(db):
    _create_transition_row(db, "TRADE-001")
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        _terms(),
        "2026-09-08T19:00:00Z",
    )

    with pytest.raises(sqlite3.IntegrityError):
        ShadowCompensationEntitlementRepository().create_entitlement(
            entitlement
        )


def test_entitlement_rejected_without_accounting_transition(db):
    _persist_terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(trade_id="MISSING-TRADE"),
        _terms(),
        "2026-09-08T19:00:00Z",
    )

    with pytest.raises(sqlite3.IntegrityError):
        ShadowCompensationEntitlementRepository().create_entitlement(
            entitlement
        )


def test_duplicate_entitlement_is_rejected(db):
    _persist_entitlement(db)

    with pytest.raises(sqlite3.IntegrityError):
        ShadowCompensationEntitlementRepository().create_entitlement(
            build_shadow_compensation_entitlement(
                _transition(),
                _terms(),
                "2026-09-08T20:00:00Z",
            )
        )


def test_entitlement_lookup_and_list_are_deterministic(db):
    terms = _persist_terms()
    _create_transition_row(db, "TRADE-002")
    _create_transition_row(db, "TRADE-001")

    repo = ShadowCompensationEntitlementRepository()
    repo.create_entitlement(
        build_shadow_compensation_entitlement(
            _transition(trade_id="TRADE-002"),
            terms,
            "2026-09-08T19:00:00Z",
        )
    )
    repo.create_entitlement(
        build_shadow_compensation_entitlement(
            _transition(trade_id="TRADE-001"),
            terms,
            "2026-09-08T19:00:00Z",
        )
    )

    assert [
        row["trade_id"]
        for row in repo.get_by_terms_id("TERMS-001")
    ] == ["TRADE-001", "TRADE-002"]
    assert [row["trade_id"] for row in repo.list_all()] == [
        "TRADE-001",
        "TRADE-002",
    ]


def test_entitlement_repository_has_no_mutation_api():
    assert not hasattr(
        ShadowCompensationEntitlementRepository,
        "update_entitlement",
    )
    assert not hasattr(
        ShadowCompensationEntitlementRepository,
        "delete_entitlement",
    )
    assert not hasattr(
        ShadowCompensationEntitlementRepository,
        "update",
    )
    assert not hasattr(
        ShadowCompensationEntitlementRepository,
        "delete",
    )


def test_persisted_objects_have_no_fee_or_money_movement_authority(db):
    entitlement = _persist_entitlement(db)
    terms_row = PerformanceCompensationTermsRepository().get_by_terms_id(
        "TERMS-001"
    )
    entitlement_row = (
        ShadowCompensationEntitlementRepository().get_by_trade_id(
            "TRADE-001"
        )
    )

    assert terms_row is not None
    assert entitlement_row is not None

    persisted_terms = _terms_from_row(terms_row)
    persisted_entitlement = _entitlement_from_row(entitlement_row)

    assert persisted_terms.real_fee_collection_allowed is False
    assert persisted_entitlement.real_fee_collection_allowed is False
    assert persisted_terms.client_funds_deduction_allowed is False
    assert persisted_entitlement.client_funds_deduction_allowed is False
    assert persisted_terms.automatic_debit_allowed is False
    assert persisted_entitlement.automatic_debit_allowed is False
    assert persisted_terms.invoice_settlement_allowed is False
    assert persisted_entitlement.invoice_settlement_allowed is False
    assert persisted_terms.execution_authority is False
    assert persisted_entitlement.execution_authority is False
    assert entitlement.real_fee_collection_allowed is False
