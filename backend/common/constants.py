from __future__ import annotations

"""
CSS Shared Constants

Declares defaults for versions and schema descriptors.
"""

DEFAULT_SCHEMA_VERSION = "1.0.0"

# Confidence scoring thresholds
CONFIDENCE_DEFAULT = 80.0
CONFIDENCE_WARNING_THRESHOLD = 70.0
CONFIDENCE_CRITICAL_THRESHOLD = 60.0

# Portfolio boundary warnings
PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD = 8.0
PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD = 50.0

# Health scoring sample defaults
DEFAULT_HEALTHY_SCORE = 85.0
DEFAULT_AMBER_SCORE = 60.0

# Broker infrastructure defaults
LATENCY_GREEN_MS = 250
LATENCY_AMBER_MS = 1000
STALE_QUOTE_SECONDS = 120
DRIFT_QUOTE_SECONDS = 30
