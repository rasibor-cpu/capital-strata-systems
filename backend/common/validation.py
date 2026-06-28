"""
CSS Validation Utilities
"""

from typing import Any, Dict, List
from backend.common.exceptions import ValidationException

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Validate that required keys are present and not None in a dictionary.
    
    Responsibility: Check existence of properties.
    Dependencies: ValidationException
    Thread-safety: Stateless helper, safe.
    """
    for field in required_fields:
        if field not in data:
            raise ValidationException(f"Missing required field: {field}")
        if data[field] is None:
            raise ValidationException(f"Required field {field} cannot be None")

def validate_field_type(field_name: str, value: Any, expected_type: type) -> None:
    """
    Validate that a field matches its expected type.
    
    Responsibility: Enforce strict type typing on deserialized objects.
    Dependencies: ValidationException
    Thread-safety: Stateless helper, safe.
    """
    if not isinstance(value, expected_type):
        raise ValidationException(
            f"Field {field_name} has invalid type: {type(value).__name__}. Expected: {expected_type.__name__}"
        )
