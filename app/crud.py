from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models, schemas


def get_employee(db: Session, employee_id: int, company_id: int = 1) -> Optional[models.Employee]:
    """Retrieve an employee by primary key ID scoped to the tenant company_id."""
    return (
        db.query(models.Employee)
        .filter(
            models.Employee.id == employee_id,
            models.Employee.company_id == company_id,
        )
        .first()
    )


def get_employee_by_email(db: Session, email: str, company_id: int = 1) -> Optional[models.Employee]:
    """Retrieve an employee by email address scoped to the tenant company_id."""
    return (
        db.query(models.Employee)
        .filter(
            models.Employee.email == email.strip().lower(),
            models.Employee.company_id == company_id,
        )
        .first()
    )


def get_employees(
    db: Session,
    company_id: int = 1,
    skip: int = 0,
    limit: int = 100,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[models.Employee]:
    """Retrieve a list of employees scoped to tenant with pagination and optional filters."""
    query = db.query(models.Employee).filter(models.Employee.company_id == company_id)
    if department:
        query = query.filter(models.Employee.department.ilike(f"%{department.strip()}%"))
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    return query.offset(skip).limit(limit).all()


def create_employee(
    db: Session,
    employee: schemas.EmployeeCreate,
    company_id: int = 1,
) -> models.Employee:
    """Create a new employee record scoped to tenant company_id, catching unique constraint violations."""
    db_employee = models.Employee(
        company_id=company_id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email.strip().lower(),
        department=employee.department,
        role=employee.role,
        salary=employee.salary,
        is_active=employee.is_active,
    )
    db.add(db_employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An employee with email '{employee.email}' already exists in this organization.",
        )
    db.refresh(db_employee)
    return db_employee


def update_employee(
    db: Session,
    db_employee: models.Employee,
    employee_update: schemas.EmployeeUpdate,
) -> models.Employee:
    """Update fields of an existing employee, catching unique constraint violations."""
    update_data = employee_update.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].strip().lower()
    for field, value in update_data.items():
        setattr(db_employee, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this organization.",
        )
    db.refresh(db_employee)
    return db_employee


def delete_employee(db: Session, db_employee: models.Employee) -> None:
    """Delete an employee record."""
    db.delete(db_employee)
    db.commit()
