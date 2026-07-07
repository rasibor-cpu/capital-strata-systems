from __future__ import annotations

from typing import Any, Mapping


class ExecutionQualityMonitorError(ValueError):
    """Exception raised when execution quality monitoring encounters invalid input or configurations."""
    pass


class ExecutionQualityMonitor:
    """
    Advisory-only Execution Quality Monitor.
    Evaluates execution quality after simulated/paper/live-read-only trade events.
    Runs in shadow mode with zero runtime execution impact.
    """

    def __init__(self) -> None:
        pass

    def evaluate_execution(
        self,
        execution_event: Mapping[str, Any],
        market_metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Evaluates the quality of a completed or failed execution event.
        Fails closed by raising ExecutionQualityMonitorError if required keys are missing or malformed.
        """
        # Validate inputs
        if not isinstance(execution_event, Mapping):
            raise ExecutionQualityMonitorError("execution_event must be a Mapping")

        mkt_met = market_metrics if market_metrics is not None else {}
        if not isinstance(mkt_met, Mapping):
            raise ExecutionQualityMonitorError("market_metrics must be a Mapping")

        # Validate required trade/execution identifiers
        for field in ["trade_id", "symbol", "fill_status"]:
            val = execution_event.get(field)
            if not val or not isinstance(val, str) or not val.strip():
                raise ExecutionQualityMonitorError(f"Missing or empty required field in execution_event: {field}")

        fill_status = execution_event["fill_status"].strip().upper()
        if fill_status not in {"FILLED", "PARTIALLY_FILLED", "REJECTED", "FAILED", "CANCELLED"}:
            raise ExecutionQualityMonitorError(f"Invalid fill_status: {execution_event['fill_status']}")

        # 1. Parse Latency Quality
        latency_ms = self._parse_latency(execution_event, mkt_met)
        latency_score = round(max(0.0, min(100.0, 100.0 - (latency_ms / 10.0))), 4)

        # 2. Parse Slippage Quality
        slippage_bps = self._parse_slippage(execution_event, mkt_met)
        slippage_score = round(max(0.0, min(100.0, 100.0 - slippage_bps * 2.0)), 4)

        # 3. Parse Spread Quality
        spread_bps = self._parse_spread(execution_event, mkt_met)
        spread_score = round(max(0.0, min(100.0, 100.0 - spread_bps * 2.0)), 4)

        # 4. Fill Status Quality
        if fill_status == "FILLED":
            fill_score = 100.0
        elif fill_status == "PARTIALLY_FILLED":
            fill_score = 60.0
        else:
            fill_score = 0.0

        # Compute Aggregated Score
        if fill_status in {"REJECTED", "FAILED"}:
            # Failed or rejected fills score poorly
            execution_quality_score = 0.0
        else:
            total_score = slippage_score + spread_score + latency_score + fill_score
            execution_quality_score = round(total_score / 4.0, 4)

        # Determine Grade
        execution_grade = self._get_grade(execution_quality_score)

        # Determine Strengths and Weaknesses
        dimension_scores = {
            "slippage": slippage_score,
            "spread": spread_score,
            "latency": latency_score,
            "fill": fill_score,
        }
        strengths = self._get_strengths(dimension_scores, fill_status)
        weaknesses = self._get_weaknesses(dimension_scores, fill_status)

        return {
            "execution_quality_score": execution_quality_score,
            "execution_grade": execution_grade,
            "slippage_bps": slippage_bps,
            "latency_ms": latency_ms,
            "spread_bps": spread_bps,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
        }

    def _parse_latency(self, execution_event: Mapping[str, Any], mkt_met: Mapping[str, Any]) -> float:
        # Check direct latency_ms
        if "latency_ms" in execution_event:
            return self._to_float(execution_event["latency_ms"], "latency_ms")
        if "latency_ms" in mkt_met:
            return self._to_float(mkt_met["latency_ms"], "latency_ms")

        # Fallback to order_latency or latency in seconds
        for field in ["order_latency", "latency"]:
            if field in execution_event:
                return self._to_float(execution_event[field], field) * 1000.0
            if field in mkt_met:
                return self._to_float(mkt_met[field], field) * 1000.0

        raise ExecutionQualityMonitorError("Latency metric could not be determined from inputs")

    def _parse_slippage(self, execution_event: Mapping[str, Any], mkt_met: Mapping[str, Any]) -> float:
        # Check direct slippage_bps
        if "slippage_bps" in execution_event:
            return self._to_float(execution_event["slippage_bps"], "slippage_bps")
        if "slippage_bps" in mkt_met:
            return self._to_float(mkt_met["slippage_bps"], "slippage_bps")

        # Calculate using prices
        if "expected_entry_price" in execution_event and "actual_fill_price" in execution_event:
            expected = self._to_float(execution_event["expected_entry_price"], "expected_entry_price")
            actual = self._to_float(execution_event["actual_fill_price"], "actual_fill_price")
            if expected <= 0.0:
                raise ExecutionQualityMonitorError("expected_entry_price must be positive")
            if actual < 0.0:
                raise ExecutionQualityMonitorError("actual_fill_price cannot be negative")
            return round(abs(actual - expected) / expected * 10000.0, 4)

        raise ExecutionQualityMonitorError("Slippage basis points could not be determined from inputs")

    def _parse_spread(self, execution_event: Mapping[str, Any], mkt_met: Mapping[str, Any]) -> float:
        # Check direct spread_bps
        if "spread_bps" in execution_event:
            return self._to_float(execution_event["spread_bps"], "spread_bps")
        if "spread_bps" in mkt_met:
            return self._to_float(mkt_met["spread_bps"], "spread_bps")

        # Fallback to spread / spread_at_execution
        spread: float | None = None
        for field in ["spread", "spread_at_execution"]:
            if field in execution_event:
                spread = self._to_float(execution_event[field], field)
                break
            if field in mkt_met:
                spread = self._to_float(mkt_met[field], field)
                break

        if spread is None:
            raise ExecutionQualityMonitorError("Spread metric could not be determined from inputs")

        if spread < 0.0:
            raise ExecutionQualityMonitorError("Spread cannot be negative")

        # Convert to bps if we have a price
        price: float | None = None
        if "expected_entry_price" in execution_event:
            price = self._to_float(execution_event["expected_entry_price"], "expected_entry_price")
        elif "actual_fill_price" in execution_event:
            price = self._to_float(execution_event["actual_fill_price"], "actual_fill_price")

        if price is not None and price > 0.0:
            return round(spread / price * 10000.0, 4)

        raise ExecutionQualityMonitorError("Spread basis points could not be calculated (missing entry price)")

    @staticmethod
    def _to_float(val: Any, field_name: str) -> float:
        if val is None:
            raise ExecutionQualityMonitorError(f"Field {field_name} is None")
        if isinstance(val, bool):
            raise ExecutionQualityMonitorError(f"Field {field_name} must be numeric, not bool")
        try:
            return float(val)
        except (ValueError, TypeError) as exc:
            raise ExecutionQualityMonitorError(f"Field {field_name} must be numeric") from exc

    @staticmethod
    def _get_grade(score: float) -> str:
        if score >= 90.0:
            return "A"
        elif score >= 80.0:
            return "B"
        elif score >= 70.0:
            return "C"
        elif score >= 60.0:
            return "D"
        else:
            return "F"

    @staticmethod
    def _get_strengths(scores: dict[str, float], fill_status: str) -> list[str]:
        strengths: list[str] = []
        if scores["slippage"] >= 85.0:
            strengths.append("Low Slippage")
        if scores["spread"] >= 85.0:
            strengths.append("Tight Bid-Ask Spread")
        if scores["latency"] >= 85.0:
            strengths.append("Low Execution Latency")
        if fill_status == "FILLED":
            strengths.append("Complete Fill")
        return strengths

    @staticmethod
    def _get_weaknesses(scores: dict[str, float], fill_status: str) -> list[str]:
        weaknesses: list[str] = []
        if fill_status in {"REJECTED", "FAILED", "CANCELLED"}:
            weaknesses.append("Failed/Rejected Fill")
            # If rejected or failed, slippage/spread/latency are irrelevant or bad
            if scores["slippage"] < 60.0:
                weaknesses.append("High Slippage")
            if scores["spread"] < 60.0:
                weaknesses.append("Wide Bid-Ask Spread")
            if scores["latency"] < 60.0:
                weaknesses.append("High Execution Latency")
        else:
            if scores["slippage"] < 60.0:
                weaknesses.append("High Slippage")
            if scores["spread"] < 60.0:
                weaknesses.append("Wide Bid-Ask Spread")
            if scores["latency"] < 60.0:
                weaknesses.append("High Execution Latency")
            if fill_status == "PARTIALLY_FILLED":
                weaknesses.append("Incomplete Fill")
        return weaknesses
