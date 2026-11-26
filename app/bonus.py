from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, Union

from app import schemas
from app.exceptions import (
    DomainError,
    EmployeeMissingSalaryError,
    InvalidBonusPercentageError,
    InvalidSalaryError,
)

Number = Union[Decimal, int, float, str]


def to_decimal(val: Number) -> Decimal:
    """Safely convert any numeric representation to Decimal without framework dependencies."""
    return val if isinstance(val, Decimal) else Decimal(str(val))


def round_currency(amount: Decimal) -> Decimal:
    """Round monetary amount to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_bonus(salary: Number, bonus_percentage: Number = Decimal("10.0")) -> Decimal:
    """
    Calculate bonus given base salary and percentage (0-100).
    Framework-free pure calculation function raising domain exceptions.
    """
    salary_dec = to_decimal(salary)
    pct_dec = to_decimal(bonus_percentage)

    if salary_dec < Decimal("0"):
        raise InvalidSalaryError("Salary must be non-negative.")
    if pct_dec < Decimal("0") or pct_dec > Decimal("100"):
        raise InvalidBonusPercentageError("Bonus percentage must be between 0 and 100.")

    bonus = (salary_dec * pct_dec) / Decimal("100")
    return round_currency(bonus)


def calculate_salary(basic_salary: Number, bonus: Number) -> Decimal:
    """Calculate total compensation by adding basic salary and bonus."""
    basic_dec = to_decimal(basic_salary)
    bonus_dec = to_decimal(bonus)

    if basic_dec < Decimal("0"):
        raise InvalidSalaryError("Basic salary must be non-negative.")
    if bonus_dec < Decimal("0"):
        raise InvalidSalaryError("Bonus must be non-negative.")

    return round_currency(basic_dec + bonus_dec)


def divide_salary(salary: Number, employees: int) -> Decimal:
    """
    Divide total salary pool evenly among a given number of employees.
    Guards against division by zero and negative inputs.
    """
    salary_dec = to_decimal(salary)

    if not isinstance(employees, int) or employees <= 0:
        raise ValueError("Number of employees must be a positive integer greater than zero.")
    if salary_dec < Decimal("0"):
        raise InvalidSalaryError("Salary must be non-negative.")

    return round_currency(salary_dec / Decimal(employees))


def calculate_discount(price: Number, discount: Number) -> Decimal:
    """Calculate final price after applying a discount amount."""
    price_dec = to_decimal(price)
    discount_dec = to_decimal(discount)

    if price_dec < Decimal("0"):
        raise ValueError("Price must be non-negative.")
    if discount_dec < Decimal("0"):
        raise ValueError("Discount must be non-negative.")
    if discount_dec > price_dec:
        raise ValueError("Discount cannot exceed original price.")

    return round_currency(price_dec - discount_dec)


def calculate_total(price: Number, quantity: int) -> Decimal:
    """Calculate total cost for price and quantity."""
    price_dec = to_decimal(price)

    if price_dec < Decimal("0"):
        raise ValueError("Price must be non-negative.")
    if not isinstance(quantity, int) or quantity < 0:
        raise ValueError("Quantity must be a non-negative integer.")

    return round_currency(price_dec * Decimal(quantity))


def calculate_employee_bonus(
    employee: Any,
    bonus_percentage: Optional[Decimal] = None,
    default_percentage: Decimal = Decimal("10.0"),
) -> schemas.BonusResponse:
    """
    Single canonical service function to calculate employee bonus.
    Consolidates bonus logic to prevent duplication across handlers.
    Raises domain exceptions on invalid input or missing salary.
    """
    if employee.salary is None:
        raise EmployeeMissingSalaryError(employee_id=employee.id)

    pct = bonus_percentage if bonus_percentage is not None else default_percentage
    bonus_val = calculate_bonus(salary=employee.salary, bonus_percentage=pct)
    total_comp = calculate_salary(basic_salary=employee.salary, bonus=bonus_val)

    return schemas.BonusResponse(
        employee_id=employee.id,
        company_id=employee.company_id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        department=employee.department,
        role=employee.role,
        salary=employee.salary,
        bonus_percentage=pct,
        bonus=bonus_val,
        total_compensation=total_comp,
    )
