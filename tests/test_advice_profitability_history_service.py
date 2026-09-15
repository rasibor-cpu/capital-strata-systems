from decimal import Decimal
import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.advice_profitability_history_service import (
    AdviceProfitabilityHistoryService,
)
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


REFS = ("evidence:1",)
AT = "2026-09-15T00:00:00Z"


def test_history_reconstructs_advice_level_customer_and_css_economics(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    try:
        service = PersistenceService()
        terms = PerformanceCompensationTerms(
            "TERMS-A", "USD", Decimal("0.20"), AT, REFS, True
        )
        service.performance_compensation_terms.create_terms(terms)

        service.sessions.create_session(
            session_id="SESSION-A",
            status="closed",
            mode="paper",
            broker_name="SIM",
            broker_mode="paper",
            started_at=AT,
        )

        state = initial_performance_account("USD")
        for trade_id, advice_id, pnl in (
            ("T1", "A1", Decimal("-50")),
            ("T2", "A2", Decimal("80")),
        ):
            service.trades.create_trade(
                trade_id=trade_id,
                session_id="SESSION-A",
                broker_name="SIM",
                broker_mode="paper",
                symbol="EURUSD",
                direction="LONG",
                status="closed",
                order_type="MARKET",
                quantity=Decimal("1"),
                filled_quantity=Decimal("1"),
                entry_price=Decimal("1"),
                opened_at=AT,
            )
            service.trade_provenance.create_provenance(
                TradeProvenance(
                    trade_id=trade_id,
                    attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
                    mandate_compliance=MandateCompliance.COMPLIANT,
                    advice_id=advice_id,
                    recommendation_timestamp=AT,
                    acceptance_timestamp=AT,
                    evidence_refs=REFS,
                )
            )
            perf = AttributablePerformance(
                trade_id=trade_id,
                advice_id=advice_id,
                realized_pnl=pnl,
                currency="USD",
                verification_timestamp=AT,
                provenance_evidence_refs=REFS,
                economics_evidence_refs=REFS,
            )
            service.attributable_performance.create_attributable_performance(perf)
            transition = apply_attributable_performance(state, perf)
            service.performance_accounting_transitions.create_transition(transition)
            entitlement = build_shadow_compensation_entitlement(
                transition, terms, AT
            )
            service.shadow_compensation_entitlements.create_entitlement(entitlement)
            state = transition.new_state

        history = AdviceProfitabilityHistoryService(service).list_by_terms_id(
            "TERMS-A"
        )

        assert len(history) == 2
        assert history[0].advice_id == "A1"
        assert history[0].css_shadow_fee == Decimal("0.00")
        assert history[1].advice_id == "A2"
        assert history[1].recovered_loss == Decimal("50")
        assert history[1].new_economic_gain == Decimal("30")
        assert history[1].css_shadow_fee == Decimal("6.00")
        assert history[1].customer_retained_after_css_fee == Decimal("74.00")
    finally:
        conn.close()
