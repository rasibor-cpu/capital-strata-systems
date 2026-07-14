from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    assert_enterprise_safe,
    stable_id,
)


class OptionsIncomeExplainabilityAdapter:
    def adapt(self, explanations: Sequence[Mapping[str, Any]], *, audit_reference: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for explanation in explanations:
            item = dict(explanation)
            assert_enterprise_safe(item)
            decision = str(item.get("decision", "UNKNOWN")).upper()
            entity = str(item.get("entity", SUBSYSTEM_ID))
            rows.append(
                {
                    "explanation_id": str(item.get("explanation_id") or stable_id("oi-explain", decision, entity, item)),
                    "payload_version": PAYLOAD_VERSION,
                    "subsystem": SUBSYSTEM_ID,
                    "decision": decision,
                    "summary": str(item.get("summary", "")),
                    "primary_reasons": [str(value) for value in item.get("primary_reasons", [])],
                    "supporting_metrics": dict(item.get("supporting_metrics", {})) if isinstance(item.get("supporting_metrics"), Mapping) else {},
                    "rules_evaluated": [str(value) for value in item.get("rules_evaluated", [])],
                    "warnings": [str(value) for value in item.get("warnings", [])],
                    "unavailable_inputs": [str(value) for value in item.get("unavailable_inputs", [])],
                    "source_modules": [str(value) for value in item.get("source_modules", [])],
                    "correlation_id": stable_id("oi-explain-correlation", decision, entity),
                    "audit_reference": str(audit_reference or ""),
                    **ENTERPRISE_SAFE_FLAGS,
                }
            )
        rows.sort(key=lambda row: (row["decision"], row["explanation_id"]))
        return rows


def adapt_options_income_explanations(explanations: Sequence[Mapping[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return OptionsIncomeExplainabilityAdapter().adapt(explanations, **kwargs)


__all__ = ["OptionsIncomeExplainabilityAdapter", "adapt_options_income_explanations"]
