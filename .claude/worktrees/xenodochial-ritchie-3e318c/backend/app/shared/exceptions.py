"""Custom application exceptions."""


class AppException(Exception):
    """Base exception for application errors."""
    pass


class NotFoundException(AppException):
    """Resource not found (404)."""
    pass


class ValidationException(AppException):
    """Validation error (400)."""
    pass


class AuthenticationException(AppException):
    """Authentication error (401)."""
    pass


class ForbiddenException(AppException):
    """Forbidden / permission denied (403)."""
    pass
