from __future__ import annotations

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
    This adapter is PREPARATION ONLY.
    It is not yet wired into runtime execution.
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

        translated_candidate = self._translate_candidate(candidate)

        translated_session = self._translate_session(
            session=session,
            role_profile=role_profile,
        )

        translated_portfolio = portfolio_state or {
            "CRYPTO": 0,
            "FX": 0,
            "FUTURES": 0,
            "OPTIONS": 0,
        }

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
    ) -> Dict[str, Any]:

        probability = float(
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

        cost = float(
            candidate.get(
                "cost",
                0.0,
            )
        )

        return {
            "asset_class": str(candidate.get("asset_class", "UNKNOWN")).upper(),
            "symbol": str(candidate.get("symbol", "UNKNOWN")),
            "expected_value": expected_value,
            "cost": cost,
            "probability": probability,
        }

    def _translate_session(
        self,
        *,
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
    ) -> Dict[str, Any]:

        role = str(
            role_profile.get(
                "role",
                session.get("role", "TRADER"),
            )
        ).upper()

        created = session.get("created")

        if created is None:
            created = 0

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

        return {
            "approved": approved,
            "reason": reason,
        }