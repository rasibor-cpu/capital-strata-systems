"""
CSS Enterprise Exception Hierarchy

Houses all standardized, domain-specific exception types across the repository.
"""

class CSSException(Exception):
    """Base exception for all Capital Strata Systems (CSS) errors."""
    pass

class ValidationException(CSSException):
    """Raised when an object fails input validation checks."""
    pass

class PersistenceException(CSSException):
    """Raised during database or file-based operations."""
    pass

class ConfigurationException(CSSException):
    """Raised for configuration validation or loading errors."""
    pass

class EnterpriseEventException(CSSException):
    """Raised for Event Bus and model exceptions."""
    pass

class NotificationException(CSSException):
    """Raised for Notification delivery and queue errors."""
    pass

class ReportingException(CSSException):
    """Raised for Report generation and archiving errors."""
    pass

class OperationsException(CSSException):
    """Raised for Operational diagnostics and timelines errors."""
    pass
