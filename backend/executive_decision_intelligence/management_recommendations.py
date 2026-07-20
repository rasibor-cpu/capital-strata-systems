"""Phase 179 — management recommendations (advisory text; never trading instructions)."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_prioritizer import dedupe_by_code


_BANNED_TOKENS = ("buy ", "sell ", "execute order", "place order", "liquidate", "short ")


def _sanitize_text(text: str) -> str:
    lower = text.lower()
    for token in _BANNED_TOKENS:
        if token in lower:
            return "Review upstream advisory management actions (trading verbs suppressed)."
    return text


def build_management_recommendations(
    *,
    priorities: list[dict[str, Any]] | None,
    risks: list[dict[str, Any]] | None,
    opportunities: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for src, kind in (
        (priorities or [], "priority"),
        (risks or [], "risk"),
        (opportunities or [], "opportunity"),
    ):
        for entry in src[:5]:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("code") or "")
            if not code or code.startswith("no_material") or code.startswith("insufficient"):
                continue
            title = _sanitize_text(str(entry.get("title") or code))
            items.append(
                {
                    "code": f"rec:{code}",
                    "title": title,
                    "reason": str(entry.get("reason") or ""),
                    "priority": entry.get("priority") or "MEDIUM",
                    "kind": kind,
                    "source": entry.get("source") or "edi",
                    "confidence": entry.get("confidence", 0.7),
                    "advisory_only": True,
                    "trading_impact": False,
                    "executable": False,
                }
            )

    if not items:
        items.append(
            {
                "code": "rec:maintain_observation",
                "title": "Maintain observation mode until upstream reporting signals stabilize.",
                "reason": "No actionable priority/risk/opportunity items available.",
                "priority": "INFO",
                "kind": "observation",
                "source": "edi",
                "confidence": 0.5,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    return dedupe_by_code(items)
