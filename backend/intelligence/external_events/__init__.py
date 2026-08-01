"""MI-EXT-001 external events package — extends GIE/intel; advisory-only."""

from backend.intelligence.external_events.catalogue import SourceCatalogue
from backend.intelligence.external_events.constants import TrustTier
from backend.intelligence.external_events.models import ExternalEvent
from backend.intelligence.external_events.pipeline import ExternalEventPipeline

__all__ = [
    "ExternalEvent",
    "ExternalEventPipeline",
    "SourceCatalogue",
    "TrustTier",
]
