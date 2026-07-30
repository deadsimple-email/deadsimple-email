"""Dead Simple Email SDK exceptions."""

from __future__ import annotations


class DeadSimpleError(Exception):
    """Base exception for all Dead Simple API errors."""

    def __init__(self, message: str, code: str = "", status_code: int = 0, details: list | None = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


class AuthenticationError(DeadSimpleError):
    """Raised when API key is invalid or missing."""
    pass


class ValidationError(DeadSimpleError):
    """Raised when request parameters are invalid."""
    pass


class NotFoundError(DeadSimpleError):
    """Raised when a resource is not found."""
    pass


class RateLimitError(DeadSimpleError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 0, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)
