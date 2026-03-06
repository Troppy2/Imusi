"""
Custom exceptions for consistent API error responses.
Handlers in main.py map these to HTTP status and a uniform JSON shape.
"""


class AppException(Exception):
    """Base for application errors with HTTP status and error code."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "ERROR",
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found (404)."""

    def __init__(self, message: str = "Resource not found", resource: str | None = None, resource_id: int | str | None = None):
        details = {}
        if resource:
            details["resource"] = resource
        if resource_id is not None:
            details["resource_id"] = resource_id
        super().__init__(
            message=message,
            status_code=404,
            code="NOT_FOUND",
            details=details if details else None,
        )


class BadRequestError(AppException):
    """Bad request / validation (400)."""

    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=400,
            code=code,
            details=details,
        )


class ConflictError(AppException):
    """Conflict e.g. duplicate (409)."""

    def __init__(self, message: str = "Conflict", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=409,
            code="CONFLICT",
            details=details,
        )


class UnauthorizedError(AppException):
    """Authentication/authorization failure (401)."""

    def __init__(self, message: str = "Unauthorized", code: str = "UNAUTHORIZED", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=401,
            code=code,
            details=details,
        )


class ServerConfigError(AppException):
    """Server-side configuration error (500)."""

    def __init__(self, message: str = "Server configuration error", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=500,
            code="SERVER_CONFIG_ERROR",
            details=details,
        )
