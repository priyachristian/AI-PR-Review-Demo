from decimal import Decimal
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas, security
from app.bonus import calculate_employee_bonus
from app.config import settings
from app.database import get_db

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
)


def _unwrap(val: Any, default: Any = None) -> Any:
    """Helper to unwrap FastAPI parameter defaults when endpoints are called directly in tests."""
    if hasattr(val, "default"):
        return default if val.default is ... else val.default
    return val


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
    """Register a new employee scoped to the tenant organization. Requires Admin authorization."""
    existing = crud.get_employee_by_email(db, email=employee.email, company_id=current_user.company_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An employee with email '{employee.email}' already exists.",
        )
    return crud.create_employee(db=db, employee=employee, company_id=current_user.company_id)


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
    """Retrieve employees scoped to the authenticated tenant organization."""
    return crud.get_employees(
        db=db,
        company_id=current_user.company_id,
        skip=_unwrap(skip, 0),
        limit=_unwrap(limit, 100),
        department=_unwrap(department, None),
        is_active=_unwrap(is_active, None),
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
    """Fetch details of an employee scoped to tenant organization."""
    security.verify_employee_access(employee_id=employee_id, current_user=current_user)

    employee = crud.get_employee(db=db, employee_id=employee_id, company_id=current_user.company_id)
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
        default=None,
        ge=0,
        le=settings.MAX_BONUS_PERCENTAGE,
        description="Bonus percentage (0 to 100)",
    ),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """
    Calculate bonus and total compensation for an employee based on base salary.
    Scoped by tenant (company_id) and role/owner authorization to prevent IDOR.
    """
    security.verify_employee_access(employee_id=employee_id, current_user=current_user)

    employee = crud.get_employee(db=db, employee_id=employee_id, company_id=current_user.company_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    pct = _unwrap(bonus_percentage, None)
    return calculate_employee_bonus(
        employee=employee,
        bonus_percentage=pct,
        default_percentage=settings.DEFAULT_BONUS_PERCENTAGE,
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
    """Update fields of an employee within the tenant organization. Requires Admin authorization."""
    employee = crud.get_employee(db=db, employee_id=employee_id, company_id=current_user.company_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee_update.email and employee_update.email.strip().lower() != employee.email.lower():
        conflict = crud.get_employee_by_email(
            db,
            email=employee_update.email,
            company_id=current_user.company_id,
        )
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
    """Delete an employee within tenant organization. Requires Admin authorization."""
    employee = crud.get_employee(db=db, employee_id=employee_id, company_id=current_user.company_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    crud.delete_employee(db=db, db_employee=employee)
    return None
