"""Base domain exception classes and auth-specific exceptions."""


class DomainError(Exception):
    """Base class for all domain exceptions."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)


# --- Auth exceptions ---


class CredentialsAlreadySetError(DomainError):
    code = "already_set"
    status_code = 409
    message = "Password has already been set"


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    status_code = 401
    message = "Invalid username or password"


class InvalidCurrentPasswordError(DomainError):
    code = "invalid_current_password"
    status_code = 401
    message = "Current password is incorrect"


class UnauthenticatedError(DomainError):
    code = "unauthenticated"
    status_code = 401
    message = "Session missing or expired"


class SessionExpiredError(UnauthenticatedError):
    """Subclass for expired (vs. missing/invalid) sessions.

    Same status code and error code as UnauthenticatedError — the distinction
    is internal only, useful for logging or future differentiation.
    """

    message = "Session has expired"


# --- Company exceptions ---


class CompanyNotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    message = "Company not found"


class CompanyNameConflictError(DomainError):
    code = "name_conflict"
    status_code = 409
    message = "A company with this name already exists"
