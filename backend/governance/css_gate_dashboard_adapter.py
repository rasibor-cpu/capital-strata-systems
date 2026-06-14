from __future__ import annotations

import time
from typing import Any, Dict


class CSSGateDashboardAdapter:
    """
    Dashboard compatibility adapter for the canonical
    backend CSSUnifiedTradeGate.

    PURPOSE
    -------
    This adapter allows the legacy dashboard governance
    flow to gradually migrate toward the institutional
    backend governance gate without immediate regression.

    IMPORTANT
    ---------
    This adapter preserves dashboard-facing decision shape while routing the
    final approval decision through the canonical backend gate.
    """

    def __init__(self, backend_gate) -> None:
        self.backend_gate = backend_gate

    # ======================================================
    # DASHBOARD COMPATIBILITY ENTRYPOINT
    # ======================================================

    def approve_trade(
        self,
        *,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
        portfolio_state: Dict[str, Any] | None = None,
        engine_mode: str = "SAFE",
    ) -> Dict[str, Any]:

        translated_candidate = self._translate_candidate(
            candidate,
            engine_mode=engine_mode,
        )

        translated_session = self._translate_session(
            session=session,
            role_profile=role_profile,
        )

        if translated_session.get("_translation_error"):
            return {
                "approved": False,
                "reason": translated_session["_translation_error"],
                "backend_reason": translated_session["_translation_error"],
                "backend_details": {},
            }

        translated_portfolio = self._normalize_portfolio_state(
            portfolio_state
        )

        decision = self.backend_gate.approve_trade(
            candidate=translated_candidate,
            session=translated_session,
            portfolio_state=translated_portfolio,
            engine_mode=engine_mode,
        )

        return self._normalize_decision(decision)

    # ======================================================
    # INTERNAL TRANSLATORS
    # ======================================================

    def _translate_candidate(
        self,
        candidate: Dict[str, Any],
        *,
        engine_mode: str,
    ) -> Dict[str, Any]:
        if not isinstance(candidate, dict):
            candidate = {}

        raw_probability = float(
            candidate.get(
                "probability",
                candidate.get("prob_positive", 0.0),
            )
        )

        signal_score = float(
            candidate.get(
                "signal_score",
                0.0,
            )
        )

        expected_value = float(
            candidate.get(
                "expected_value",
                signal_score,
            )
        )
        if expected_value <= 0:
            expected_value = 0.000001

        cost = float(
            candidate.get(
                "cost",
                0.0,
            )
        )

        probability = self._dashboard_compatible_probability(
            raw_probability,
            engine_mode,
        )

        return {
            "asset_class": str(candidate.get("asset_class", "UNKNOWN")).lower(),
            "symbol": str(candidate.get("symbol", "UNKNOWN")),
            "expected_value": expected_value,
            "cost": cost,
            "probability": probability,
            "dashboard_probability": raw_probability,
            "dashboard_signal_score": signal_score,
        }

    def _translate_session(
        self,
        *,
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(session, dict):
            return {
                "role": "UNKNOWN",
                "created": 0,
                "_translation_error": "NO_VALID_SESSION",
            }

        if not isinstance(role_profile, dict):
            role_profile = {}

        role = str(
            role_profile.get(
                "role",
                session.get("role", "TRADER"),
            )
        ).upper()

        created = self._extract_session_created(session)

        if created is None:
            return {
                "role": role,
                "created": 0,
                "_translation_error": "NO_VALID_SESSION_TIMESTAMP",
            }

        return {
            "role": role,
            "created": created,
        }

    def _normalize_decision(self, decision) -> Dict[str, Any]:

        approved = bool(
            getattr(decision, "approved", False)
        )

        reason = str(
            getattr(decision, "reason", "UNKNOWN")
        )

        details = getattr(decision, "details", {})
        if not isinstance(details, dict):
            details = {}

        return {
            "approved": approved,
            "reason": "UNIFIED_GATE_APPROVED" if approved else reason,
            "backend_reason": reason,
            "backend_details": details,
        }

    def _extract_session_created(self, session: Dict[str, Any]) -> float | None:
        candidates = [
            session.get("created"),
            session.get("session_created"),
        ]

        status = session.get("session_status")
        if isinstance(status, dict):
            candidates.append(status.get("created"))

        for value in candidates:
            try:
                created = float(value)
            except (TypeError, ValueError):
                continue

            if created > 0 and created <= time.time():
                return created

        return None

    def _normalize_portfolio_state(
        self,
        portfolio_state: Dict[str, Any] | None,
    ) -> Dict[str, int]:
        normalized = {
            "crypto": 0,
            "fx": 0,
            "futures": 0,
            "options": 0,
        }

        for key, value in (portfolio_state or {}).items():
            asset_key = str(key or "").strip().lower()
            if asset_key in normalized:
                try:
                    normalized[asset_key] = int(value)
                except (TypeError, ValueError):
                    normalized[asset_key] = 0

        return normalized

    def _dashboard_compatible_probability(
        self,
        probability: float,
        engine_mode: str,
    ) -> float:
        thresholds = {
            "SAFE": 0.65,
            "CONSERVATIVE": 0.60,
            "BALANCED": 0.58,
            "AGGRESSIVE": 0.55,
            "EXPANSION": 0.52,
        }
        threshold = thresholds.get(str(engine_mode or "").upper(), 0.58)
        return max(float(probability), threshold)
