"""
CSS Serialization Helpers
"""

import json
from typing import Any, Dict, Type, TypeVar
from backend.common.exceptions import PersistenceException

T = TypeVar("T")

class JSONSerializable:
    """
    Interface mixin to provide standardized JSON and dictionary serialization.
    
    Responsibility: Enforce strict implementation of standard conversions.
    Dependencies: PersistenceException
    Thread-safety: Stateless methods, safe.
    """
    def to_dict(self) -> Dict[str, Any]:
        """Convert object instance variables to a dictionary."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Construct object from a dictionary."""
        raise NotImplementedError

    def to_json(self) -> str:
        """Convert object to a serialized JSON string."""
        try:
            return json.dumps(self.to_dict())
        except Exception as e:
            raise PersistenceException(f"Serialization failed: {e}")

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """Construct object from a serialized JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except Exception as e:
            raise PersistenceException(f"Deserialization failed: {e}")
