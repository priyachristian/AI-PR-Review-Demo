"""Domain exceptions for Employee Management service.

These exceptions are framework-agnostic and are translated into appropriate
HTTP status codes at the API router layer.
"""


class DomainError(Exception):
    """Base domain exception."""
    pass


class EmployeeMissingSalaryError(DomainError):
    """Raised when an employee has no base salary configured for bonus calculation."""

    def __init__(self, employee_id: int):
        super().__init__(f"Employee with ID {employee_id} does not have a base salary configured.")
        self.employee_id = employee_id


class InvalidBonusPercentageError(DomainError, ValueError):
    """Raised when bonus percentage is outside allowable business boundaries (0-100%)."""

    def __init__(self, message: str = "Bonus percentage must be between 0 and 100."):
        super().__init__(message)


class InvalidSalaryError(DomainError, ValueError):
    """Raised when a salary amount is invalid or negative."""

    def __init__(self, message: str = "Salary must be non-negative."):
        super().__init__(message)
