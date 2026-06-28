"""
CSS Schema Versioning Utilities
"""

from backend.common.exceptions import ValidationException
from backend.common.constants import DEFAULT_SCHEMA_VERSION

def validate_schema_version(schema_version: str, expected_version: str = DEFAULT_SCHEMA_VERSION) -> None:
    """
    Validate that the schema version matches expected formats and major version increments.
    
    Responsibility: Check compatibility index of incoming dictionaries.
    Dependencies: ValidationException, DEFAULT_SCHEMA_VERSION
    Thread-safety: Stateless helper, safe.
    """
    if not schema_version:
        raise ValidationException("schema_version is missing")
    if not isinstance(schema_version, str):
        raise ValidationException("schema_version must be a string")
    try:
        actual_major = int(schema_version.split(".")[0])
        expected_major = int(expected_version.split(".")[0])
        if actual_major != expected_major:
            raise ValidationException(
                f"Incompatible schema version: {schema_version}. Expected: {expected_version}"
            )
    except (ValueError, IndexError):
        raise ValidationException(f"Invalid schema version format: {schema_version}")
