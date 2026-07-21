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


def sanitize_error_message(exc: BaseException) -> str:
    text = f"{type(exc).__name__}:{exc}"
    lowered = text.lower()
    for needle in ("token", "secret", "password", "authorization", "bearer", "refresh"):
        if needle in lowered:
            return f"{type(exc).__name__}:[redacted]"
    return text[:200]


__all__ = [
    "AuthenticationNotActivatedError",
    "ConfigurationRequiredError",
    "ProviderUnavailableError",
    "QuestradeAdvisoryError",
    "RateLimitError",
    "SymbolUnsupportedError",
    "sanitize_error_message",
]
