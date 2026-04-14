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


# --- Ingestion / Source exceptions ---


class RoutingError(DomainError):
    code = "routing_error"
    status_code = 422
    message = "Company routing failed"


class SourceNotFoundError(DomainError):
    code = "source_not_found"
    status_code = 404
    message = "Source not found"


class SourceNotFailedError(DomainError):
    code = "state_conflict"
    status_code = 409
    message = "Source is not in a failed state"


# --- Inference exceptions ---


class InferenceValidationError(DomainError):
    """LLM response failed validation (bad JSON, missing fields, etc.)."""

    code = "inference_validation_failed"
    status_code = 500
    message = "LLM response validation failed"

    def __init__(self, message: str | None = None, raw_response: str | None = None):
        self.raw_response = raw_response
        super().__init__(message)


class InferenceApiError(DomainError):
    """LLM API call failed after retries exhausted."""

    code = "inference_api_failed"
    status_code = 500
    message = "LLM API call failed"


# --- Review / InferredFact exceptions ---


class FactNotFoundError(DomainError):
    code = "fact_not_found"
    status_code = 404
    message = "Inferred fact not found"


class FactNotPendingError(DomainError):
    code = "fact_not_pending"
    status_code = 409
    message = "Inferred fact is not in pending status"


class FactCompanyMismatchError(DomainError):
    code = "fact_company_mismatch"
    status_code = 404
    message = "Inferred fact does not belong to this company"


# --- Person exceptions ---


class PersonNotFoundError(DomainError):
    code = "person_not_found"
    status_code = 404
    message = "Person not found"


class PersonCompanyMismatchError(DomainError):
    code = "person_company_mismatch"
    status_code = 404
    message = "Person does not belong to this company"


# --- Functional area exceptions ---


class AreaNotFoundError(DomainError):
    code = "area_not_found"
    status_code = 404
    message = "Functional area not found"


class AreaNameConflictError(DomainError):
    code = "area_name_conflict"
    status_code = 409
    message = "A functional area with this name already exists"
