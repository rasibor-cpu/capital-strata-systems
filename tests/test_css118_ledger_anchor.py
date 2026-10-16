"""Closeout C6: independently verifiable anchoring of the CSS-118 ledgers (synthetic keys only)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from css118_support import ADMIN_A, ADMIN_B, NOW, TRADER, activate, approve_trader
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.ledger_anchor import ANCHOR_KEY_ENV, AnchorError, LedgerAnchor, env_anchor_key, public_key_b64

ANCHOR_KEY = Ed25519PrivateKey.from_private_bytes(b"\x42" * 32)  # synthetic test key
OTHER_KEY = Ed25519PrivateKey.from_private_bytes(b"\x24" * 32)
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def world(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: b"synthetic-test-mandate-key-0123456789abcdef")
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    approve_trader(engine.trader_registry)
    return engine, LedgerAnchor(tmp_path / "tp", key_provider=lambda: ANCHOR_KEY)


def _pub():
    return public_key_b64(ANCHOR_KEY)


def test_no_key_means_unanchored_never_a_silent_default(world, monkeypatch):
    engine, _ = world
    monkeypatch.delenv(ANCHOR_KEY_ENV, raising=False)
    assert env_anchor_key() is None
    anchor = LedgerAnchor(engine.root)
    with pytest.raises(AnchorError, match="anchor_key_unavailable"):
        anchor.checkpoint(now=NOW)
    assert anchor.verify(_pub()).status == "UNANCHORED"


def test_checkpoint_verifies_and_allows_later_appends(world):
    engine, anchor = world
    statement = anchor.checkpoint(now=NOW)
    assert statement["seq"] == 1 and "signature_b64" in statement
    activate(engine.consent, "u2", "CSS Autonomous Trading", "Safe")  # append after anchoring
    report = anchor.verify(_pub(), external_statement=statement)
    assert report.ok and report.status == "VERIFIED"
    assert report.ledgers["consent"]["unanchored_tail_lines"] == 1
    assert report.ledgers["trader_registry"]["status"] == "VERIFIED"


def test_rewritten_history_is_detected_even_if_rehashed(world):
    engine, anchor = world
    anchor.checkpoint(now=NOW)
    reg = engine.trader_registry
    # attacker rewrites the registry consistently: re-proposes with a wider scope and re-hashes the chain
    for p in (reg.log.path, reg.log.head_path):
        p.unlink()
    reg.propose(trader_id=TRADER, display_name="Synthetic", public_key_b64=public_key_b64(OTHER_KEY),
                asset_classes=["FX", "CRYPTO", "FUTURES", "OPTIONS"], actor_ctx=ADMIN_A, now=NOW)
    reg.approve(TRADER, actor_ctx=ADMIN_B, now=NOW)  # same length as the anchored history
    reg._events()  # the forged chain is internally consistent...
    report = anchor.verify(_pub())
    assert not report.ok and "ledger_anchored_prefix_modified:trader_registry" in report.problems  # ...but not anchored


def test_truncation_detected(world):
    engine, anchor = world
    anchor.checkpoint(now=NOW)
    path = engine.consent.ledger.path
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:-1]))
    assert "ledger_truncated:consent" in anchor.verify(_pub()).problems


def test_forged_checkpoint_without_the_key_is_rejected(world):
    _, anchor = world
    anchor.checkpoint(now=NOW)
    forger = LedgerAnchor(anchor.root, key_provider=lambda: OTHER_KEY)
    forger.checkpoint(now=NOW)  # appended with the wrong key
    problems = anchor.verify(_pub()).problems
    assert "checkpoint_signature_invalid:2" in problems


def test_edited_checkpoint_body_is_rejected(world):
    _, anchor = world
    anchor.checkpoint(now=NOW)
    rec = json.loads(anchor.path.read_text())
    rec["body"]["ledgers"]["consent"]["lines"] = 0
    anchor.path.write_text(json.dumps(rec) + "\n")
    assert "checkpoint_signature_invalid:1" in anchor.verify(_pub()).problems


def test_anchor_log_rollback_detected_with_external_statement(world):
    engine, anchor = world
    anchor.checkpoint(now=NOW)
    activate(engine.consent, "u2", "CSS Autonomous Trading", "Safe")
    latest = anchor.checkpoint(now=NOW)  # published externally
    lines = anchor.path.read_text().splitlines()
    anchor.path.write_text(lines[0] + "\n")  # attacker drops the latest checkpoint
    report = anchor.verify(_pub(), external_statement=latest)
    assert "anchor_log_rolled_back_before_external_statement" in report.problems
    anchor.path.unlink()
    assert anchor.verify(_pub(), external_statement=latest).status == "FAILED"


def test_new_checkpoint_refuses_to_bless_a_diverged_ledger(world):
    engine, anchor = world
    anchor.checkpoint(now=NOW)
    path = engine.consent.ledger.path
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:-1]))
    with pytest.raises(AnchorError, match="ledger_diverged_from_previous_checkpoint:consent"):
        anchor.checkpoint(now=NOW)


def test_wrong_public_key_fails(world):
    _, anchor = world
    anchor.checkpoint(now=NOW)
    assert not anchor.verify(public_key_b64(OTHER_KEY)).ok
    assert anchor.verify(None).problems == ["anchor_public_key_required"]


def test_line_ending_conversion_does_not_break_anchoring(world):
    engine, anchor = world
    anchor.checkpoint(now=NOW)
    path = engine.consent.ledger.path
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert anchor.verify(_pub()).ledgers["consent"]["status"] == "VERIFIED"


def test_cli_verifier_is_read_only_and_reports(world, tmp_path):
    _, anchor = world
    statement = anchor.checkpoint(now=NOW)
    stmt = tmp_path / "statement.json"
    stmt.write_text(json.dumps(statement))
    before = {p: p.read_bytes() for p in anchor.root.iterdir() if p.is_file()}
    proc = subprocess.run([sys.executable, str(REPO / "tools" / "verify_css_ledger_anchors.py"), "--root", str(anchor.root),
                           "--public-key", _pub(), "--statement", str(stmt)], capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["status"] == "VERIFIED"
    assert {p: p.read_bytes() for p in anchor.root.iterdir() if p.is_file()} == before
