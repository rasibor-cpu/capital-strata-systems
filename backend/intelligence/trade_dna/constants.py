"""DIP-002 Trade DNA version constants."""

from __future__ import annotations

# Canonical immutable fact schema for Trade DNA records.
SCHEMA_VERSION = "css.trade_dna.v1"

# Evidence custody envelope version (how sources are cited on a DNA record).
EVIDENCE_VERSION = "css.trade_dna.evidence.v1"

# Analysis / metric computation version family (Layer 2 — not stored in facts).
ANALYSIS_VERSION = "css.trade_dna.analysis.v1"

# Advisory conclusion envelope version (Layer 3 — never facts).
ADVISORY_VERSION = "css.trade_dna.advisory.v1"

# Supported schema versions for deserialize / compatibility checks.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({SCHEMA_VERSION})

# Minimum known schema versions that older readers must tolerate as readable.
COMPATIBLE_SCHEMA_PREFIX = "css.trade_dna.v"

LAYER_FACTS = "facts"
LAYER_DERIVED = "derived"
LAYER_ADVISORY = "advisory"

# Context availability semantics (never treat bare UNKNOWN as observed truth).
FIELD_UNAVAILABLE = "UNAVAILABLE"
FIELD_OBSERVED_UNKNOWN = "OBSERVED_UNKNOWN"

# Capture outbox statuses (durable reconciliation markers).
OUTBOX_PENDING_DNA = "PENDING_DNA"
OUTBOX_DNA_COMMITTED = "DNA_COMMITTED"
OUTBOX_COMPLETE = "COMPLETE"
OUTBOX_CONFLICT = "CONFLICT"
