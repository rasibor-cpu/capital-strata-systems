"""CSS live-data shadow paper runner.

Observation-only harness: real public market prices are fed through the existing
V1 signal engine and governance gates, and every decision is written to an
append-only, hash-chained journal. Fills are explicitly simulated. This package
contains no broker order-submission capability.
"""

SCHEMA_VERSION = "css.shadow_paper.v1"
