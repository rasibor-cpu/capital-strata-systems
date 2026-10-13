"""CSS-062 independent security acceptance review — negative regression tests.

Each test below reproduces a defect found during independent review of PR #109
at head bc7d59719f5e4c65e3a75314ef2efd5daaa8834c and pins the fix.

Tests marked ``xfail(strict=True)`` assert the SECURE behaviour for findings
that are deliberately NOT fixed in this PR (they need an owner design decision
or owner-provisioned credentials). They fail today by design; if someone fixes
the underlying gap they will XPASS, which ``strict=True`` turns into a failure
so the acceptance matrix gets updated rather than silently going stale.

Simulation only. No broker, no live trading, no production keys.
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime import governed_paper_route
from backend.runtime.pilot_coordination_ledger import (
    AuthoritativePilotCoordinationLedger,
    CoordinationReceipt,
    LocalSimulatorOutcomeEvidence,
)
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger
from backend.runtime.trusted_governed_paper_route import (
    TrustedSimulationBlocked,
    simulate_trusted_governed_paper_order,
)
from backend.runtime.trusted_paper_authority import (
    AuthenticatedTrustRegistry,
    TrustedPaperAuthority,
)
from backend.runtime.trusted_risk_evaluators import TrustedRiskEvaluators
from tests.test_trusted_governed_paper_route import PAPER_ROUTE_AUDIENCE, _order_context

ISSUER_ID = "css062-review-issuer"
CANDIDATE_SHA = "c" * 40


# ------------------------------------------------------------------ fixtures
@pytest.fixture
def ledger(tmp_path: Path) -> AuthoritativePilotCoordinationLedger:
    return AuthoritativePilotCoordinationLedger(
        tmp_path / "coordination.db", config=DEFAULT_ORDER_LIMIT_CONFIG
    )


@pytest.fixture
def authority(monkeypatch) -> TrustedPaperAuthority:
    # Test-generated ephemeral key: NOT an owner credential, never persisted.
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(
        "backend.runtime.trusted_paper_authority.compute_current_checkout_sha",
        lambda root: CANDIDATE_SHA,
    )
    registry = AuthenticatedTrustRegistry(
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        public_key_hex=key.public_key().public_bytes_raw().hex(),
        private_key=key,
    )
    return TrustedPaperAuthority(registry=registry, evaluators=TrustedRiskEvaluators())


def _reserve(ledger, approval_id, nonce, child_id, cad="10.00", parent_id="p1") -> CoordinationReceipt:
    return ledger.atomic_consume_and_reserve(
        approval_id=approval_id,
        nonce=nonce,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        parent_id=parent_id,
        child_id=child_id,
        proposed_child_cad=cad,
        estimated_fees_cad="0.00",
    )


def _evidence(outcome: str, child_id: str = "c1") -> LocalSimulatorOutcomeEvidence:
    return LocalSimulatorOutcomeEvidence(
        outcome=outcome, simulator_instance_id="sim-review", evidence_hash="h", child_id=child_id
    )


def _sim(ledger, authority, *, approval_id="A1", nonce="n1", order_context=None, evidence=None):
    return simulate_trusted_governed_paper_order(
        ledger=ledger,
        trusted_authority=authority,
        approval_id=approval_id,
        nonce=nonce,
        order_context=order_context if order_context is not None else _order_context(),
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        simulator_evidence=evidence,
    )


# ====================================== Gate 5: outcome / transition binding
def test_fill_evidence_cannot_release_capacity(ledger):
    """R-1: a confirmed FILL must never free CAD capacity."""
    assert _reserve(ledger, "A1", "n1", "c1").success
    assert ledger.release_reservation(
        child_id="c1", reason="x", confirmed_by_simulator=_evidence("confirmed_fill")
    ) is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_no_fill_evidence_cannot_commit(ledger):
    assert _reserve(ledger, "A1", "n1", "c1").success
    assert ledger.commit_reservation(
        child_id="c1", confirmed_by_simulator=_evidence("confirmed_no_fill")
    ) is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


@pytest.mark.parametrize(
    "forged",
    [
        SimpleNamespace(verified_outcome=lambda: "confirmed_no_fill", child_id="c1"),
        {"outcome": "confirmed_no_fill", "child_id": "c1"},
        "confirmed_no_fill",
    ],
)
def test_duck_typed_evidence_rejected(ledger, forged):
    """R-2: only the exact evidence type is accepted."""
    assert _reserve(ledger, "A1", "n1", "c1").success
    assert ledger.release_reservation(child_id="c1", reason="x", confirmed_by_simulator=forged) is False
    assert ledger.commit_reservation(child_id="c1", confirmed_by_simulator=forged) is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_evidence_subclass_rejected(ledger):
    @dataclass(frozen=True)
    class AlwaysNoFill(LocalSimulatorOutcomeEvidence):
        def verified_outcome(self) -> str:  # noqa: D401
            return "confirmed_no_fill"

    assert _reserve(ledger, "A1", "n1", "c1").success
    ev = AlwaysNoFill("garbage", "sim", "h", "c1")
    assert ledger.release_reservation(child_id="c1", reason="x", confirmed_by_simulator=ev) is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_evidence_for_other_child_rejected(ledger):
    assert _reserve(ledger, "A1", "n1", "c1").success
    assert _reserve(ledger, "A2", "n2", "c2", cad="5.00").success
    assert ledger.release_reservation(
        child_id="c2", reason="x", confirmed_by_simulator=_evidence("confirmed_no_fill", child_id="c1")
    ) is False
    assert ledger.reservation_state(child_id="c2") == "OPEN"


def test_route_mismatched_evidence_preserves_reservation(ledger, authority):
    result = _sim(ledger, authority, evidence=_evidence("confirmed_no_fill", child_id="other"))
    assert result["status"] == "NO_FILL_RELEASE_FAILED"
    assert ledger.reservation_state(child_id="c1") == "OPEN"


# ================================ Gate 5: commit-ack uncertainty / replay
class _BusyOnBegin:
    """Connection proxy whose BEGIN fails (e.g. SQLITE_BUSY after timeout)."""

    def __init__(self, inner):
        self._inner = inner

    def execute(self, sql, *args):
        if sql.strip().upper().startswith("BEGIN"):
            raise sqlite3.OperationalError("database is locked")
        return self._inner.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_replayed_approval_with_sqlite_error_is_not_reported_durable(ledger, monkeypatch):
    """R-3: a replay whose own txn never ran must not be reported as committed."""
    assert _reserve(ledger, "A1", "n1", "c1").success
    real = ledger._connect
    calls = {"n": 0}

    def busy_once():
        # Only the transaction's connection is busy; later reads are healthy,
        # so the durability check really runs against the durable database.
        calls["n"] += 1
        return _BusyOnBegin(real()) if calls["n"] == 1 else real()

    monkeypatch.setattr(ledger, "_connect", busy_once)
    receipt = _reserve(ledger, "A1", "n-other", "c-other")
    monkeypatch.undo()
    assert receipt.success is False
    assert receipt.reason.startswith("COORDINATION_SQLITE_ERROR")
    assert ledger.reservation_state(child_id="c-other") is None


def test_route_ack_uncertain_preserves_reservation_and_ignores_outcome(ledger, authority, monkeypatch):
    """R-3b: ACK-uncertain (success=True) must not fall through to release/commit."""
    real_atomic = ledger.atomic_consume_and_reserve

    def ack_uncertain(**kwargs):
        r = real_atomic(**kwargs)
        assert r.success
        return CoordinationReceipt(
            True, "COORDINATION_COMMIT_ACK_UNCERTAIN", r.approval_id, r.nonce,
            r.child_id, r.reserved_cad, r.transaction_id,
        )

    monkeypatch.setattr(ledger, "atomic_consume_and_reserve", ack_uncertain)
    result = _sim(ledger, authority, evidence=_evidence("confirmed_no_fill"))
    assert result["status"] == "COMMIT_ACK_UNCERTAIN_RECONCILED"
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_corrupt_stored_amount_fails_closed_with_receipt(ledger):
    assert _reserve(ledger, "A1", "n1", "c1").success
    ledger._connect().execute("UPDATE pilot_reservations SET reserved_cad='NaN' WHERE child_id='c1'")
    receipt = _reserve(ledger, "A2", "n2", "c2", cad="1.00")
    assert receipt.success is False
    assert receipt.reason.startswith("COORDINATION_STATE_INVALID")
    assert ledger.approval_exists("A2") is False


# ======================================== Gate 3: binding to signed payload
class _ShiftingContext(Mapping):
    """Mapping that serves one value when signed and another when re-read."""

    def __init__(self, base: dict, signed_cad: str, later_cad: str):
        self._base = dict(base, proposed_child_cad=signed_cad)
        self._later = later_cad

    def __getitem__(self, key):
        return self._base[key]

    def __iter__(self):
        return iter(self._base)

    def __len__(self):
        return len(self._base)

    def get(self, key, default=None):
        if key == "proposed_child_cad":
            return self._later
        return self._base.get(key, default)


def test_reservation_uses_signed_payload_not_caller_mapping(ledger, authority):
    """R-4: the reserved amount must equal the SIGNED amount."""
    ctx = _ShiftingContext(_order_context(), signed_cad="1.00", later_cad="19.00")
    _sim(ledger, authority, order_context=ctx)
    rows = ledger._connect().execute("SELECT reserved_cad FROM pilot_reservations").fetchall()
    assert [r[0] for r in rows] == ["1.00"]


def test_verification_uses_pinned_public_key(ledger, authority):
    """A registry whose pinned public key no longer matches the signer blocks."""
    other = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    object.__setattr__(authority.registry, "public_key_hex", other)
    with pytest.raises(TrustedSimulationBlocked, match="INTENT_VERIFICATION_FAILED"):
        _sim(ledger, authority)
    assert ledger.approval_exists("A1") is False


# ======================================== Gate 1: reconciliation idempotence
def test_reconcile_does_not_duplicate_trusted_path_records(ledger):
    """R-5: reconcile_legacy must not add legacy rows for trusted reservations."""
    assert _reserve(ledger, "A1", "n1", "c1").success
    legacy = PilotExposureReservationLedger(ledger.path, config=DEFAULT_ORDER_LIMIT_CONFIG)
    assert legacy.reserve(parent_id="p2", child_id="L1", proposed_child_cad="3.00").approved
    first = ledger.reconcile_legacy()
    second = ledger.reconcile_legacy()
    assert first == {"created": 1, "skipped": 1, "failures": []}
    assert second == {"created": 0, "skipped": 2, "failures": []}
    counts = dict(
        ledger._connect().execute(
            "SELECT child_id, COUNT(*) FROM pilot_coordination GROUP BY child_id"
        ).fetchall()
    )
    assert counts == {"c1": 1, "L1": 1}
    assert ledger.verify_consistency() == {"consistent": True, "problems": []}


# ======================================== production route stays blocked
def test_production_route_raises_unconditionally_before_side_effects():
    """Static check: the first statement after the two guards is a bare raise.

    Every path through ``submit_governed_paper_order`` raises before any
    order validation, reservation or broker call.
    """
    src = textwrap.dedent(inspect.getsource(governed_paper_route.submit_governed_paper_order))
    fn = ast.parse(src).body[0]
    body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert all(isinstance(n, ast.If) for n in body[:2])
    for guard in body[:2]:
        assert all(isinstance(s, ast.Raise) for s in guard.body) and not guard.orelse
    blocker = body[2]
    assert isinstance(blocker, ast.Raise)
    assert "PAPER_AUTHORITY_PROVENANCE_UNVERIFIED" in ast.unparse(blocker)


def test_trusted_route_never_references_broker_submission():
    """AST check (docstrings excluded): no broker module import or submit call."""
    import backend.runtime.trusted_governed_paper_route as route_mod

    tree = ast.parse(inspect.getsource(route_mod))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    for forbidden in ("submit_order", "submit_governed_paper_order", "broker_oanda", "execution_router"):
        assert not any(forbidden in n for n in names), forbidden


# ============================== OPEN findings (strict xfail — not fixed here)
@pytest.mark.xfail(
    strict=True,
    reason="OPEN G2-A: no owner-signed manifest/root-of-trust check; any caller can "
    "self-provision an AuthenticatedTrustRegistry with its own key (owner action required)",
)
def test_open_self_provisioned_registry_is_rejected(tmp_path):
    fake_git = tmp_path / "repo" / ".git"
    fake_git.mkdir(parents=True)
    (fake_git / "HEAD").write_text("d" * 40)
    key = Ed25519PrivateKey.generate()
    with pytest.raises(Exception):
        registry = AuthenticatedTrustRegistry(
            issuer_id="self-provisioned",
            candidate_sha="d" * 40,
            public_key_hex=key.public_key().public_bytes_raw().hex(),
            private_key=key,
        )
        TrustedPaperAuthority(
            registry=registry, evaluators=TrustedRiskEvaluators(), repo_root=fake_git.parent
        )._verify_current_checkout()


@pytest.mark.xfail(
    strict=True,
    reason="OPEN G3-A: reserved proposed_child_cad is not derived from the evaluated "
    "notional via verified broker/rate evidence (owner design decision required)",
)
def test_open_reserved_cad_bound_to_evaluated_notional(ledger, authority):
    ctx = _order_context()
    ctx["requested_notional"] = 50_000.0
    ctx["proposed_child_cad"] = "0.01"
    with pytest.raises(TrustedSimulationBlocked):
        _sim(ledger, authority, order_context=ctx)


@pytest.mark.xfail(
    strict=True,
    reason="OPEN G5-A: legacy PilotExposureReservationLedger.transition() on the same "
    "database can release a trusted reservation without simulator evidence",
)
def test_open_legacy_api_cannot_release_trusted_reservation(ledger):
    assert _reserve(ledger, "A1", "n1", "c1").success
    legacy = PilotExposureReservationLedger(ledger.path, config=DEFAULT_ORDER_LIMIT_CONFIG)
    assert legacy.transition("c1", from_state="OPEN", to_state="RELEASED") is False
