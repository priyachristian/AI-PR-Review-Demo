from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
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
):
    """Register a new employee. Checks that email is not already taken."""
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
    department: Optional[str] = Query(None, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    """Retrieve a list of employees with optional pagination and filtering."""
    return crud.get_employees(
        db=db,
        skip=skip,
        limit=limit,
        department=department,
        is_active=is_active,
    )


@router.get(
    "/{employee_id}",
    response_model=schemas.EmployeeResponse,
    summary="Get an employee by ID",
)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
):
    """Fetch details of a single employee by their ID."""
    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    return employee


@router.put(
    "/{employee_id}",
    response_model=schemas.EmployeeResponse,
    summary="Update an employee's details",
)
def update_employee(
    employee_id: int,
    employee_update: schemas.EmployeeUpdate,
    db: Session = Depends(get_db),
):
    """Update fields of an existing employee. Validates email uniqueness if updated."""
    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee_update.email and employee_update.email != employee.email:
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
    employee_id: int,
    db: Session = Depends(get_db),
):
    """Delete an employee by their ID."""
    employee = crud.get_employee(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )
    crud.delete_employee(db=db, db_employee=employee)
    return None
