from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Union
from fastapi.params import Param

Number = Union[Decimal, int, float, str, Any]


def to_decimal(val: Number) -> Decimal:
    """Safely convert any numeric representation to Decimal."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, Param):
        val = val.default
    return Decimal(str(val))


def round_currency(amount: Decimal) -> Decimal:
    """Round monetary amount to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_bonus(salary: Number, bonus_percentage: Number = Decimal("10.0")) -> Decimal:
    """
    Calculate bonus given base salary and percentage (0-100).
    Uses proper decimal handling and validation.
    """
    salary_dec = to_decimal(salary)
    pct_dec = to_decimal(bonus_percentage)

    if salary_dec < Decimal("0"):
        raise ValueError("Salary must be non-negative.")
    if pct_dec < Decimal("0") or pct_dec > Decimal("100"):
        raise ValueError("Bonus percentage must be between 0 and 100.")

    bonus = (salary_dec * pct_dec) / Decimal("100")
    return round_currency(bonus)


def calculate_salary(basic_salary: Number, bonus: Number) -> Decimal:
    """Calculate total compensation by adding basic salary and bonus."""
    basic_dec = to_decimal(basic_salary)
    bonus_dec = to_decimal(bonus)

    if basic_dec < Decimal("0"):
        raise ValueError("Basic salary must be non-negative.")
    if bonus_dec < Decimal("0"):
        raise ValueError("Bonus must be non-negative.")

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
        raise ValueError("Salary must be non-negative.")

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
