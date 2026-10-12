from datetime import datetime, timezone
from decimal import Decimal
import pytest
from backend.runtime.pilot_broker_evidence import BrokerInstrumentEvidence
from backend.runtime.pilot_currency_conversion import VerifiedRateInput
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger
from backend.runtime.governed_paper_route import submit_governed_paper_order, GovernedPaperRouteBlocked


def setup(tmp_path, broker):
    now = datetime.now(timezone.utc)
    inst = BrokerInstrumentEvidence(broker, "PAPER-ACCOUNT", "TEST-INSTRUMENT", "FX" if broker == "OANDA_PAPER" else "FUTURES", "USD", Decimal("1"), now, "instrument-evidence")
    rate = VerifiedRateInput("USD", "CAD", Decimal("1.25"), now, "rate-evidence")
    ledger = PilotExposureReservationLedger(tmp_path / "paper.sqlite3")
    return dict(
        paper_broker=broker, ledger=ledger, parent_id="P1", child_id="C1",
        instrument=inst, quote_rate=rate,
        trusted_evidence_ids=frozenset({"instrument-evidence", "rate-evidence"}),
        risk_gross_quote="5", risk_cash_quote="5", risk_max_loss_quote="5", fee_quote="0.1",
        quantity=1.0, side="BUY", limit_price=5.0,
        decision_envelope={"final_decision": "ALLOW"}, now=now,
    )


@pytest.mark.parametrize("broker", ["IBKR_PAPER", "OANDA_PAPER"])
def test_governed_paper_routes_only(broker, tmp_path):
    a = setup(tmp_path, broker)
    result = submit_governed_paper_order(**a)
    assert result["status"] == "FILLED"
    assert result["broker"] == broker
    assert a["ledger"].snapshot()[0]["state"] == "COMMITTED"
    with pytest.raises(GovernedPaperRouteBlocked):
        submit_governed_paper_order(**a)


def test_live_broker_refused(tmp_path):
    args = setup(tmp_path, "OANDA_PAPER")
    args["paper_broker"] = "OANDA_LIVE"
    with pytest.raises(GovernedPaperRouteBlocked):
        submit_governed_paper_order(**args)
    assert args["ledger"].snapshot() == []


def test_no_allow_envelope_refused(tmp_path):
    args = setup(tmp_path, "IBKR_PAPER")
    args["decision_envelope"] = {"final_decision": "DENY"}
    with pytest.raises(GovernedPaperRouteBlocked):
        submit_governed_paper_order(**args)
    assert args["ledger"].snapshot() == []


def test_oversized_risk_refused(tmp_path):
    args = setup(tmp_path, "IBKR_PAPER")
    args["risk_gross_quote"] = "100"
    with pytest.raises(GovernedPaperRouteBlocked):
        submit_governed_paper_order(**args)
    assert args["ledger"].snapshot() == []
