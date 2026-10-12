"""Governed paper-only order path; never connects to a live broker.

A synthetic decision envelope is not enough: require complete risk evidence,
current budget capacity and a final ALLOW decision before paper simulation.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from backend.runtime.pilot_broker_evidence import BrokerInstrumentEvidence, validate_broker_preflight_evidence
from backend.runtime.pilot_currency_conversion import VerifiedRateInput
from backend.runtime.pilot_currency_reservation import reserve_converted_pilot_exposure
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger
from engine.brokers.ibkr_paper_broker import IbkrPaperBroker
from engine.brokers.oanda_paper_broker import OandaPaperBroker


class GovernedPaperRouteBlocked(RuntimeError):
    pass


_PAPER_BROKERS = {"IBKR_PAPER": IbkrPaperBroker, "OANDA_PAPER": OandaPaperBroker}


def submit_governed_paper_order(
    *,
    paper_broker: str,
    ledger: PilotExposureReservationLedger,
    parent_id: str,
    child_id: str,
    instrument: BrokerInstrumentEvidence,
    quote_rate: VerifiedRateInput | None,
    trusted_evidence_ids: frozenset[str],
    risk_gross_quote: str,
    risk_cash_quote: str,
    risk_max_loss_quote: str,
    fee_quote: str,
    quantity: float,
    side: str,
    limit_price: float,
    decision_envelope: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Paper execution demonstration: not a production risk engine or approval."""
    if paper_broker not in _PAPER_BROKERS or instrument.broker_id != paper_broker:
        raise GovernedPaperRouteBlocked("PAPER_BROKER_NOT_ALLOWED")
    if type(decision_envelope) is not dict or decision_envelope.get("final_decision") != "ALLOW":
        raise GovernedPaperRouteBlocked("DECISION_NOT_ALLOW")
    # SECURITY: no trusted authorization issuer is wired in this candidate.
    # An arbitrary caller-supplied ALLOW string cannot prove R7, AntiBleed,
    # RiskGovernor, the kill switch, order binding or replay protection.
    # Block even paper submission until independently verified authority exists.
    raise GovernedPaperRouteBlocked("PAPER_AUTHORITY_PROVENANCE_UNVERIFIED")
    if side not in ("BUY", "SELL") or type(quantity) not in (int, float) or type(limit_price) not in (int, float):
        raise GovernedPaperRouteBlocked("INVALID_ORDER")
    import math
    if not math.isfinite(quantity) or quantity <= 0 or not math.isfinite(limit_price) or limit_price <= 0:
        raise GovernedPaperRouteBlocked("INVALID_ORDER")
    if not validate_broker_preflight_evidence(
        instrument=instrument, rate=quote_rate, budget_currency="CAD",
        expected_broker_id=paper_broker, expected_account_id=instrument.account_id,
        expected_instrument_id=instrument.instrument_id,
        trusted_evidence_ids=trusted_evidence_ids, now=now,
    ):
        raise GovernedPaperRouteBlocked("BROKER_EVIDENCE_INVALID")
    reservation = reserve_converted_pilot_exposure(
        ledger, parent_id=parent_id, child_id=child_id,
        source_currency=instrument.quote_currency,
        gross_notional=risk_gross_quote, cash_commitment=risk_cash_quote,
        maximum_loss=risk_max_loss_quote, fees=fee_quote,
        risk_bounded=True, instrument_verified=True, rate_provenance_verified=True,
        rate=quote_rate, now=now,
    )
    if reservation.decision is None or not reservation.decision.approved:
        raise GovernedPaperRouteBlocked("PILOT_RESERVATION_DENIED")
    broker = _PAPER_BROKERS[paper_broker]()
    try:
        result = broker.submit_order(
            instrument=instrument.instrument_id, side=side, quantity=quantity,
            order_type="LIMIT", price=limit_price, decision_envelope=decision_envelope,
        )
    except Exception as exc:
        # A blocked or errored paper submission must NOT release a reservation
        # without reconciliation: distinguish unknown state from confirmed no-fill.
        raise GovernedPaperRouteBlocked("PAPER_SUBMISSION_FAILED_RECONCILE") from exc
    if not ledger.transition(child_id, from_state="OPEN", to_state="COMMITTED"):
        raise GovernedPaperRouteBlocked("PAPER_LEDGER_COMMIT_FAILED_RECONCILE")
    return dict(result)
