from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class PortfolioExposureRecord:
    symbol: str
    asset_class: str
    exposure_value: float
    side: str


class PortfolioCorrelationEngineError(RuntimeError):
    """Fail-closed exception for portfolio correlation analysis."""


class PortfolioCorrelationEngine:
    """Deterministic portfolio correlation and concentration analysis."""

    DEFAULT_CORRELATION_GROUPS: dict[str, set[str]] = {
        "BTC_ETH_SOL": {"BTCUSD", "ETHUSD", "SOLUSD"},
        "MAJOR_USD_FX": {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"},
        "EQUITY_INDEX_FUTURES": {"ES", "NQ", "YM", "RTY", "MES", "MNQ", "MYM", "M2K"},
    }

    def __init__(self, correlation_groups: Mapping[str, Iterable[str]] | None = None) -> None:
        self.correlation_groups = self._normalize_group_config(correlation_groups or {})

    def analyze_portfolio(self, positions: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        if positions is None:
            raise PortfolioCorrelationEngineError("positions must not be None")
        if not isinstance(positions, Iterable):
            raise PortfolioCorrelationEngineError("positions must be iterable")

        records = [self._normalize_position(position) for position in positions]
        if not records:
            return self._empty_summary()

        by_asset_class: dict[str, float] = {}
        by_symbol: dict[str, float] = {}
        long_exposure = 0.0
        short_exposure = 0.0
        directional_exposure = 0.0
        grouped_exposure: dict[str, float] = {}

        for record in records:
            exposure = abs(float(record.exposure_value))
            asset_class = record.asset_class
            symbol = record.symbol

            by_asset_class[asset_class] = by_asset_class.get(asset_class, 0.0) + exposure
            by_symbol[symbol] = by_symbol.get(symbol, 0.0) + exposure

            if record.side == "SHORT":
                short_exposure += exposure
                directional_exposure -= exposure
            else:
                long_exposure += exposure
                directional_exposure += exposure

            correlation_group = self._resolve_group(symbol)
            if correlation_group:
                grouped_exposure[correlation_group] = grouped_exposure.get(correlation_group, 0.0) + exposure

        total_exposure = long_exposure + short_exposure
        directional_concentration = abs(long_exposure - short_exposure) / total_exposure if total_exposure > 0 else 0.0
        concentration_score = self._compute_concentration_score(
            by_symbol,
            by_asset_class,
            total_exposure,
            directional_concentration,
        )
        correlation_score = self._compute_correlation_score(grouped_exposure, total_exposure)

        return {
            "total_exposure": round(total_exposure, 8),
            "by_asset_class": self._sorted_rounded_map(by_asset_class),
            "by_symbol": self._sorted_rounded_map(by_symbol),
            "long_exposure": round(long_exposure, 8),
            "short_exposure": round(short_exposure, 8),
            "directional_exposure": round(directional_exposure, 8),
            "directional_concentration": round(directional_concentration, 8),
            "concentration_score": concentration_score,
            "correlation_score": correlation_score,
            "grouped_exposure": self._sorted_rounded_map(grouped_exposure),
            "correlation_groups": self._sorted_group_map(),
        }

    def _resolve_group(self, symbol: str) -> str | None:
        normalized = self._normalize_symbol(symbol)
        for group_name, members in self._sorted_group_map().items():
            if normalized in members:
                return group_name
        return None

    def _compute_concentration_score(
        self,
        by_symbol: Mapping[str, float],
        by_asset_class: Mapping[str, float],
        total_exposure: float,
        directional_concentration: float,
    ) -> float:
        if total_exposure <= 0:
            return 0.0

        largest_symbol = max(by_symbol.values(), default=0.0)
        largest_asset_class = max(by_asset_class.values(), default=0.0)
        symbol_concentration = largest_symbol / total_exposure
        asset_concentration = largest_asset_class / total_exposure
        score = (symbol_concentration * 0.45) + (asset_concentration * 0.35) + (directional_concentration * 0.20)
        return round(max(0.0, min(score, 1.0)), 8)

    def _compute_correlation_score(self, grouped_exposure: Mapping[str, float], total_exposure: float) -> float:
        if total_exposure <= 0:
            return 0.0
        if not grouped_exposure:
            return 0.0

        largest_group = max(grouped_exposure.values())
        score = largest_group / total_exposure
        return round(max(0.0, min(score, 1.0)), 8)

    def _normalize_position(self, position: Mapping[str, Any]) -> PortfolioExposureRecord:
        if not isinstance(position, Mapping):
            raise PortfolioCorrelationEngineError("Each position must be a mapping")

        symbol = self._normalize_symbol(position.get("symbol"))
        asset_class = str(position.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN"
        if not symbol:
            raise PortfolioCorrelationEngineError("Position symbol must be non-empty")

        exposure_value = self._extract_exposure_value(position)
        side = self._resolve_side(position, exposure_value)

        return PortfolioExposureRecord(
            symbol=symbol,
            asset_class=asset_class,
            exposure_value=exposure_value,
            side=side,
        )

    def _extract_exposure_value(self, position: Mapping[str, Any]) -> float:
        candidate_fields = (
            "exposure_value",
            "market_value",
            "notional_value",
            "position_value",
            "current_value",
            "value",
        )
        for field in candidate_fields:
            if field in position and position.get(field) is not None:
                try:
                    return float(position[field])
                except (TypeError, ValueError) as exc:
                    raise PortfolioCorrelationEngineError(f"Position field {field} must be numeric") from exc

        if "quantity" not in position or position.get("quantity") is None:
            raise PortfolioCorrelationEngineError("Position must include exposure_value, value, or quantity")

        try:
            return float(position["quantity"])
        except (TypeError, ValueError) as exc:
            raise PortfolioCorrelationEngineError("Position quantity must be numeric") from exc

    def _resolve_side(self, position: Mapping[str, Any], exposure_value: float) -> str:
        side_value = str(position.get("side") or position.get("direction") or "").strip().upper()
        if side_value in {"LONG", "BUY"}:
            return "LONG"
        if side_value in {"SHORT", "SELL"}:
            return "SHORT"
        if exposure_value < 0:
            return "SHORT"
        return "LONG"

    @staticmethod
    def _normalize_symbol(symbol: Any) -> str:
        text = str(symbol or "").strip().upper()
        if not text:
            return ""
        return "".join(ch for ch in text if ch.isalnum())

    @staticmethod
    def _normalize_group_config(correlation_groups: Mapping[str, Iterable[str]]) -> dict[str, set[str]]:
        normalized: dict[str, set[str]] = {}
        for group_name, members in correlation_groups.items():
            normalized_name = str(group_name or "").strip().upper()
            if not normalized_name:
                raise PortfolioCorrelationEngineError("Correlation group name must be non-empty")
            member_set: set[str] = set()
            for member in members:
                normalized_member = PortfolioCorrelationEngine._normalize_symbol(member)
                if not normalized_member:
                    raise PortfolioCorrelationEngineError("Correlation group members must be non-empty")
                member_set.add(normalized_member)
            if not member_set:
                raise PortfolioCorrelationEngineError("Correlation group must contain at least one member")
            normalized[normalized_name] = member_set

        merged = dict(PortfolioCorrelationEngine.DEFAULT_CORRELATION_GROUPS)
        merged.update(normalized)
        return merged

    def _sorted_group_map(self) -> dict[str, set[str]]:
        return {key: self.correlation_groups[key] for key in sorted(self.correlation_groups.keys())}

    @staticmethod
    def _sorted_rounded_map(values: Mapping[str, float]) -> dict[str, float]:
        return {key: round(values[key], 8) for key in sorted(values.keys())}

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {
            "total_exposure": 0.0,
            "by_asset_class": {},
            "by_symbol": {},
            "long_exposure": 0.0,
            "short_exposure": 0.0,
            "directional_exposure": 0.0,
            "directional_concentration": 0.0,
            "concentration_score": 0.0,
            "correlation_score": 0.0,
            "grouped_exposure": {},
            "correlation_groups": {},
        }
