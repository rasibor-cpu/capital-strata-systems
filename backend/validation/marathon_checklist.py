from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarathonCheckResult:
    check_name: str
    passed: bool
    required: bool = True
    warning: bool = False
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarathonChecklist:
    results: tuple[MarathonCheckResult, ...]

    def passed_checks(self) -> list[str]:
        return [result.check_name for result in self.results if result.passed]

    def failed_checks(self) -> list[str]:
        return [result.check_name for result in self.results if result.required and not result.passed]

    def warnings(self) -> list[str]:
        return [result.message or result.check_name for result in self.results if result.warning]

    def recommendations(self) -> list[str]:
        recommendations: list[str] = []
        for result in self.results:
            if result.required and not result.passed:
                detail = result.message or "mandatory check failed"
                recommendations.append(f"Resolve {result.check_name}: {detail}")
            elif result.warning:
                detail = result.message or "review recommended"
                recommendations.append(f"Review {result.check_name}: {detail}")
        return recommendations

    def go_no_go(self) -> bool:
        return not any(result.required and not result.passed for result in self.results)
