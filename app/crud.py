from typing import List, Optional
from sqlalchemy.orm import Session
from app import models, schemas


def get_employee(db: Session, employee_id: int) -> Optional[models.Employee]:
    """Retrieve an employee by primary key ID using parameterized query."""
    return db.query(models.Employee).filter(models.Employee.id == employee_id).first()


def get_employee_by_email(db: Session, email: str) -> Optional[models.Employee]:
    """Retrieve an employee by email address."""
    return db.query(models.Employee).filter(models.Employee.email == email.strip().lower()).first()


def get_employees(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[models.Employee]:
    """Retrieve a list of employees with pagination and optional filters."""
    query = db.query(models.Employee)
    if department:
        query = query.filter(models.Employee.department.ilike(f"%{department.strip()}%"))
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    return query.offset(skip).limit(limit).all()


def create_employee(db: Session, employee: schemas.EmployeeCreate) -> models.Employee:
    """Create a new employee record."""
    db_employee = models.Employee(
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email.strip().lower(),
        department=employee.department,
        role=employee.role,
        salary=employee.salary,
        is_active=employee.is_active,
    )
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee


def update_employee(
    db: Session,
    db_employee: models.Employee,
    employee_update: schemas.EmployeeUpdate,
) -> models.Employee:
    """Update fields of an existing employee."""
    update_data = employee_update.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].strip().lower()
    for field, value in update_data.items():
        setattr(db_employee, field, value)
    db.commit()
    db.refresh(db_employee)
    return db_employee


def delete_employee(db: Session, db_employee: models.Employee) -> None:
    """Delete an employee record."""
    db.delete(db_employee)
    db.commit()
