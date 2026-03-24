"""Base domain exception classes."""


class DomainError(Exception):
    """Base class for all domain exceptions."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)
