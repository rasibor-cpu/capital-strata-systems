"""Questrade advisory error taxonomy (no credential leakage)."""

from __future__ import annotations


class QuestradeAdvisoryError(Exception):
    """Base advisory error — messages must be sanitized."""

    code = "QUESTRADE_ADVISORY_ERROR"

    def __init__(self, message: str = "questrade_advisory_error", *, code: str | None = None) -> None:
        self.code = code or self.code
        super().__init__(str(message))


class ConfigurationRequiredError(QuestradeAdvisoryError):
    code = "CONFIGURATION_REQUIRED"

    def __init__(self, message: str = "CONFIGURATION_REQUIRED") -> None:
        super().__init__(message, code=self.code)


class AuthenticationNotActivatedError(QuestradeAdvisoryError):
    code = "AUTHENTICATION_NOT_ACTIVATED"


class RateLimitError(QuestradeAdvisoryError):
    code = "RATE_LIMIT"


class SymbolUnsupportedError(QuestradeAdvisoryError):
    code = "SYMBOL_UNSUPPORTED"


class ProviderUnavailableError(QuestradeAdvisoryError):
    code = "PROVIDER_UNAVAILABLE"


class InvalidGrantError(QuestradeAdvisoryError):
    code = "INVALID_GRANT"


class AuthorizationRevokedError(QuestradeAdvisoryError):
    code = "AUTHORIZATION_REVOKED"


class UnsafeApiServerError(QuestradeAdvisoryError):
    code = "API_SERVER_REJECTED"


def sanitize_error_message(exc: BaseException) -> str:
    return f"{type(exc).__name__}:[redacted]"


__all__ = [
    "AuthenticationNotActivatedError",
    "AuthorizationRevokedError",
    "InvalidGrantError",
    "ConfigurationRequiredError",
    "ProviderUnavailableError",
    "QuestradeAdvisoryError",
    "RateLimitError",
    "SymbolUnsupportedError",
    "UnsafeApiServerError",
    "sanitize_error_message",
]
