"""Governed paper-only order path; never connects to a live broker.

A synthetic decision envelope is not enough: require complete risk evidence,
current budget capacity and a final ALLOW decision before paper simulation.

The original ``submit_governed_paper_order`` remains **unconditionally fail-closed**
(see the raise at ``PAPER_AUTHORITY_PROVENANCE_UNVERIFIED``) until a verified
issuer, key registry, atomic replay ledger, and the complete R7/AntiBleed/
RiskGovernor/kill-switch execution chain exist and are independently reviewed.

``simulate_governed_paper_order`` is a **paper-only simulation** that exercises
that issuer/verifier/reservation boundary with fake broker objects and never
replaces the production route. It is used by isolated tests to prove the
boundary works; it is not a production substitute.

The trusted evaluator integration is **not** complete: the caller supplies the
gate-evaluator callables (``PaperGateEvaluators``), so this module currently
demonstrates signing scaffolding, not a fully wired trusted decision producer.
The production route remains the only authoritative path and stays blocked.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import math
from typing import Any, Mapping
from backend.runtime.pilot_broker_evidence import BrokerInstrumentEvidence, validate_broker_preflight_evidence
from backend.runtime.pilot_currency_conversion import VerifiedRateInput
from backend.runtime.pilot_currency_reservation import reserve_converted_pilot_exposure
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger
from backend.runtime.pilot_paper_authorization import verify_paper_intent_signature
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError
from backend.runtime.paper_authority_issuer import PaperAuthorityIssuer, PaperGateEvaluators, PaperAuthorityIssuerError
from backend.runtime.paper_authority_registry import PaperIssuerRegistry, PaperIssuerRegistryError
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


# ---------------------------------------------------------------------------
# Simulation-only path. Does not replace the production route above.
# ---------------------------------------------------------------------------


_LOCAL_SIMULATION_BROKER_TYPES: set[type] = set()
"""Test-only allow-list of concrete local simulator types.

A test must explicitly register the type of the local simulator before it can
be used by ``simulate_governed_paper_order``. Any other object — including a
real broker adapter — is rejected before any method is invoked.
"""


def register_local_simulation_broker_type(broker_type: type) -> None:
    """Test-only: explicitly allow-list one concrete local simulator type."""
    if not isinstance(broker_type, type):
        raise TypeError("broker_type must be a type")
    _LOCAL_SIMULATION_BROKER_TYPES.add(broker_type)


def clear_local_simulation_broker_types() -> None:
    """Test-only: clear the allow-list."""
    _LOCAL_SIMULATION_BROKER_TYPES.clear()


def _validate_fake_broker(fake_broker: Any) -> None:
    """Reject anything that is not an explicitly allow-listed local simulator.

    A real broker adapter (or any other order-capable object) must be rejected
    **before any method is invoked** on it.
    """
    if fake_broker is None:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_FAKE_BROKER_REQUIRED")
    if type(fake_broker) not in _LOCAL_SIMULATION_BROKER_TYPES:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_BROKER_NOT_LOCAL_SIMULATOR")
    if not hasattr(fake_broker, "submit_order"):
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_BROKER_NOT_LOCAL_SIMULATOR")


def _reconcile_or_reject(ledger: PilotExposureReservationLedger, child_id: str, parent_id: str) -> None:
    """Release the reservation only on a confirmed rejection; otherwise surface.

    A blocked or errored simulation must never silently drop a reservation:
    if the reservation is still OPEN, release it; otherwise leave the state for
    operator reconciliation and log the ambiguity.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        released = ledger.transition(child_id, from_state="OPEN", to_state="RELEASED")
        if not released:
            logger.warning(
                "simulate_governed_paper_order ambiguous reservation state child_id=%s parent_id=%s",
                child_id,
                parent_id,
            )
            raise GovernedPaperRouteBlocked("PAPER_SIMULATION_AMBIGUOUS_STATE")
    except GovernedPaperRouteBlocked:
        raise
    except Exception as exc:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_RECONCILE_ERROR") from exc


def simulate_governed_paper_order(
    *,
    paper_broker: str,
    ledger: PilotExposureReservationLedger,
    authorization_ledger: PilotAuthorizationLedger,
    issuer: PaperAuthorityIssuer,
    issuer_registry: PaperIssuerRegistry,
    issuer_id: str,
    order_request: Mapping[str, Any],
    evaluators: PaperGateEvaluators,
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
    fake_broker: Any | None = None,
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    """Paper-only simulation of the issuer/verifier/reservation boundary.

    This function is additive scaffolding used by isolated tests to exercise
    the trusted-issuer wiring. It does **not** replace
    ``submit_governed_paper_order`` and never grants execution authority.

    The trusted-evaluator integration is **not** complete here: the caller
    supplies ``PaperGateEvaluators``, so this function currently demonstrates
    signing scaffolding (not a fully wired trusted decision producer). The
    production route remains the authoritative path and stays blocked.

    A rejection produces **no reservation and no simulated fill**.
    """
    import logging

    logger = logging.getLogger(__name__)

    # 0) Reject anything that is not an explicitly allow-listed local simulator
    #    BEFORE any method is invoked on it. A real broker adapter must be rejected.
    _validate_fake_broker(fake_broker)

    # 0b) Validate numeric/finite/type of the caller's numeric fields.
    for name in ("quantity", "limit_price", "risk_amount"):
        value = order_request.get(name)
        if type(value) is not str:
            raise GovernedPaperRouteBlocked(f"PAPER_SIMULATION_INVALID_ORDER:{name}_not_canonical_string")
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError):
            raise GovernedPaperRouteBlocked(f"PAPER_SIMULATION_INVALID_ORDER:{name}_not_decimal")
        if not amount.is_finite() or amount <= 0:
            raise GovernedPaperRouteBlocked(f"PAPER_SIMULATION_INVALID_ORDER:{name}_not_positive")

    # 1) The issuer must be enrolled in the pinned registry. Fail closed if not.
    try:
        issuer_public_key = issuer_registry.issuer_public_key(issuer_id)
    except PaperIssuerRegistryError as exc:
        logger.warning("simulate_governed_paper_order issuer not enrolled id=%s", issuer_id)
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_ISSUER_NOT_ENROLLED") from exc

    # 2) The issuer signs a complete intent from internal evaluators only.
    #    This raises PaperAuthorityIssuerError on any missing/failed evaluator.
    #    NOTE: the evaluators are caller-supplied in this scaffolding — this is
    #    not a fully trusted decision producer. See the module docstring.
    try:
        payload, signature = issuer.issue_paper_intent(
            order_request=order_request,
            evaluators=evaluators,
            issued_at=issued_at,
            now_for_nonce=now,
        )
    except PaperAuthorityIssuerError as exc:
        logger.warning(
            "simulate_governed_paper_order issuer denied child_id=%s exc=%s",
            order_request.get("child_id"),
            exc,
        )
        raise GovernedPaperRouteBlocked(f"PAPER_SIMULATION_ISSUER_DENIED:{exc}") from exc

    # 3) Verify the signature against the pinned key. Reuse the existing verifier.
    try:
        from cryptography.hazmat.primitives import serialization

        public_key_bytes = issuer_public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    except Exception as exc:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_ISSUER_KEY_INVALID") from exc

    verification = verify_paper_intent_signature(
        payload,
        signature,
        public_key_bytes,
        expected_candidate_sha=str(order_request.get("candidate_sha", "")),
        expected_broker=str(order_request.get("broker", "")),
        expected_account=str(order_request.get("account", "")),
        expected_instrument=str(order_request.get("instrument", "")),
        expected_child_id=str(order_request.get("child_id", "")),
        now=now,
    )
    if not verification.valid:
        logger.warning(
            "simulate_governed_paper_order signature/binding rejected reason=%s",
            verification.reason,
        )
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_INVALID")

    # 4) Complete request binding. Bind the *submission* arguments (quantity,
    #    limit_price, side, paper_broker, instrument, risk inputs) to the signed
    #    intent, so a caller cannot sign one order/risk and submit another.
    if payload.get("mode") != "PAPER":
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_MODE_MISMATCH")

    try:
        signed_quantity = Decimal(payload["quantity"])
        signed_limit_price = Decimal(payload["limit_price"])
        signed_risk = Decimal(payload["risk_amount"])
    except (KeyError, InvalidOperation, ValueError):
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INVALID_ORDER:signed_decimal")

    if side != str(order_request.get("side", "")):
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:side")
    if not math.isfinite(quantity) or quantity <= 0:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INVALID_ORDER:quantity")
    if not math.isfinite(limit_price) or limit_price <= 0:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INVALID_ORDER:limit_price")
    if Decimal(str(quantity)) != signed_quantity:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:quantity")
    if Decimal(str(limit_price)) != signed_limit_price:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:limit_price")

    # Bind the signed broker/account/instrument to the actual broker evidence.
    if payload.get("broker") != instrument.broker_id:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:broker")
    if payload.get("account") != instrument.account_id:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:account")
    if payload.get("instrument") != instrument.instrument_id:
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_BINDING_MISMATCH:instrument")
    if paper_broker != instrument.broker_id:
        raise GovernedPaperRouteBlocked("PAPER_BROKER_NOT_ALLOWED")

    # Bind the signed risk_amount to the reservation's risk inputs. The signed
    # risk must be derivable from the caller-supplied reservation inputs + the
    # conversion rate (so a caller cannot sign one risk and reserve another).
    try:
        gross = Decimal(risk_gross_quote)
        cash = Decimal(risk_cash_quote)
        max_loss = Decimal(risk_max_loss_quote)
        fees = Decimal(fee_quote)
    except (InvalidOperation, ValueError):
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INVALID_ORDER:risk_decimals")
    for name, v in (("gross", gross), ("cash", cash), ("max_loss", max_loss), ("fees", fees)):
        if not v.is_finite() or v < 0:
            raise GovernedPaperRouteBlocked(f"PAPER_SIMULATION_INVALID_ORDER:{name}")

    if instrument.quote_currency == "CAD":
        computed_cad_risk = max_loss + fees
    else:
        if quote_rate is None:
            raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INVALID_ORDER:no_conversion_rate")
        computed_cad_risk = (max_loss + fees) * quote_rate.quote_per_base
    computed_cad_risk = computed_cad_risk.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    if computed_cad_risk != signed_risk:
        raise GovernedPaperRouteBlocked(
            f"PAPER_SIMULATION_INTENT_BINDING_MISMATCH:risk_amount:{computed_cad_risk}!={signed_risk}"
        )

    # 5) Broker evidence + currency normalization + reservation + one-time consumption.
    #    No reservation or simulated fill happens before every check above passes.
    reservation_created = False
    try:
        if not validate_broker_preflight_evidence(
            instrument=instrument,
            rate=quote_rate,
            budget_currency="CAD",
            expected_broker_id=paper_broker,
            expected_account_id=instrument.account_id,
            expected_instrument_id=instrument.instrument_id,
            trusted_evidence_ids=trusted_evidence_ids,
            now=now,
        ):
            raise GovernedPaperRouteBlocked("BROKER_EVIDENCE_INVALID")
        # One-time consumption of the signed intent (fail closed on replay or
        # tampered ledger). The nonce from the issuer doubles as the
        # authorization ID. NOTE: `_claim` bypasses the ledger's public
        # `consume()` contract; this is a scaffolding limitation, not a
        # production-grade atomic replay boundary.
        try:
            approval_id = f"paper-sim:{payload['child_id']}:{payload['nonce']}"
            authorization_ledger._claim(approval_id, "CONSUMED")
        except PilotReplayError as exc:
            raise GovernedPaperRouteBlocked("PAPER_SIMULATION_INTENT_REPLAYED") from exc

        reservation = reserve_converted_pilot_exposure(
            ledger,
            parent_id=payload["parent_id"],
            child_id=payload["child_id"],
            source_currency=instrument.quote_currency,
            gross_notional=risk_gross_quote,
            cash_commitment=risk_cash_quote,
            maximum_loss=risk_max_loss_quote,
            fees=fee_quote,
            risk_bounded=True,
            instrument_verified=True,
            rate_provenance_verified=True,
            rate=quote_rate,
            now=now,
        )
        # Only mark reservation_created=True if THIS call actually created the
        # reservation (decision.approved is True and the reason indicates a new
        # reservation). A denied reservation (e.g. duplicate child) must not
        # cause cleanup to release an existing OPEN reservation.
        if reservation.decision is None or not reservation.decision.approved:
            if reservation.decision is not None and "DUPLICATE" in reservation.decision.reason:
                raise GovernedPaperRouteBlocked("PILOT_DUPLICATE_CHILD_RESERVATION")
            raise GovernedPaperRouteBlocked("PILOT_RESERVATION_DENIED")
        reservation_created = reservation.decision.reason == "PILOT_RESERVATION_CREATED"
        if not reservation_created:
            # A duplicate child whose reservation already exists must not be
            # silently released by this path.
            raise GovernedPaperRouteBlocked("PILOT_DUPLICATE_CHILD_RESERVATION")

        # 6) Simulated fill via the local simulator only.
        try:
            result = fake_broker.submit_order(
                instrument=payload["instrument"],
                side=payload["side"],
                quantity=quantity,
                order_type="LIMIT",
                price=limit_price,
                decision_envelope=decision_envelope,
            )
        except Exception as exc:
            logger.warning(
                "simulate_governed_paper_order local-simulator submission failed child_id=%s",
                payload.get("child_id"),
            )
            # Outcome UNKNOWN: do NOT release the reservation. The caller must
            # reconcile; a confirmed no-fill is required before any release.
            reservation_created = False  # never release on unknown outcome
            raise GovernedPaperRouteBlocked("PAPER_SUBMISSION_FAILED_RECONCILE") from exc

        if not ledger.transition(payload["child_id"], from_state="OPEN", to_state="COMMITTED"):
            raise GovernedPaperRouteBlocked("PAPER_LEDGER_COMMIT_FAILED_RECONCILE")
        return dict(result)
    except GovernedPaperRouteBlocked as exc:
        # Rejection path: only release a reservation that THIS call created.
        if reservation_created:
            _reconcile_or_reject(ledger, payload["child_id"], payload["parent_id"])
        raise
    except Exception as exc:
        logger.warning(
            "simulate_governed_paper_order unexpected error child_id=%s",
            payload.get("child_id"),
        )
        if reservation_created:
            _reconcile_or_reject(ledger, payload["child_id"], payload["parent_id"])
        raise GovernedPaperRouteBlocked("PAPER_SIMULATION_UNEXPECTED_ERROR") from exc
