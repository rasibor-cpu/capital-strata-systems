"""Capital Allocation Intelligence Engine (CAIE) advisory primitives."""

from .opportunity_proposal import OpportunityProposal
from .opportunity_validator import OpportunityValidationResult, validate_opportunity_proposal

__all__ = [
    "OpportunityProposal",
    "OpportunityValidationResult",
    "validate_opportunity_proposal",
]
