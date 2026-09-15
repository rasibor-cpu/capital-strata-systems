from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CorrelationPair:
    asset_a: str
    asset_b: str
    correlation: Decimal
    relationship: str


@dataclass(frozen=True)
class ConcentrationAlert:
    asset_a: str
    asset_b: str
    correlation: Decimal
    combined_weight: Decimal
    severity: str


def _validate_series(name: str, values: Sequence[Decimal]) -> None:
    if not name.strip():
        raise ValueError("asset name is required")
    if len(values) < 2:
        raise ValueError("at least two observations are required")
    if any(not value.is_finite() for value in values):
        raise ValueError("series contains non-finite values")


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def pearson_correlation(a: Sequence[Decimal], b: Sequence[Decimal]) -> Decimal:
    if len(a) != len(b):
        raise ValueError("series lengths must match")
    _validate_series("a", a)
    _validate_series("b", b)

    mean_a = _mean(a)
    mean_b = _mean(b)
    da = [x - mean_a for x in a]
    db = [x - mean_b for x in b]
    numerator = sum((x * y for x, y in zip(da, db)), Decimal("0"))
    denom_a = sum((x * x for x in da), Decimal("0"))
    denom_b = sum((y * y for y in db), Decimal("0"))

    if denom_a == 0 or denom_b == 0:
        raise ValueError("zero-variance series cannot be correlated")

    with localcontext() as ctx:
        ctx.prec = 28
        denominator = (denom_a * denom_b).sqrt()
        result = numerator / denominator
        if result > 1:
            result = Decimal("1")
        elif result < -1:
            result = Decimal("-1")
        return result.quantize(Decimal("0.000001"))


def classify_correlation(value: Decimal) -> str:
    if value >= Decimal("0.75"):
        return "STRONGLY_POSITIVE"
    if value >= Decimal("0.50"):
        return "POSITIVE"
    if value <= Decimal("-0.75"):
        return "STRONGLY_NEGATIVE"
    if value <= Decimal("-0.50"):
        return "NEGATIVE"
    return "NEUTRAL"


def correlation_pairs(
    returns_by_asset: Mapping[str, Sequence[Decimal]],
) -> tuple[CorrelationPair, ...]:
    names = sorted(returns_by_asset)
    pairs: list[CorrelationPair] = []
    for i, asset_a in enumerate(names):
        _validate_series(asset_a, returns_by_asset[asset_a])
        for asset_b in names[i + 1 :]:
            corr = pearson_correlation(
                returns_by_asset[asset_a],
                returns_by_asset[asset_b],
            )
            pairs.append(
                CorrelationPair(
                    asset_a=asset_a,
                    asset_b=asset_b,
                    correlation=corr,
                    relationship=classify_correlation(corr),
                )
            )
    return tuple(pairs)


def detect_hidden_concentration(
    pairs: Sequence[CorrelationPair],
    portfolio_weights: Mapping[str, Decimal],
    *,
    correlation_threshold: Decimal = Decimal("0.75"),
    combined_weight_threshold: Decimal = Decimal("0.35"),
) -> tuple[ConcentrationAlert, ...]:
    if not (Decimal("0") <= correlation_threshold <= Decimal("1")):
        raise ValueError("correlation_threshold must be in [0, 1]")
    if not (Decimal("0") < combined_weight_threshold <= Decimal("1")):
        raise ValueError("combined_weight_threshold must be in (0, 1]")

    total_weight = sum(portfolio_weights.values(), Decimal("0"))
    if any(weight < 0 for weight in portfolio_weights.values()):
        raise ValueError("portfolio weights must be non-negative")
    if total_weight > Decimal("1.000001"):
        raise ValueError("portfolio weights cannot exceed 1")

    alerts: list[ConcentrationAlert] = []
    for pair in pairs:
        if pair.correlation < correlation_threshold:
            continue
        combined = portfolio_weights.get(pair.asset_a, Decimal("0")) + portfolio_weights.get(
            pair.asset_b, Decimal("0")
        )
        if combined < combined_weight_threshold:
            continue
        severity = "HIGH" if combined >= Decimal("0.50") else "MODERATE"
        alerts.append(
            ConcentrationAlert(
                asset_a=pair.asset_a,
                asset_b=pair.asset_b,
                correlation=pair.correlation,
                combined_weight=combined,
                severity=severity,
            )
        )
    return tuple(sorted(alerts, key=lambda x: (-x.combined_weight, x.asset_a, x.asset_b)))
