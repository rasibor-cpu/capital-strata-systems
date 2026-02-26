"""
Schema Registry
Capital Strata Systems – Phase 17C

Single source of truth for report schema versions.
Prevents silent drift.
"""

SCHEMA_REGISTRY = {
    "CSS_MONTH_END_V1": "v1.0",
    "CSS_YEAR_END_V1": "v1.0",
    "GLOBAL_REPORT_ENVELOPE": "v1.0",
}


def get_schema_version(schema_name: str) -> str:
    if schema_name not in SCHEMA_REGISTRY:
        raise ValueError(f"Unknown schema: {schema_name}")
    return SCHEMA_REGISTRY[schema_name]