import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.runtime.governed_pilot_profile import PilotConfigurationError
from backend.runtime.pilot_authorization_ledger import (
    PilotAuthorizationLedger, PilotReplayError,
)
from pilot_dual_control_fixtures import (
    RELEASE_SHA, SESSION, EphemeralTestSecretProvider, approvals, profile, registry,
)

PROVIDER = EphemeralTestSecretProvider()


def consume(ledger, p, *, key_registry=None, session_id=SESSION, release=RELEASE_SHA, pair=None, **kw):
    return ledger.consume(
        p, approvals=approvals(p, PROVIDER) if pair is None else pair, key_provider=PROVIDER,
        key_registry=key_registry or registry(), session_id=session_id,
        running_release_sha=release, **kw,
    )


def test_consume_exactly_once(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    receipt = consume(ledger, p)
    assert ledger.receipt_is_recorded(receipt)
    with pytest.raises(PilotReplayError):
        consume(ledger, p)


def test_journal_records_attributable_approvals_without_key_material(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    consume(ledger, p)
    entry = ledger.verify_chain()[-1]
    assert entry["release_sha"] == RELEASE_SHA
    assert [a["role"] for a in entry["approvals"]] == ["PILOT_SPONSOR", "RELEASE_SECURITY_APPROVER"]
    assert {a["key_id"] for a in entry["approvals"]} == {"sponsor-k1", "release-k1"}
    raw = ledger.journal.read_text()
    for key_id in ("sponsor-k1", "release-k1"):
        assert PROVIDER.get_key(key_id).hex() not in raw


def test_restart_cannot_reuse_consumed_approval(tmp_path):
    p = profile()
    consume(PilotAuthorizationLedger(tmp_path), p)
    restarted = PilotAuthorizationLedger(tmp_path)  # new instance == process restart
    with pytest.raises(PilotReplayError):
        consume(restarted, p)


def test_new_session_or_release_cannot_consume(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, session_id="proc-session-2")
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, release="b" * 40)
    assert not ledger.is_claimed(p.approval_id)


def test_single_approval_or_revoked_key_cannot_consume(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, pair=approvals(p, PROVIDER)[:1])
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, key_registry=registry(**{"sponsor-k1": "REVOKED"}))
    assert not ledger.is_claimed(p.approval_id)


def test_revoked_approval_cannot_be_consumed(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    ledger.revoke(p.approval_id, revoked_by="robert-asibor", reason="test")
    with pytest.raises(PilotReplayError):
        consume(ledger, p)


def test_expired_approval_rejected(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    p = profile()
    with pytest.raises(PilotConfigurationError):
        consume(ledger, p, now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert not ledger.is_claimed(p.approval_id)


def test_tampered_journal_fails_closed(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    receipt = consume(ledger, profile(approval_id="a-1"))
    lines = ledger.journal.read_text().splitlines()
    record = json.loads(lines[0])
    record["effective_ceiling_cad"] = "9999.00"
    ledger.journal.write_text(json.dumps(record) + "\n")
    with pytest.raises(PilotReplayError):
        ledger.verify_chain()
    assert not ledger.receipt_is_recorded(receipt)
    with pytest.raises(PilotReplayError):
        consume(ledger, profile(approval_id="a-2"))


def test_forged_receipt_not_recognised(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    receipt = consume(ledger, profile())
    forged = dataclasses.replace(receipt, effective_ceiling_cad="5000.00")
    assert not ledger.receipt_is_recorded(forged)
    assert not ledger.receipt_is_recorded({"entry_hash": receipt.entry_hash})


_RACE = """
import sys
sys.path.insert(0, "tests")
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError
from pilot_dual_control_fixtures import RELEASE_SHA, SESSION, EphemeralTestSecretProvider, approvals, profile, registry
provider = EphemeralTestSecretProvider()
p = profile(approval_id="race-001")
try:
    PilotAuthorizationLedger(sys.argv[1]).consume(
        p, approvals=approvals(p, provider), key_provider=provider, key_registry=registry(),
        session_id=SESSION, running_release_sha=RELEASE_SHA)
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
