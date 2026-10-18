"""Application-specific exceptions and error hierarchy."""

from typing import Any


class AppException(Exception):
    """Base application exception mapped to structured JSON error responses."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class UnauthorizedError(AppException):
    """Exception raised for unauthenticated requests or invalid credentials (401)."""

    def __init__(
        self,
        code: str = "unauthorized",
        message: str = "Authentication required or credentials invalid",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=401, code=code, message=message, details=details)


class ForbiddenError(AppException):
    """Exception raised for unauthorized actions due to role or permission restrictions (403)."""

    def __init__(
        self,
        code: str = "forbidden",
        message: str = "You do not have permission to perform this action",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=403, code=code, message=message, details=details)


class NotFoundError(AppException):
    """Exception raised when a requested resource is not found or not visible (404)."""

    def __init__(
        self,
        code: str = "not_found",
        message: str = "The requested resource was not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=404, code=code, message=message, details=details)


class ConflictError(AppException):
    """Exception raised for resource conflicts or business rule state violations (409)."""

    def __init__(
        self,
        code: str = "conflict",
        message: str = "Conflict with current resource state",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=409, code=code, message=message, details=details)


class FileTooLargeError(AppException):
    """Exception raised when uploaded file exceeds size limits (413)."""

    def __init__(
        self,
        code: str = "file_too_large",
        message: str = "Uploaded file exceeds maximum allowed size",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=413, code=code, message=message, details=details)


class UnsupportedMediaTypeError(AppException):
    """Exception raised when uploaded file format is unsupported (415)."""

    def __init__(
        self,
        code: str = "unsupported_media_type",
        message: str = "Unsupported media type. Only CSV and XLSX files are supported",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=415, code=code, message=message, details=details)


class ValidationError(AppException):
    """Exception raised for business data or input validation failures (422)."""

    def __init__(
        self,
        code: str = "validation_error",
        message: str = "Validation failed for the request payload",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=422, code=code, message=message, details=details)


class RateLimitError(AppException):
    """Exception raised when request rate limit is exceeded (429)."""

    def __init__(
        self,
        code: str = "rate_limited",
        message: str = "Rate limit exceeded. Please try again later",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=429, code=code, message=message, details=details)


class ServiceUnavailableError(AppException):
    """Exception raised when an external dependency or database is down (503)."""

    def __init__(
        self,
        code: str = "database_unavailable",
        message: str = "The service is temporarily unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=503, code=code, message=message, details=details)
