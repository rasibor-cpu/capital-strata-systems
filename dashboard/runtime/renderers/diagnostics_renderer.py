from __future__ import annotations

from dashboard.runtime.render_contracts.diagnostics_render_contract import (
    DiagnosticsRenderContract,
)


class DiagnosticsRenderer:
    """
    PCNRASS-safe pure runtime diagnostics renderer.
    """

    def render(self, contract: DiagnosticsRenderContract) -> str:
        if not contract.has_items():
            return ""

        lines = [
            "==============================",
            " RUNTIME DIAGNOSTICS",
            "==============================",
        ]

        lines.extend(self._section("Messages", contract.messages))
        lines.extend(self._section("Warnings", contract.warnings))
        lines.extend(self._section("Hydration Gaps", contract.hydration_gaps))
        lines.extend(self._section("Builder Failures", contract.builder_failures))
        lines.extend(self._section("Governance Alerts", contract.governance_alerts))
        lines.append("==============================")

        return "\n".join(lines)

    @staticmethod
    def _section(title: str, values: tuple[str, ...]) -> list[str]:
        lines = [f"{title}:"]

        if not values:
            lines.append("  NONE")
            lines.append("")
            return lines

        lines.extend(f"  {value}" for value in values)
        lines.append("")

        return lines
