from __future__ import annotations

from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeRuntimeValidatorError(ValueError):
    """Raised when certification runtime safety validation fails closed."""


class OptionsIncomeRuntimeValidator:
    def validate(self, payload: Mapping[str, Any], *, section: str = "options_income") -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise OptionsIncomeRuntimeValidatorError("runtime payload must be a mapping")
        blockers: list[str] = []
        warnings: list[str] = []
        _validate_node(payload, path=section, blockers=blockers, warnings=warnings)
        status = "FAIL" if blockers else ("WARNING" if warnings else "PASS")
        return {
            "section": section,
            "status": status,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "paper_only": True,
            **SAFE_FLAGS,
        }


def _validate_node(value: Any, *, path: str, blockers: list[str], warnings: list[str]) -> None:
    if isinstance(value, Mapping):
        if "execution_allowed" in value and value.get("execution_allowed") is not False:
            blockers.append(f"{path}:execution_enabled")
        if "live_trading_blocked" in value and value.get("live_trading_blocked") is not True:
            blockers.append(f"{path}:live_trading_not_blocked")
        if "broker_execution_armed" in value and value.get("broker_execution_armed") is not False:
            blockers.append(f"{path}:broker_execution_armed")
        if "advisory_only" in value and value.get("advisory_only") is not True:
            blockers.append(f"{path}:not_advisory_only")
        if "paper_only" in value and value.get("paper_only") is not True:
            blockers.append(f"{path}:not_paper_only")
        if any(key in value for key in ("execution_allowed", "live_trading_blocked", "broker_execution_armed")):
            for key, expected in SAFE_FLAGS.items():
                if value.get(key) is not expected:
                    blockers.append(f"{path}:missing_or_invalid_{key}")
        for key, child in value.items():
            _validate_node(child, path=f"{path}.{key}", blockers=blockers, warnings=warnings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_node(child, path=f"{path}[{index}]", blockers=blockers, warnings=warnings)


__all__ = ["OptionsIncomeRuntimeValidator", "OptionsIncomeRuntimeValidatorError"]
