from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import replace
from backend.runtime.pilot_broker_evidence import BrokerInstrumentEvidence, validate_broker_preflight_evidence
from backend.runtime.pilot_currency_conversion import VerifiedRateInput


def setup():
    now = datetime.now(timezone.utc)
    inst = BrokerInstrumentEvidence("BROKER", "ACCOUNT", "EUR-TEST", "FX", "EUR", Decimal("1"), now, "instrument-record")
    rate = VerifiedRateInput("EUR", "CAD", Decimal("1.5"), now, "fx-record")
    args = dict(instrument=inst, rate=rate, budget_currency="CAD",
                expected_broker_id="BROKER", expected_account_id="ACCOUNT",
                expected_instrument_id="EUR-TEST", trusted_evidence_ids=frozenset({"instrument-record", "fx-record"}), now=now)
    return args


def test_matching_bound_fresh_evidence_passes_boundary():
    assert validate_broker_preflight_evidence(**setup())


def test_mismatch_broker_account_instrument_and_missing_allowlist_fail():
    for k, v in [("expected_broker_id", "OTHER"), ("expected_account_id", "OTHER"),
                 ("expected_instrument_id", "OTHER"), ("trusted_evidence_ids", frozenset())]:
        kw = setup()
        kw[k] = v
        assert not validate_broker_preflight_evidence(**kw)


def test_stale_future_or_wrong_direction_fx_rejected():
    for kind in ("stale", "future", "wrong"):
        kw = setup()
        rate = kw["rate"]
        if kind == "stale":
            kw["rate"] = replace(rate, observed_at=kw["now"] - timedelta(minutes=1))
        elif kind == "future":
            kw["rate"] = replace(rate, observed_at=kw["now"] + timedelta(seconds=1))
        else:
            kw["rate"] = VerifiedRateInput("CAD", "EUR", Decimal("0.7"), kw["now"], "fx-record")
        assert not validate_broker_preflight_evidence(**kw)


def test_instrument_multiplier_and_evidence_freshness_rejected():
    for modified in ({"contract_multiplier": Decimal("0")},
                     {"observed_at": datetime.now(timezone.utc)-timedelta(minutes=1)},
                     {"evidence_id": "untrusted"}):
        kw = setup()
        kw["instrument"] = replace(kw["instrument"], **modified)
        assert not validate_broker_preflight_evidence(**kw)


def test_no_rate_required_when_quote_matches_budget():
    kw = setup()
    kw["instrument"] = replace(kw["instrument"], quote_currency="CAD")
    kw["rate"] = None
    assert validate_broker_preflight_evidence(**kw)
    kw["rate"] = setup()["rate"]
    assert not validate_broker_preflight_evidence(**kw)
