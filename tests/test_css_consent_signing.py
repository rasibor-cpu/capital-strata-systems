"""Grok audit A-M2: authenticated consent records, active pointer and external anchoring.

Every attack is first shown to succeed against the UNSIGNED ledger (the original defect), then to
be refused once the run's consent is signed with a key held outside the run root.
All keys here use the SYNTHETIC test-only protect backend (tests/agreement_support.py); the real
Windows DPAPI backend is exercised by the Windows-only test at the end.
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from agreement_support import accept_agreement, test_key_store
from css118_support import KEY
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.cad146 import SIM_USER, Cad146Simulation, SimulationError
from backend.trading_profiles import consent as consent_mod
from backend.trading_profiles import consent_signing
from backend.trading_profiles.consent_signing import ConsentIntegrity, ConsentSigningError, WindowsDpapiBackend
from backend.trading_profiles.copy_engine import CopyTradeEngine

T0 = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_ambient_switches(monkeypatch):
    for var in ("REA_KILL_SWITCH", "CSS_SIM_ENTRY_HALT", "CSS_LIVE_TRADING_ENABLED", "CSS_ENABLE_LIVE_TRADING"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def store(tmp_path):
    return test_key_store(tmp_path / "keys")  # sibling of the run roots, never inside one


def _sim(root, store, presenter=accept_agreement, now=T0, **kw):
    return Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=root.parent / "ops",
                            operator="robert", starting_equity=14_600.0, presenter=presenter, now=now,
                            key_store=store, **kw)


def _signed(track_root, store):
    return cad146.make_engine(track_root, store)


def _unsigned(track_root):
    return CopyTradeEngine(track_root, key_provider=lambda: KEY)


def _status(engine, root):
    return cad146.consent_status(engine, run_id=cad146.read_run_id(root))


def _forge_record(track_root, mutate):
    """What a local writer can do to an unkeyed chain: edit the active record, recompute every
    entry_hash from there on, and repoint the active settings at the forged record."""
    path = track_root / "consent_ledger.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    engine = _unsigned(track_root)
    active = engine.preferences.get(SIM_USER).active
    idx = next(i for i, r in enumerate(rows) if r["entry_hash"] == active.consent_record_hash)
    mutate(rows[idx])
    prev = rows[idx - 1]["entry_hash"] if idx else "GENESIS"
    for r in rows[idx:]:
        r.pop("entry_hash")
        sig = r.pop("signature", None)
        r["prev_hash"] = prev
        r["entry_hash"] = consent_mod._sha(r)
        if sig is not None:
            r["signature"] = sig  # the old signature is all a forger without the key can offer
        prev = r["entry_hash"]
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    engine.preferences.activate(SIM_USER, replace(active, consent_record_hash=rows[idx]["entry_hash"]))
    return rows[idx]


# --------------------------------------------------------------------------------- forgery
def test_defect_unkeyed_chain_lets_a_forged_copy_rebind_consent(tmp_path, store):
    """Grok's repro: copy the run, rewrite run_binding, recompute the chain, repoint: valid."""
    run_a, run_c = tmp_path / "runA", tmp_path / "runC"
    _sim(run_a, store)
    shutil.copytree(run_a, run_c)
    for track in ("track_a", "track_b"):
        _forge_record(run_c / track, lambda r, t=track: r.update(
            run_binding=cad146.run_binding(run_c / t, cad146.read_run_id(run_c))))
    # Defect (unsigned verification, as before A-M2): the forged copy is accepted with no review.
    assert _status(_unsigned(run_c / "track_a"), run_c) == (True, "consent_valid")
    # Fixed: the signed verification refuses it.
    ok, why = _status(_signed(run_c / "track_a", store), run_c)
    assert ok is False and why == "consent_ledger_signature_invalid"
    with pytest.raises(SimulationError, match="consent_activation_required"):
        _sim(run_c, store, presenter=None)


def test_edited_acceptance_in_place_is_refused(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    _forge_record(root / "track_a", lambda r: r.update(operator_id="someone-else"))
    assert _status(_unsigned(root / "track_a"), root) == (True, "consent_valid")  # defect
    assert _status(_signed(root / "track_a", store), root) == (False, "consent_ledger_signature_invalid")


def test_repointing_the_active_settings_to_another_signed_record_is_refused(tmp_path, store, monkeypatch):
    root = tmp_path / "run"
    _sim(root, store)
    first = _signed(root / "track_a", store).preferences.get(SIM_USER).active
    monkeypatch.setattr(cad146, "_desired_policy_hash", lambda: "0" * 64)  # force a second acceptance
    with pytest.raises(SimulationError):
        _sim(root, store, presenter=lambda r: r.decline("declined_by_operator"), now=T0 + timedelta(minutes=5))
    monkeypatch.undo()
    engine = _signed(root / "track_a", store)
    rows = [json.loads(x) for x in (root / "track_a" / "consent_ledger.jsonl").read_text().splitlines()]
    declined = rows[-1]
    assert declined["record_type"] == "DECLINED"
    # A forger repoints the active settings at a different (validly signed) record.
    engine.preferences.activate(SIM_USER, replace(first, consent_record_hash=declined["entry_hash"]))
    assert _status(engine, root)[0] is False
    engine.preferences.activate(SIM_USER, first)
    pointer = json.loads((root / "track_a" / "consent_active_pointer.json").read_text())
    pointer["users"][SIM_USER]["body"]["policy_hash"] = "f" * 64  # tamper with the signed pointer itself
    (root / "track_a" / "consent_active_pointer.json").write_text(json.dumps(pointer))
    assert _status(engine, root) == (False, "consent_active_pointer_signature_invalid")


# --------------------------------------------------------------------------------- anchoring
def test_external_statement_detects_truncation_and_rollback(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    track = root / "track_a"
    snapshot = {p.name: p.read_bytes() for p in track.iterdir() if p.is_file()}
    # Later activity appends records and checkpoints (a decline after a forced re-presentation).
    engine = _signed(track, store)
    engine.consent.ledger.append("NOTE", {"user_id": SIM_USER, "note": "later signed entry"})
    assert _status(_signed(track, store), root) == (True, "consent_valid")
    # Rollback: restore every file in the run root to the earlier snapshot (ledger AND checkpoints).
    for name, data in snapshot.items():
        (track / name).write_bytes(data)
    (track / "consent_anchor_checkpoints.jsonl").write_bytes(snapshot["consent_anchor_checkpoints.jsonl"])
    assert _status(_signed(track, store), root) == (False, "consent_anchor_rolled_back_or_diverged")


def test_missing_external_statement_fails_closed(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    for statement in (store.directory / "anchors").glob("*.json"):
        statement.unlink()
    assert _status(_signed(root / "track_b", store), root) == (False, "consent_anchor_statement_missing")


def test_rewritten_anchor_log_fails_closed(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    log = root / "track_a" / "consent_anchor_checkpoints.jsonl"
    rec = json.loads(log.read_text().splitlines()[-1])
    rec["body"]["ledgers"]["consent"]["lines"] = 0  # pretend nothing was anchored
    log.write_text(json.dumps(rec) + "\n")
    assert _status(_signed(root / "track_a", store), root) == (False, "consent_anchor_digest_mismatch")


# --------------------------------------------------------------------------------- custody
def test_signing_keys_never_live_in_the_run_folder(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    key_id, key = store.signing_key()
    seed = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    needles = (seed, seed.hex().encode(), base64.b64encode(seed))
    for path in root.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert not any(n in data for n in needles), f"key material found in {path}"
            assert not path.name.endswith(".dpapi") and path.name != "registry.json"
    assert repr(store).endswith("key_material_redacted=True)") and seed.hex() not in repr(store)


def test_key_store_inside_or_containing_a_run_root_is_refused(tmp_path):
    root = tmp_path / "run"
    with pytest.raises(SimulationError, match="consent_key_dir_overlaps_run_root"):
        _sim(root, test_key_store(root / "keys"))
    with pytest.raises(SimulationError, match="consent_key_dir_overlaps_run_root"):
        _sim(root, test_key_store(root / "track_a" / "keys"))
    with pytest.raises(SimulationError, match="consent_key_dir_overlaps_run_root"):
        _sim(tmp_path / "keys2" / "run", test_key_store(tmp_path / "keys2"))
    assert not (root / "run.json").exists()


def test_account_binding_is_explicit_and_fails_closed(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    other = test_key_store(store.directory, account="OTHERDOMAIN\\mallory")
    with pytest.raises(ConsentSigningError, match="consent_key_account_mismatch"):
        other.signing_key()
    # Editing the registry's account does not help: the protected seed is bound to the real account.
    reg = json.loads(store.registry_path.read_text())
    reg["keys"][0]["account"] = "OTHERDOMAIN\\mallory"
    store.registry_path.write_text(json.dumps(reg))
    with pytest.raises(ConsentSigningError, match="consent_key_unavailable"):
        test_key_store(store.directory, account="OTHERDOMAIN\\mallory").signing_key()


def test_no_key_store_means_no_simulation(tmp_path, monkeypatch):
    def unavailable():
        raise ConsentSigningError("consent_key_store_requires_windows_dpapi")

    monkeypatch.setattr(consent_signing, "default_consent_key_store", unavailable)
    with pytest.raises(SimulationError, match="consent_signing_unavailable"):
        Cad146Simulation(tmp_path / "run", artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                         operator="robert", presenter=accept_agreement, now=T0)
    assert not (tmp_path / "run" / "run.json").exists()


def test_unsigned_acceptance_from_before_signing_needs_reacceptance(tmp_path, store, monkeypatch):
    root = tmp_path / "run"
    monkeypatch.setattr(cad146, "make_engine", lambda r, ks=None: _plain(r))
    _sim(root, store)  # legacy-style run: unsigned acceptance
    monkeypatch.undo()
    calls = []
    _sim(root, store, presenter=lambda r: calls.append(1) or accept_agreement(r), now=T0 + timedelta(hours=1))
    assert calls == [1] and _status(_signed(root / "track_a", store), root) == (True, "consent_valid")


def _plain(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return CopyTradeEngine(root, key_provider=lambda: KEY)


# --------------------------------------------------------------------------------- rotation
def test_rotation_keeps_existing_acceptances_and_revocation_forces_reacceptance(tmp_path, store):
    root = tmp_path / "run"
    _sim(root, store)
    old_id, _ = store.signing_key()
    new_id = store.rotate(reason="test rotation")
    assert new_id != old_id and store.signing_key()[0] == new_id
    assert _status(_signed(root / "track_a", store), root) == (True, "consent_valid")  # retired key verifies
    reg = store.public_registry()
    assert {k["key_id"]: k["status"] for k in reg["keys"]} == {old_id: "RETIRED", new_id: "ACTIVE"}
    assert all("seed" not in json.dumps(k) and "private" not in json.dumps(k) for k in reg["keys"])
    store.revoke(old_id, reason="suspected compromise")
    assert not list(store.directory.glob(f"{old_id}.*"))  # protected seed destroyed
    assert _status(_signed(root / "track_a", store), root)[0] is False
    calls = []
    _sim(root, store, presenter=lambda r: calls.append(1) or accept_agreement(r), now=T0 + timedelta(hours=2))
    assert calls == [1] and _status(_signed(root / "track_a", store), root) == (True, "consent_valid")


def test_router_decision_check_uses_signed_verification(tmp_path, store):
    root = tmp_path / "run"
    sim = _sim(root, store)
    assert sim.track_a.router.engine.consent.verify_active(SIM_USER) == (True, "consent_valid")
    _forge_record(root / "track_a", lambda r: r.update(operator_id="x"))
    ok, why = sim.track_a.router.engine.consent.verify_active(SIM_USER)
    assert ok is False and why == "consent_ledger_signature_invalid"


# --------------------------------------------------------------------------------- DPAPI
@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI is only available on Windows")
def test_windows_dpapi_per_user_roundtrip_and_entropy_binding(tmp_path):
    backend = WindowsDpapiBackend()
    blob = backend.protect(b"synthetic-seed-0123456789abcdef", b"entropy-a")
    assert b"synthetic-seed" not in blob
    assert backend.unprotect(blob, b"entropy-a") == b"synthetic-seed-0123456789abcdef"
    with pytest.raises(ConsentSigningError):
        backend.unprotect(blob, b"entropy-b")
    real = consent_signing.ConsentKeyStore(tmp_path / "keys", backend=backend)
    root = tmp_path / "run"
    _sim(root, real)
    assert _status(_signed(root / "track_a", real), root) == (True, "consent_valid")


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows behaviour")
def test_dpapi_backend_refuses_outside_windows():
    with pytest.raises(ConsentSigningError, match="consent_key_store_requires_windows_dpapi"):
        WindowsDpapiBackend()


def test_integrity_object_reprs_hold_no_key_material(tmp_path, store):
    integrity = ConsentIntegrity(store, tmp_path / "root")
    key_id, key = store.signing_key()
    seed_hex = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    assert seed_hex not in repr(integrity) and seed_hex not in repr(store)


def test_cli_key_commands_never_print_key_material(tmp_path, store, capsys, monkeypatch):
    import importlib.util
    monkeypatch.setattr(consent_signing, "default_consent_key_store", lambda: store)
    spec = importlib.util.spec_from_file_location("css_sim_cli", Path(__file__).resolve().parents[1] / "tools" / "css_sim_cad146.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    key_id, key = store.signing_key()
    seed_hex = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    assert cli.main(["keys", "status"]) == 0
    assert cli.main(["keys", "rotate", "--reason", "test"]) == 0
    assert cli.main(["keys", "export-public", "--out", str(tmp_path / "public.json")]) == 0
    assert cli.main(["keys", "revoke", "--key-id", key_id, "--reason", "test"]) == 0
    out = capsys.readouterr().out + (tmp_path / "public.json").read_text()
    assert seed_hex not in out and key_id in out
