from decimal import Decimal
import pytest

from engine.commercial.commercial_controls import ControlledAction, RESOLVE_RECONCILIATION_EXCEPTION
from engine.commercial.reconciliation_service import ReconciliationService, SettlementEvidence
from engine.domain.collections import CollectionStatus, CollectionTransaction


def make_exception():
    c = CollectionTransaction(
        obligation_id="obl-x", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="x-key",
        status=CollectionStatus.SETTLED, provider_reference="p1",
        settlement_reference="s1", ledger_txn_id="l1",
    )
    svc = ReconciliationService()
    svc.reconcile(c, SettlementEvidence(c.collection_id, "p1", "s1", Decimal("24.00"), "CAD"))
    return svc, next(iter(svc.exceptions.values()))


def approved(exception_id, resolution_reference="ticket-1", *, maker="fincon-01", checker="finance-controller",
             status="APPROVED", action_type=RESOLVE_RECONCILIATION_EXCEPTION):
    return ControlledAction(
        action_id="act-1", action_type=action_type, object_ref=f"reconciliation_exception:{exception_id}",
        payload={"exception_id": exception_id, "resolution_reference": resolution_reference},
        payload_hash="0" * 64, idempotency_key="k", maker_id=maker, maker_role="FINCON",
        requested_at="2026-09-29T00:00:00Z", status=status, checker_id=checker, checker_role="HEAD_FINCON",
    )


def test_resolution_requires_attribution_and_reference():
    svc, item = make_exception()
    with pytest.raises(ValueError):
        svc.apply_approved_resolution(approved(item.exception_id, resolution_reference=""))
    assert item.resolved_at is None


def test_resolution_is_attributed_to_the_checker_and_removed_from_open_queue():
    svc, item = make_exception()
    resolved = svc.apply_approved_resolution(approved(item.exception_id))
    assert resolved.resolved_at is not None
    assert resolved.resolved_by == "finance-controller"
    assert resolved.resolution_reference == "ticket-1"
    assert svc.open_exceptions() == []


def test_resolved_exception_is_immutable_except_idempotent_retry():
    svc, item = make_exception()
    first = svc.apply_approved_resolution(approved(item.exception_id))
    second = svc.apply_approved_resolution(approved(item.exception_id))
    assert second.resolved_at == first.resolved_at
    with pytest.raises(ValueError):
        svc.apply_approved_resolution(approved(item.exception_id, "ticket-2", checker="other-user"))


# ---------------------------------------------------------------------------
# Register item #8: no ungoverned resolution path remains.
# ---------------------------------------------------------------------------


def test_the_legacy_unchecked_resolve_exception_entry_point_is_gone():
    svc, _item = make_exception()
    assert not hasattr(svc, "resolve_exception")


@pytest.mark.parametrize("status", ["PENDING", "REJECTED", "EXECUTED", "FAILED", ""])
def test_an_action_that_is_not_approved_cannot_resolve(status):
    svc, item = make_exception()
    with pytest.raises(PermissionError):
        svc.apply_approved_resolution(approved(item.exception_id, status=status))
    assert item.resolved_at is None


@pytest.mark.parametrize("maker,checker", [("same", "same"), ("fincon-01", None), ("fincon-01", ""), ("", "head-01")])
def test_self_approved_or_unattributed_actions_cannot_resolve(maker, checker):
    svc, item = make_exception()
    with pytest.raises(PermissionError):
        svc.apply_approved_resolution(approved(item.exception_id, maker=maker, checker=checker))
    assert item.resolved_at is None


def test_a_different_action_type_cannot_resolve():
    svc, item = make_exception()
    with pytest.raises(PermissionError):
        svc.apply_approved_resolution(approved(item.exception_id, action_type="ENROLL_TRIAL"))
    assert item.resolved_at is None


def test_an_unknown_exception_cannot_be_resolved():
    svc, _item = make_exception()
    with pytest.raises(KeyError):
        svc.apply_approved_resolution(approved("no-such-exception"))


def _production_sources():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    for top in ("engine", "backend", "dashboard", "scripts", "tools", "ui", "ops", "governance"):
        for path in (root / top).rglob("*.py"):
            try:
                yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    for path in root.glob("*.py"):
        yield path.name, path.read_text(encoding="utf-8", errors="replace")


def test_only_the_maker_checker_executor_calls_the_governed_entry_point():
    """Architecture guard: production code resolves exceptions only via CommercialControls."""
    sources = list(_production_sources())
    callers = sorted(rel for rel, text in sources if ".apply_approved_resolution(" in text)
    assert callers == ["engine/commercial/commercial_controls.py"]
    assert not [rel for rel, text in sources if ".resolve_exception(" in text]
