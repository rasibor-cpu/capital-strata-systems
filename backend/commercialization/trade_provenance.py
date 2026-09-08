from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class AttributionClass(str, Enum):
    """
    Canonical origin/attribution class for a CSS-visible trade.

    Attribution must be established from contemporaneous evidence.
    It must never be assigned retrospectively based on whether a
    trade won or lost.
    """

    CSS_ADVISED = "CSS_ADVISED"
    CSS_ADVISED_ACCEPTED = "CSS_ADVISED_ACCEPTED"
    CSS_MODIFIED = "CSS_MODIFIED"
    CUSTOMER_DIRECTED = "CUSTOMER_DIRECTED"
    EXTERNAL = "EXTERNAL"


class MandateCompliance(str, Enum):
    """
    Relationship between the executed trade and the CSS recommendation.
    """

    COMPLIANT = "COMPLIANT"
    MODIFIED = "MODIFIED"
    OVERRIDDEN = "OVERRIDDEN"
    OUTSIDE_CSS = "OUTSIDE_CSS"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class TradeProvenance:
    """
    Immutable COM-002A attribution contract.

    A trade is eligible to enter future CSS performance-attribution
    accounting only when CSS advice can be identified and the executed
    trade remained compliant with that advice.

    This object DOES NOT:
    - calculate investment performance;
    - calculate a performance fee;
    - permit real fee accrual;
    - collect a fee;
    - modify client funds;
    - grant execution authority.
    """

    trade_id: str
    attribution_class: AttributionClass
    mandate_compliance: MandateCompliance

    advice_id: Optional[str] = None
    recommendation_timestamp: Optional[str] = None
    acceptance_timestamp: Optional[str] = None
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        trade_id = self.trade_id.strip()

        if not trade_id:
            raise ValueError("trade_id is required")

        if trade_id != self.trade_id:
            raise ValueError("trade_id must be canonical and whitespace-free")

        if self.advice_id is not None:
            advice_id = self.advice_id.strip()

            if not advice_id:
                raise ValueError("advice_id cannot be blank")

            if advice_id != self.advice_id:
                raise ValueError(
                    "advice_id must be canonical and whitespace-free"
                )

        if self.attribution_class == AttributionClass.CSS_ADVISED_ACCEPTED:
            if not self.advice_id:
                raise ValueError(
                    "CSS_ADVISED_ACCEPTED requires advice_id"
                )

            if self.mandate_compliance != MandateCompliance.COMPLIANT:
                raise ValueError(
                    "CSS_ADVISED_ACCEPTED requires COMPLIANT mandate"
                )

            if not self.acceptance_timestamp:
                raise ValueError(
                    "CSS_ADVISED_ACCEPTED requires acceptance_timestamp"
                )

            if not self.evidence_refs:
                raise ValueError(
                    "CSS_ADVISED_ACCEPTED requires evidence"
                )

    @property
    def css_performance_attributable(self) -> bool:
        """
        Fail-closed gate for later COM-002B accounting.

        True means only that the trade may be considered by the future
        performance-attribution engine. It does not mean a fee is earned.
        """

        return (
            self.attribution_class
            == AttributionClass.CSS_ADVISED_ACCEPTED
            and self.mandate_compliance
            == MandateCompliance.COMPLIANT
            and bool(self.advice_id)
            and bool(self.acceptance_timestamp)
            and bool(self.evidence_refs)
        )

    @property
    def customer_directed(self) -> bool:
        return self.attribution_class in {
            AttributionClass.CUSTOMER_DIRECTED,
            AttributionClass.CSS_MODIFIED,
            AttributionClass.EXTERNAL,
        }

    @property
    def shadow_fee_attribution_eligible(self) -> bool:
        """
        COM-002A establishes attribution eligibility only.

        COM-002B/C/D will additionally require verified P&L,
        loss recovery, high-water mark and hurdle calculations.
        """

        return self.css_performance_attributable

    @property
    def real_fee_collection_allowed(self) -> bool:
        """
        Regulatory fail-closed invariant.

        COM-002A can never authorize real fee collection.
        """

        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        """
        CSS cannot deduct customer funds under COM-002A.
        """

        return False

    @property
    def execution_authority(self) -> bool:
        """
        Provenance metadata never creates trading authority.
        """

        return False


def attribution_reason(
    provenance: TradeProvenance,
) -> str:
    """
    Stable human/audit explanation of attribution status.
    """

    if provenance.css_performance_attributable:
        return "css_advice_accepted_and_mandate_compliant"

    if provenance.attribution_class == AttributionClass.CSS_MODIFIED:
        return "customer_materially_modified_css_advice"

    if provenance.attribution_class == AttributionClass.CUSTOMER_DIRECTED:
        return "customer_originated_trade"

    if provenance.attribution_class == AttributionClass.EXTERNAL:
        return "activity_outside_css"

    if provenance.attribution_class == AttributionClass.CSS_ADVISED:
        return "css_advice_not_yet_authoritatively_accepted"

    return "performance_attribution_not_established"
