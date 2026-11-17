"""Root application entrypoint and utility functions.

Provides complete, clean, secure, and working implementations of bonus calculations,
salary helpers, and parameterized employee lookups.
"""

from decimal import Decimal
from typing import Optional
from fastapi import Depends, HTTPException, Path, Query, status
from fastapi.params import Param
from sqlalchemy.orm import Session

from app import crud, models, schemas, security
from app.bonus import (
    calculate_bonus as _calc_bonus,
    calculate_discount,
    calculate_salary,
    calculate_total,
    divide_salary,
    round_currency,
    to_decimal,
)
from app.config import settings
from app.database import SessionLocal, get_db
from app.main import app


def get_employee(employee_id: int, db: Optional[Session] = None) -> Optional[models.Employee]:
    """
    Retrieve an employee securely using parameterized query.
    Fixes previous SQL injection vulnerability by using SQLAlchemy ORM.
    """
    if db is not None:
        return crud.get_employee(db=db, employee_id=employee_id)

    # If called without an injected session, manage a dedicated session
    session = SessionLocal()
    try:
        return crud.get_employee(db=session, employee_id=employee_id)
    finally:
        session.close()


def get_customer_name(name: str) -> str:
    """Validate and return customer name."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Customer name cannot be empty.")
    return name.strip()


@app.get(
    "/bonus/{employee_id}",
    response_model=schemas.BonusResponse,
    tags=["Bonus Calculation"],
    summary="Calculate employee bonus and total compensation",
)
def calculate_bonus(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    bonus_percentage: Optional[Decimal] = Query(
        default=settings.DEFAULT_BONUS_PERCENTAGE,
        ge=0,
        le=settings.MAX_BONUS_PERCENTAGE,
        description="Bonus percentage between 0 and 100",
    ),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """
    Calculate bonus for an employee using proper decimal arithmetic.
    Protected by authentication and authorization.
    Handles non-existent employees (404) and missing salary (400).
    """
    user = security.resolve_user(current_user)
    security.verify_employee_access(employee_id=employee_id, current_user=user)

    employee = get_employee(employee_id=employee_id, db=db)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.salary is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Employee with ID {employee_id} does not have a base salary configured.",
        )

    if isinstance(bonus_percentage, Param) or bonus_percentage is None:
        pct = settings.DEFAULT_BONUS_PERCENTAGE
    else:
        pct = bonus_percentage
    try:
        bonus_val = _calc_bonus(salary=employee.salary, bonus_percentage=pct)
        total_comp = calculate_salary(basic_salary=employee.salary, bonus=bonus_val)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )

    return schemas.BonusResponse(
        employee_id=employee.id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        department=employee.department,
        role=employee.role,
        salary=employee.salary,
        bonus_percentage=pct,
        bonus=bonus_val,
        total_compensation=total_comp,
    )


# Expose arithmetic utilities at module level
__all__ = [
    "app",
    "calculate_bonus",
    "calculate_discount",
    "calculate_salary",
    "calculate_total",
    "divide_salary",
    "get_customer_name",
    "get_employee",
    "round_currency",
]

print("Hello")