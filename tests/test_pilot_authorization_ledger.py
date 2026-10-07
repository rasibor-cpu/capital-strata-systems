import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.runtime.governed_pilot_profile import (
    GovernedPilotProfile, PilotConfigurationError, sign_profile,
)
from backend.runtime.pilot_authorization_ledger import (
    PilotAuthorizationLedger, PilotReplayError,
)

KEY = b"k" * 32
SESSION = "proc-session-1"


def make_profile(approval_id="change-001"):
    now = datetime.now(timezone.utc)
    return GovernedPilotProfile.from_mapping({
        "approval_id": approval_id, "approver_id": "owner-1",
        "scope": "PILOT_PREFLIGHT_ONE_ORDER", "broker_id": "broker-a",
        "account_id": "acct-a", "asset_class": "EQUITY", "instrument": "ABC",
        "currency": "CAD", "max_aggregate_exposure": "20.00",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "session_id": SESSION,
    })


def consume(ledger, p, **kw):
    return ledger.consume(p, signature=sign_profile(p, KEY), signing_key=KEY, session_id=SESSION, **kw)


def test_consume_exactly_once(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = make_profile()
    receipt = consume(ledger, p)
    assert ledger.receipt_is_recorded(receipt)
    with pytest.raises(PilotReplayError):
        consume(ledger, p)


def test_restart_cannot_reuse_consumed_approval(tmp_path):
    p = make_profile()
    consume(PilotAuthorizationLedger(tmp_path), p)
    restarted = PilotAuthorizationLedger(tmp_path)  # new instance == process restart
    with pytest.raises(PilotReplayError):
        consume(restarted, p)


def test_new_session_cannot_consume(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = make_profile()
    with pytest.raises(PilotConfigurationError):
        ledger.consume(p, signature=sign_profile(p, KEY), signing_key=KEY, session_id="proc-session-2")


def test_revoked_approval_cannot_be_consumed(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = make_profile()
    ledger.revoke(p.approval_id, revoked_by="owner-1", reason="test")
    with pytest.raises(PilotReplayError):
        consume(ledger, p)


def test_invalid_signature_or_expiry_rejected(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = make_profile()
    with pytest.raises(PilotConfigurationError):
        ledger.consume(p, signature="0" * 64, signing_key=KEY, session_id=SESSION)
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert not ledger.is_claimed(p.approval_id)


def test_tampered_journal_fails_closed(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    receipt = consume(ledger, make_profile("a-1"))
    lines = ledger.journal.read_text().splitlines()
    record = json.loads(lines[0])
    record["effective_ceiling_cad"] = "9999.00"
    ledger.journal.write_text(json.dumps(record) + "\n")
    with pytest.raises(PilotReplayError):
        ledger.verify_chain()
    assert not ledger.receipt_is_recorded(receipt)
    with pytest.raises(PilotReplayError):
        consume(ledger, make_profile("a-2"))


def test_forged_receipt_not_recognised(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    receipt = consume(ledger, make_profile())
    forged = dataclasses.replace(receipt, effective_ceiling_cad="5000.00")
    assert not ledger.receipt_is_recorded(forged)
    assert not ledger.receipt_is_recorded({"entry_hash": receipt.entry_hash})


_RACE = """
import sys
from datetime import datetime, timedelta, timezone
from backend.runtime.governed_pilot_profile import GovernedPilotProfile, sign_profile
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError
now = datetime.now(timezone.utc)
p = GovernedPilotProfile.from_mapping({
    "approval_id": "race-001", "approver_id": "owner-1", "scope": "PILOT_PREFLIGHT_ONE_ORDER",
    "broker_id": "broker-a", "account_id": "acct-a", "asset_class": "EQUITY", "instrument": "ABC",
    "currency": "CAD", "max_aggregate_exposure": "20.00",
    "issued_at": (now - timedelta(minutes=1)).isoformat(),
    "expires_at": (now + timedelta(minutes=10)).isoformat(), "session_id": "proc-session-1"})
key = b"k" * 32
try:
    PilotAuthorizationLedger(sys.argv[1]).consume(
        p, signature=sign_profile(p, key), signing_key=key, session_id="proc-session-1")
    print("ok")
except PilotReplayError:
    print("replay")
"""


def test_concurrent_processes_consume_once(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    procs = [subprocess.Popen([sys.executable, "-c", _RACE, str(tmp_path)], cwd=repo_root,
                              stdout=subprocess.PIPE, text=True) for _ in range(6)]
    results = sorted(proc.communicate(timeout=60)[0].strip() for proc in procs)
    assert results.count("ok") == 1 and results.count("replay") == 5
    PilotAuthorizationLedger(tmp_path).verify_chain()
