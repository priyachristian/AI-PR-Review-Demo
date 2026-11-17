from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.params import Param
from sqlalchemy.orm import Session

from app import crud, schemas, security
from app.bonus import calculate_bonus, calculate_salary
from app.config import settings
from app.database import get_db

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
)


@router.post(
    "/",
    response_model=schemas.EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee",
)
def create_employee(
    employee: schemas.EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    """Register a new employee. Requires Admin authorization."""
    user = security.resolve_user(current_user)
    if user.role != security.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required to create employee records.",
        )

    existing = crud.get_employee_by_email(db, email=employee.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An employee with email '{employee.email}' already exists.",
        )
    return crud.create_employee(db=db, employee=employee)


@router.get(
    "/",
    response_model=List[schemas.EmployeeResponse],
    summary="List all employees with optional filters",
)
def list_employees(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of records to return"),
    department: Optional[str] = Query(None, min_length=1, max_length=100, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """Retrieve a list of employees with optional pagination and filtering."""
    security.resolve_user(current_user)
    skip_val = skip.default if isinstance(skip, Param) else skip
    limit_val = limit.default if isinstance(limit, Param) else limit
    department_val = department.default if isinstance(department, Param) else department
    is_active_val = is_active.default if isinstance(is_active, Param) else is_active

    return crud.get_employees(
        db=db,
        skip=skip_val,
        limit=limit_val,
        department=department_val,
        is_active=is_active_val,
    )


@router.get(
    "/{employee_id}",
    response_model=schemas.EmployeeResponse,
    summary="Get an employee by ID",
)
def get_employee(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """Fetch details of a single employee by their ID."""
    user = security.resolve_user(current_user)
    security.verify_employee_access(employee_id=employee_id, current_user=user)

    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    return employee


@router.get(
    "/{employee_id}/bonus",
    response_model=schemas.BonusResponse,
    summary="Calculate bonus and total compensation for an employee",
)
def get_employee_bonus(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    bonus_percentage: Optional[Decimal] = Query(
        default=settings.DEFAULT_BONUS_PERCENTAGE,
        ge=0,
        le=settings.MAX_BONUS_PERCENTAGE,
        description="Bonus percentage (0 to 100)",
    ),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """
    Calculate bonus and total compensation for an employee based on their base salary.
    Sensitive compensation data protected by authentication & authorization.
    """
    user = security.resolve_user(current_user)
    security.verify_employee_access(employee_id=employee_id, current_user=user)

    employee = crud.get_employee(db=db, employee_id=employee_id)
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
        bonus_val = calculate_bonus(salary=employee.salary, bonus_percentage=pct)
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


@router.put(
    "/{employee_id}",
    response_model=schemas.EmployeeResponse,
    summary="Update an employee's details",
)
def update_employee(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    employee_update: schemas.EmployeeUpdate = ...,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    """Update fields of an existing employee. Requires Admin authorization."""
    user = security.resolve_user(current_user)
    if user.role != security.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required to update employee records.",
        )

    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee_update.email and employee_update.email.strip().lower() != employee.email.lower():
        conflict = crud.get_employee_by_email(db, email=employee_update.email)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{employee_update.email}' is already in use by another employee.",
            )

    return crud.update_employee(
        db=db,
        db_employee=employee,
        employee_update=employee_update,
    )


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an employee",
)
def delete_employee(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    """Delete an employee by their ID. Requires Admin authorization."""
    user = security.resolve_user(current_user)
    if user.role != security.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required to delete employee records.",
        )

    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    crud.delete_employee(db=db, db_employee=employee)
    return None
