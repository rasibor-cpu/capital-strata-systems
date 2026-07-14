from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from backend.options.options_income_end_to_end_validator import OptionsIncomeEndToEndValidator
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeReplayValidatorError(ValueError):
    """Raised when deterministic replay validation fails closed."""


class OptionsIncomeReplayValidator:
    def validate(self, scenario_factory: Callable[[], Mapping[str, Any]] | None = None) -> dict[str, Any]:
        factory = scenario_factory or (lambda: OptionsIncomeEndToEndValidator().validate())
        first = dict(factory())
        second = dict(factory())
        first_hash = _stable_hash(first)
        second_hash = _stable_hash(second)
        match = first_hash == second_hash
        return {
            "status": "PASS" if match else "FAIL",
            "same_inputs": True,
            "same_outputs": match,
            "same_ordering": match,
            "same_certification": first.get("status") == second.get("status"),
            "first_hash": first_hash,
            "second_hash": second_hash,
            "blockers": [] if match else ["replay_mismatch"],
            "paper_only": True,
            **SAFE_FLAGS,
        }


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


__all__ = ["OptionsIncomeReplayValidator", "OptionsIncomeReplayValidatorError"]
