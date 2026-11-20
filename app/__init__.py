"""Employee Management Demo Application package."""

from app.main import app
from app.crud import get_employee
from app.bonus import (
    calculate_bonus,
    calculate_salary,
    divide_salary,
    calculate_discount,
    calculate_total,
    round_currency,
)

__all__ = [
    "app",
    "get_employee",
    "calculate_bonus",
    "calculate_salary",
    "divide_salary",
    "calculate_discount",
    "calculate_total",
    "round_currency",
]
