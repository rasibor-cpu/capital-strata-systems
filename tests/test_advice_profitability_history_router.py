"""Regression coverage for the advice-profitability-history router endpoint.

Closes a pre-existing defect found while auditing auth on this route: an
unknown terms_id raised AdviceProfitabilityError unhandled, producing a
generic 500 instead of a clean 404. Also covers malformed terms_id, a known
terms_id with an authorized role, and a known terms_id with an unauthorized
role -- the full matrix the CSS commercial-security closure work asked for.
"""
from __future__ import annotations

from decimal import Decimal
import sqlite3

import pytest
from fastapi import FastAPI

import backend.app.auth.token_store as token_store_module
import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.auth.token_store import TokenStore
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.performance_accounting import (
    apply_attributable_performance,
    initial_performance_account,
)
from backend.commercialization.performance_attribution import AttributablePerformance
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms,
    build_shadow_compensation_entitlement,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)
from dashboard.runtime.client_earnings_router import create_client_earnings_router
from tests.asgi_test_client import AsgiTestClient as TestClient

REFS = ("evidence:1",)
AT = "2026-09-15T00:00:00Z"


@pytest.fixture
def fresh_token_store(monkeypatch):
    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    return store


@pytest.fixture
def seeded_terms_db(monkeypatch):
    """An in-memory persistence DB with one real, complete TERMS-A chain."""
    # check_same_thread=False: FastAPI runs sync endpoints in a worker thread
    # (run_in_threadpool), not the thread that created this connection.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    service = PersistenceService()
    terms = PerformanceCompensationTerms("TERMS-A", "USD", Decimal("0.20"), AT, REFS, True)
    service.performance_compensation_terms.create_terms(terms)
    service.sessions.create_session(
        session_id="SESSION-A", status="closed", mode="paper",
        broker_name="SIM", broker_mode="paper", started_at=AT,
    )
    state = initial_performance_account("USD")
    trade_id, advice_id, pnl = "T1", "A1", Decimal("80")
    service.trades.create_trade(
        trade_id=trade_id, session_id="SESSION-A", broker_name="SIM", broker_mode="paper",
        symbol="EURUSD", direction="LONG", status="closed", order_type="MARKET",
        quantity=Decimal("1"), filled_quantity=Decimal("1"), entry_price=Decimal("1"), opened_at=AT,
    )
    service.trade_provenance.create_provenance(
        TradeProvenance(
            trade_id=trade_id, attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
            mandate_compliance=MandateCompliance.COMPLIANT, advice_id=advice_id,
            recommendation_timestamp=AT, acceptance_timestamp=AT, evidence_refs=REFS,
        )
    )
    perf = AttributablePerformance(
        trade_id=trade_id, advice_id=advice_id, realized_pnl=pnl, currency="USD",
        verification_timestamp=AT, provenance_evidence_refs=REFS, economics_evidence_refs=REFS,
    )
    service.attributable_performance.create_attributable_performance(perf)
    transition = apply_attributable_performance(state, perf)
    service.performance_accounting_transitions.create_transition(transition)
    entitlement = build_shadow_compensation_entitlement(transition, terms, AT)
    service.shadow_compensation_entitlements.create_entitlement(entitlement)

    yield
    conn.close()


def _client():
    app = FastAPI()
    app.router.routes.extend(create_client_earnings_router().routes)
    return TestClient(app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_unknown_terms_id_returns_404_not_500(fresh_token_store, seeded_terms_db):
    token = fresh_token_store.create_session("10003", ["AUDIT"], minutes=60)
    resp = _client().get(
        "/api/v1/advice-profitability-history?terms_id=NO-SUCH-TERMS",
        headers=_bearer(token),
    )
    assert resp.status_code == 404


def test_malformed_terms_id_returns_404_not_500(fresh_token_store, seeded_terms_db):
    token = fresh_token_store.create_session("10003", ["AUDIT"], minutes=60)
    resp = _client().get(
        "/api/v1/advice-profitability-history?terms_id=%00%20%3B--",
        headers=_bearer(token),
    )
    assert resp.status_code == 404


def test_known_terms_id_with_authorized_role_succeeds(fresh_token_store, seeded_terms_db):
    token = fresh_token_store.create_session("10003", ["AUDIT"], minutes=60)
    resp = _client().get(
        "/api/v1/advice-profitability-history?terms_id=TERMS-A",
        headers=_bearer(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["advice_id"] == "A1"


def test_known_terms_id_with_unauthorized_role_is_denied(fresh_token_store, seeded_terms_db):
    token = fresh_token_store.create_session("some-trader", ["TRADER"], minutes=60)
    resp = _client().get(
        "/api/v1/advice-profitability-history?terms_id=TERMS-A",
        headers=_bearer(token),
    )
    assert resp.status_code == 403


def test_error_detail_does_not_leak_a_stack_trace(fresh_token_store, seeded_terms_db):
    token = fresh_token_store.create_session("10003", ["AUDIT"], minutes=60)
    resp = _client().get(
        "/api/v1/advice-profitability-history?terms_id=NO-SUCH-TERMS",
        headers=_bearer(token),
    )
    body = resp.json()
    assert "Traceback" not in str(body)
    assert "File \"" not in str(body)
