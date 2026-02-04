"""
Correlation / Concentration Gate – REA Capital Trading Engine
------------------------------------------------------------

Purpose:
- Prevent taking on excessive correlated exposure across instruments.
- Blocks new orders if they increase correlation-weighted exposure above limits.
- Adapter-agnostic: caller supplies current portfolio exposures + correlation matrix.

Safe default:
- Missing correlation data => BLOCK (unless explicitly configured otherwise).

Notes:
- This is NOT a full risk model. It's a protective gate for concentration control.
- Uses simple correlation-weighted exposure aggregation.

Integration later:
- Strategy proposes an OrderIntent with an estimated notional exposure.
- PortfolioRiskSnapshot provides open exposures by symbol (signed notionals).
- Gate evaluates whether adding the new exposure breaches thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any, Tuple


class CorrelationDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"


@dataclass(frozen=True)
class CorrelationPolicy:
    """
    max_single_symbol_frac: Max fraction of equity in a single symbol exposure (abs notional / equity).
    max_cluster_frac: Max fraction of equity in a correlated cluster exposure.
    corr_threshold: Instruments with |corr| >= threshold are considered "cluster-linked".
    hard_block: If True, breach => BLOCK.
    allow_missing_corr: If True, missing correlation entries are treated as 0 corr (less safe).
    """
    max_single_symbol_frac: float = 0.20   # user governance: 20% of equity per single trade/exposure
    max_cluster_frac: float = 0.50         # cap correlated cluster exposure
    corr_threshold: float = 0.75
    hard_block: bool = True
    allow_missing_corr: bool = False
    reason_prefix: str = "CORRELATION_GATE"


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    """
    equity: current equity used as denominator (must be > 0)
    exposures: signed notional exposure per symbol (e.g., +$ notional long, -$ notional short)
               For FX, use USD-notional or consistent base-notional.
    """
    equity: float
    exposures: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CorrelationResult:
    decision: CorrelationDecision
    single_symbol_frac: float
    cluster_frac: float
    reason: str


def _is_num(x) -> bool:
    return isinstance(x, (int, float))


def _abs(x: float) -> float:
    return x if x >= 0 else -x


def _get_corr(
    corr: Dict[Tuple[str, str], float],
    a: str,
    b: str,
    policy: CorrelationPolicy,
) -> Optional[float]:
    if a == b:
        return 1.0
    key1 = (a, b)
    key2 = (b, a)
    if key1 in corr:
        return corr[key1]
    if key2 in corr:
        return corr[key2]
    return None if not policy.allow_missing_corr else 0.0


def evaluate_correlation_gate(
    *,
    snapshot: PortfolioRiskSnapshot,
    new_symbol: str,
    new_exposure_notional: float,
    corr: Dict[Tuple[str, str], float],
    policy: CorrelationPolicy = CorrelationPolicy(),
) -> CorrelationResult:
    """
    Evaluate whether adding (new_symbol, new_exposure_notional) breaches:
    1) Single symbol exposure fraction cap
    2) Correlated cluster exposure cap
    """

    # Validate equity
    if not _is_num(snapshot.equity) or snapshot.equity <= 0:
        return CorrelationResult(
            decision=CorrelationDecision.BLOCK,
            single_symbol_frac=0.0,
            cluster_frac=0.0,
            reason=f"{policy.reason_prefix}: BLOCK — invalid equity in snapshot.",
        )

    if not _is_num(new_exposure_notional):
        return CorrelationResult(
            decision=CorrelationDecision.BLOCK,
            single_symbol_frac=0.0,
            cluster_frac=0.0,
            reason=f"{policy.reason_prefix}: BLOCK — non-numeric new exposure.",
        )

    equity = float(snapshot.equity)
    exposures = dict(snapshot.exposures or {})

    # Existing exposure for symbol
    existing = float(exposures.get(new_symbol, 0.0))
    combined = existing + float(new_exposure_notional)

    single_symbol_frac = _abs(combined) / equity

    # Single-symbol cap
    if single_symbol_frac > policy.max_single_symbol_frac:
        action = "BLOCK" if policy.hard_block else "WARN"
        return CorrelationResult(
            decision=CorrelationDecision.BLOCK if policy.hard_block else CorrelationDecision.WARN,
            single_symbol_frac=single_symbol_frac,
            cluster_frac=single_symbol_frac,  # best effort
            reason=(
                f"{policy.reason_prefix}: {action} — {new_symbol} exposure "
                f"{(single_symbol_frac*100):.2f}% exceeds limit "
                f"{(policy.max_single_symbol_frac*100):.2f}% of equity."
            ),
        )

    # Build correlated cluster: instruments with |corr| >= threshold to new_symbol
    cluster_notional = _abs(combined)  # include the new symbol itself
    missing_corr = False

    for sym, exp in exposures.items():
        if sym == new_symbol:
            continue
        c = _get_corr(corr, new_symbol, sym, policy)
        if c is None:
            missing_corr = True
            continue
        if _abs(float(c)) >= policy.corr_threshold:
            cluster_notional += _abs(float(exp))

    # If missing corr data and not allowed => block (safe default)
    if missing_corr and not policy.allow_missing_corr:
        return CorrelationResult(
            decision=CorrelationDecision.BLOCK,
            single_symbol_frac=single_symbol_frac,
            cluster_frac=0.0,
            reason=f"{policy.reason_prefix}: BLOCK — missing correlation data for one or more symbols.",
        )

    cluster_frac = cluster_notional / equity

    if cluster_frac > policy.max_cluster_frac:
        action = "BLOCK" if policy.hard_block else "WARN"
        return CorrelationResult(
            decision=CorrelationDecision.BLOCK if policy.hard_block else CorrelationDecision.WARN,
            single_symbol_frac=single_symbol_frac,
            cluster_frac=cluster_frac,
            reason=(
                f"{policy.reason_prefix}: {action} — correlated cluster exposure "
                f"{(cluster_frac*100):.2f}% exceeds limit "
                f"{(policy.max_cluster_frac*100):.2f}% of equity."
            ),
        )

    return CorrelationResult(
        decision=CorrelationDecision.ALLOW,
        single_symbol_frac=single_symbol_frac,
        cluster_frac=cluster_frac,
        reason=f"{policy.reason_prefix}: ALLOW — concentration within limits.",
    )


def quick_self_test() -> None:
    snap = PortfolioRiskSnapshot(
        equity=100_000,
        exposures={
            "EURUSD": 10_000,
            "GBPUSD": 12_000,
            "BTCUSD": 5_000,
        },
    )

    corr = {
        ("EURUSD", "GBPUSD"): 0.85,
        ("EURUSD", "BTCUSD"): 0.10,
    }

    pol = CorrelationPolicy(
        max_single_symbol_frac=0.20,
        max_cluster_frac=0.50,
        corr_threshold=0.75,
        hard_block=True,
        allow_missing_corr=False,
    )

    r1 = evaluate_correlation_gate(
        snapshot=snap,
        new_symbol="EURUSD",
        new_exposure_notional=5_000,
        corr=corr,
        policy=pol,
    )
    r2 = evaluate_correlation_gate(
        snapshot=snap,
        new_symbol="EURUSD",
        new_exposure_notional=30_000,  # pushes single-symbol above 20%
        corr=corr,
        policy=pol,
    )

    print(r1)
    print(r2)


if __name__ == "__main__":
    quick_self_test()
