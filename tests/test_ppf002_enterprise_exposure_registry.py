from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.governance.enterprise_exposure_registry import (
    EnterpriseExposureRegistry,
    ExposureOperationStatus,
    ExposureReasonCode,
    ExposureReservationStatus,
)
from backend.governance.enterprise_profit_protection_contracts import (
    PPFMaturityTier,
    PPFRiskRequest,
)
from backend.governance.enterprise_profit_protection_manager import (
    EnterpriseProfitProtectionManager,
)


NOW = datetime(2026, 7, 24, 13, 0, tzinfo=timezone.utc)


def _ppf_decision(profit: Decimal = Decimal("100.00")):
    return EnterpriseProfitProtectionManager().evaluate(
        PPFRiskRequest(
            request_id="ppf-002-budget",
            maturity_tier=PPFMaturityTier.STARTUP,
            banked_net_profit=profit,
            principal_capital=Decimal("1000000.00"),
            current_drawdown_pct=Decimal("0"),
            previous_drawdown_pct=Decimal("0"),
            recent_loss_amount=Decimal("0"),
            volatility_score=Decimal("0"),
            liquidity_score=Decimal("1"),
            confidence_score=Decimal("1"),
            correlation_score=Decimal("0"),
            margin_utilization=Decimal("0"),
            observed_at=NOW.isoformat(),
        ),
        now=NOW,
    )


def _registry(**overrides) -> EnterpriseExposureRegistry:
    payload = {
        "profit_protection_decision": _ppf_decision(),
        "created_at": NOW,
    }
    payload.update(overrides)
    return EnterpriseExposureRegistry(**payload)


def test_ppf002_reservation_creation_and_remaining_budget() -> None:
    registry = _registry()

    result = registry.reserve_exposure(
        reservation_id="res-001",
        module="OPTIONS",
        amount=Decimal("10.00"),
        now=NOW,
    )

    assert result.accepted is True
    assert result.status is ExposureOperationStatus.ACCEPTED
    assert result.reservation.status is ExposureReservationStatus.RESERVED
    assert registry.current_state(now=NOW).reserved_exposure == Decimal("10.00")
    assert registry.remaining_budget(now=NOW) == Decimal("70.00")
    assert ExposureReasonCode.BUDGET_SOURCE_PPF in registry.current_state(now=NOW).reason_codes


def test_ppf002_duplicate_reservation_is_protected_and_idempotent_when_identical() -> None:
    registry = _registry()
    first = registry.reserve_exposure(
        reservation_id="res-dup",
        module="OPTIONS",
        amount=Decimal("10.00"),
        now=NOW,
    )
    replay = registry.reserve_exposure(
        reservation_id="res-dup",
        module="OPTIONS",
        amount=Decimal("10.00"),
        now=NOW,
    )
    duplicate = registry.reserve_exposure(
        reservation_id="res-dup",
        module="FUTURES",
        amount=Decimal("10.00"),
        now=NOW,
    )

    assert first.accepted is True
    assert replay.status is ExposureOperationStatus.IDEMPOTENT
    assert ExposureReasonCode.IDEMPOTENT_REPLAY in replay.reason_codes
    assert duplicate.accepted is False
    assert ExposureReasonCode.DUPLICATE_RESERVATION in duplicate.reason_codes


def test_ppf002_commit_and_release_reservation_lifecycle() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-life",
        module="TRADING_RUNTIME",
        amount=Decimal("12.50"),
        now=NOW,
    )

    committed = registry.commit_reservation("res-life", now=NOW)
    state_after_commit = registry.current_state(now=NOW)
    released = registry.release_reservation("res-life", now=NOW)
    state_after_release = registry.current_state(now=NOW)

    assert committed.accepted is True
    assert committed.reservation.status is ExposureReservationStatus.COMMITTED
    assert state_after_commit.current_enterprise_exposure == Decimal("12.50")
    assert state_after_commit.reserved_exposure == Decimal("0")
    assert released.accepted is True
    assert released.reservation.status is ExposureReservationStatus.RELEASED
    assert state_after_release.current_enterprise_exposure == Decimal("0")
    assert state_after_release.remaining_enterprise_risk_budget == Decimal("80.00")


def test_ppf002_owner_commit_succeeds() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-owner-commit",
        module="TRADING_RUNTIME",
        amount=Decimal("12.50"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.commit_reservation("res-owner-commit", owner_id="engine-alpha", now=NOW)

    assert result.accepted is True
    assert result.reservation.status is ExposureReservationStatus.COMMITTED


def test_ppf002_non_owner_commit_is_rejected() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-non-owner-commit",
        module="TRADING_RUNTIME",
        amount=Decimal("12.50"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.commit_reservation("res-non-owner-commit", owner_id="engine-beta", now=NOW)

    assert result.accepted is False
    assert ExposureReasonCode.OWNER_MISMATCH in result.reason_codes
    assert registry.reservations()[0].status is ExposureReservationStatus.RESERVED


def test_ppf002_owner_release_succeeds() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-owner-release",
        module="RISK",
        amount=Decimal("2.00"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.release_reservation("res-owner-release", owner_id="engine-alpha", now=NOW)

    assert result.accepted is True
    assert result.reservation.status is ExposureReservationStatus.RELEASED


def test_ppf002_non_owner_release_is_rejected() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-non-owner-release",
        module="RISK",
        amount=Decimal("2.00"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.release_reservation("res-non-owner-release", owner_id="engine-beta", now=NOW)

    assert result.accepted is False
    assert ExposureReasonCode.OWNER_MISMATCH in result.reason_codes
    assert registry.reservations()[0].status is ExposureReservationStatus.RESERVED


def test_ppf002_owner_expire_succeeds() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-owner-expire",
        module="OPTIONS",
        amount=Decimal("5.00"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.expire_reservation("res-owner-expire", owner_id="engine-alpha", now=NOW)

    assert result.accepted is True
    assert result.reservation.status is ExposureReservationStatus.EXPIRED


def test_ppf002_non_owner_expire_is_rejected() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-non-owner-expire",
        module="OPTIONS",
        amount=Decimal("5.00"),
        owner_id="engine-alpha",
        now=NOW,
    )

    result = registry.expire_reservation("res-non-owner-expire", owner_id="engine-beta", now=NOW)

    assert result.accepted is False
    assert ExposureReasonCode.OWNER_MISMATCH in result.reason_codes
    assert registry.reservations()[0].status is ExposureReservationStatus.RESERVED


def test_ppf002_release_is_idempotent() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-release",
        module="RISK",
        amount=Decimal("2.00"),
        now=NOW,
    )
    registry.release_reservation("res-release", now=NOW)

    replay = registry.release_reservation("res-release", now=NOW)

    assert replay.status is ExposureOperationStatus.IDEMPOTENT
    assert ExposureReasonCode.IDEMPOTENT_REPLAY in replay.reason_codes


def test_ppf002_reservation_expiry_and_reconciliation() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-expire",
        module="OPTIONS",
        amount=Decimal("10.00"),
        ttl_seconds=1,
        now=NOW,
    )

    result = registry.reconcile(now=NOW + timedelta(seconds=2))
    reservation = registry.reservations()[0]

    assert result.accepted is True
    assert reservation.status is ExposureReservationStatus.EXPIRED
    assert registry.remaining_budget(now=NOW + timedelta(seconds=2)) == Decimal("80.00")


def test_ppf002_explicit_expire_reservation() -> None:
    registry = _registry()
    registry.reserve_exposure(
        reservation_id="res-explicit-expire",
        module="OPTIONS",
        amount=Decimal("5.00"),
        now=NOW,
    )

    result = registry.expire_reservation("res-explicit-expire", now=NOW)

    assert result.accepted is True
    assert result.reservation.status is ExposureReservationStatus.EXPIRED
    assert ExposureReasonCode.RESERVATION_EXPIRED in result.reason_codes


def test_ppf002_over_budget_request_fails_closed() -> None:
    registry = _registry()

    result = registry.reserve_exposure(
        reservation_id="res-over",
        module="OPTIONS",
        amount=Decimal("81.00"),
        now=NOW,
    )

    assert result.accepted is False
    assert result.status is ExposureOperationStatus.REJECTED
    assert ExposureReasonCode.BUDGET_EXCEEDED in result.reason_codes
    assert registry.current_state(now=NOW).reserved_exposure == Decimal("0")


def test_ppf002_concurrent_reservation_simulation_is_thread_safe() -> None:
    registry = _registry()

    def reserve(index: int):
        return registry.reserve_exposure(
            reservation_id=f"res-concurrent-{index:02d}",
            module="MISSION_CONTROL",
            amount=Decimal("1.00"),
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(reserve, range(10)))

    assert all(result.accepted for result in results)
    assert registry.current_state(now=NOW).reserved_exposure == Decimal("10.00")
    assert registry.current_state(now=NOW).active_reservation_count == 10


def test_ppf002_module_aggregation() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-options", module="OPTIONS", amount=Decimal("4.00"), now=NOW)
    registry.reserve_exposure(reservation_id="res-futures", module="FUTURES", amount=Decimal("6.00"), now=NOW)
    registry.commit_reservation("res-futures", now=NOW)

    attribution = registry.current_state(now=NOW).module_attribution

    assert attribution["OPTIONS"]["reserved"] == Decimal("4.00")
    assert attribution["FUTURES"]["committed"] == Decimal("6.00")
    assert attribution["FUTURES"]["total"] == Decimal("6.00")


def test_ppf002_orphan_reservation_detection() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-known", module="OPTIONS", amount=Decimal("4.00"), now=NOW)
    registry.commit_reservation("res-known", now=NOW)

    result = registry.reconcile(
        {
            "res-known": Decimal("4.00"),
            "res-orphan": Decimal("1.00"),
        },
        now=NOW,
    )

    assert result.accepted is False
    assert ExposureReasonCode.ORPHAN_RESERVATION_DETECTED in result.reason_codes


@pytest.mark.parametrize(
    ("reservation_id", "module", "amount", "reason"),
    (
        ("", "OPTIONS", Decimal("1.00"), ExposureReasonCode.INVALID_IDENTIFIER),
        ("res-bad-module", "UNKNOWN", Decimal("1.00"), ExposureReasonCode.UNKNOWN_MODULE),
        ("res-negative", "OPTIONS", Decimal("-1.00"), ExposureReasonCode.NEGATIVE_EXPOSURE),
        ("res-nan", "OPTIONS", "NaN", ExposureReasonCode.INPUT_NOT_FINITE),
        ("res-inf", "OPTIONS", "Infinity", ExposureReasonCode.INPUT_NOT_FINITE),
        ("res-zero", "OPTIONS", Decimal("0"), ExposureReasonCode.INVALID_RESERVATION),
    ),
)
def test_ppf002_invalid_reservations_fail_closed(reservation_id, module, amount, reason) -> None:
    result = _registry().reserve_exposure(
        reservation_id=reservation_id,
        module=module,
        amount=amount,
        now=NOW,
    )

    assert result.accepted is False
    assert reason in result.reason_codes


def test_ppf002_missing_reservation_fails_closed() -> None:
    result = _registry().commit_reservation("missing", now=NOW)

    assert result.accepted is False
    assert ExposureReasonCode.MISSING_RESERVATION in result.reason_codes


def test_ppf002_inconsistent_reservation_state_fails_closed() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-state", module="OPTIONS", amount=Decimal("1.00"), now=NOW)
    registry.release_reservation("res-state", now=NOW)

    result = registry.commit_reservation("res-state", now=NOW)

    assert result.accepted is False
    assert ExposureReasonCode.INCONSISTENT_RESERVATION_STATE in result.reason_codes


def test_ppf002_stale_registry_rejects_mutation() -> None:
    registry = _registry(max_registry_age_seconds=1)

    result = registry.reserve_exposure(
        reservation_id="res-stale",
        module="OPTIONS",
        amount=Decimal("1.00"),
        now=NOW + timedelta(seconds=2),
    )

    assert result.accepted is False
    assert ExposureReasonCode.REGISTRY_STALE in result.reason_codes
    assert registry.current_state(now=NOW + timedelta(seconds=2)).stale is True


def test_ppf002_decimal_precision_is_deterministic() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-decimal-a", module="OPTIONS", amount=Decimal("0.10"), now=NOW)
    registry.reserve_exposure(reservation_id="res-decimal-b", module="OPTIONS", amount=Decimal("0.20"), now=NOW)

    state = registry.current_state(now=NOW)

    assert state.reserved_exposure == Decimal("0.30")
    assert state.remaining_enterprise_risk_budget == Decimal("79.70")
    assert state.as_dict()["reserved_exposure"] == "0.30"


def test_ppf002_registry_budget_comes_only_from_ppf_decision_and_principal_is_never_consumed() -> None:
    decision = _ppf_decision(profit=Decimal("10.00"))
    registry = _registry(profit_protection_decision=decision)

    assert registry.enterprise_risk_budget == Decimal("8.00")
    assert registry.reserve_exposure(
        reservation_id="res-principal-not-consumed",
        module="OPTIONS",
        amount=Decimal("9.00"),
        now=NOW,
    ).accepted is False
    assert ExposureReasonCode.PRINCIPAL_EXCLUDED in registry.current_state(now=NOW).reason_codes


def test_ppf002_reconciliation_detects_amount_mismatch_and_missing_committed() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-commit-a", module="OPTIONS", amount=Decimal("4.00"), now=NOW)
    registry.reserve_exposure(reservation_id="res-commit-b", module="FUTURES", amount=Decimal("5.00"), now=NOW)
    registry.commit_reservation("res-commit-a", now=NOW)
    registry.commit_reservation("res-commit-b", now=NOW)

    mismatch = registry.reconcile({"res-commit-a": Decimal("4.01")}, now=NOW)

    assert mismatch.accepted is False
    assert ExposureReasonCode.RECONCILIATION_MISMATCH in mismatch.reason_codes


def test_ppf002_active_reservations_can_filter_by_module() -> None:
    registry = _registry()
    registry.reserve_exposure(reservation_id="res-active-options", module="OPTIONS", amount=Decimal("1.00"), now=NOW)
    registry.reserve_exposure(reservation_id="res-active-futures", module="FUTURES", amount=Decimal("1.00"), now=NOW)

    options = registry.active_reservations(module="OPTIONS", now=NOW)

    assert [reservation.reservation_id for reservation in options] == ["res-active-options"]
