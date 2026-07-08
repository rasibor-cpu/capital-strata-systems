from __future__ import annotations

from typing import Any, Mapping
from backend.portfolio.utils import safe_float


class CommitteeExplainability:
    """Generate natural-language explainability comments for investment committee decisions."""

    def generate_comments(
        self,
        portfolio: Mapping[str, Any],
        scores: dict[str, dict[str, float]],
        context: Mapping[str, Any] | None = None,
    ) -> list[str]:
        comments = []
        ctx = context or {}
        p_name = portfolio.get("name", "Recommended")

        # CIO Comment
        cio_scores = scores.get("CIO", {})
        quality = safe_float(portfolio.get("portfolio_quality_score", 0.0))
        if quality >= 85.0:
            comments.append(
                f"The Chief Investment Officer prefers the {p_name} portfolio due to superior long-term portfolio quality of {quality:.1f}%."
            )
        else:
            comments.append(
                f"The Chief Investment Officer notes that the {p_name} portfolio quality of {quality:.1f}% meets strategic allocation parameters."
            )

        # CRO Comment
        cro_scores = scores.get("CRO", {})
        con = safe_float(portfolio.get("concentration_score", 0.0))
        dd = safe_float(portfolio.get("expected_drawdown", 0.0))
        resilience = safe_float(portfolio.get("resilience_score", 0.0))
        if con > 50.0:
            comments.append(f"The Chief Risk Officer recommends reducing concentration risk (current score: {con:.1f}%).")
        elif dd > 8.0:
            comments.append(f"The Chief Risk Officer warns that expected drawdown of {dd:.1f}% exceeds optimal risk-tolerance limits.")
        else:
            comments.append(f"The Chief Risk Officer approves the {p_name} portfolio due to its strong resilience score of {resilience:.1f}%.")

        # PM Comment
        pm_scores = scores.get("PM", {})
        ret = safe_float(portfolio.get("expected_return", 0.0))
        div = safe_float(portfolio.get("diversification_score", 0.0))
        if ret >= 15.0:
            comments.append(f"The Portfolio Manager supports the {p_name} portfolio's strong expected return of {ret:.1f}%.")
        else:
            comments.append(f"The Portfolio Manager approves the {p_name} portfolio's diversification score of {div:.1f}%.")

        # Trading Comment
        trading_scores = scores.get("Trading", {})
        liq = trading_scores.get("Liquidity", 75.0)
        broker_status = str(ctx.get("broker_health", "GREEN")).upper()
        if broker_status != "GREEN":
            comments.append(f"The Head of Trading flags operational concerns due to degraded broker health ({broker_status}).")
        elif liq < 60.0:
            comments.append(f"The Head of Trading warns that liquidity score is low ({liq:.1f}%), indicating potential execution slippage.")
        else:
            comments.append("The Head of Trading confirms execution practicality and liquidity parameters are within limits.")

        # Quant Comment
        quant_scores = scores.get("Quant", {})
        conf = quant_scores.get("Confidence", 75.0)
        if conf < 55.0:
            comments.append(f"The Quantitative Research Lead has low confidence in {p_name} because of insufficient evidence.")
        else:
            comments.append(f"The Quantitative Research Lead confirms statistical edge with {conf:.1f}% model confidence.")

        # Compliance Comment
        compliance_scores = scores.get("Compliance", {})
        gov = compliance_scores.get("Governance", 0.0)
        if gov >= 90.0:
            comments.append("The Governance & Compliance officer confirms strict adherence to advisory execution boundaries.")
        else:
            comments.append("The Governance & Compliance officer REJECTS the portfolio because execution gates are improperly armed.")

        return comments
