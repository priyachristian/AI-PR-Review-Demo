from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models, schemas


def _round(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    min_salary: Optional[Decimal] = None,
    max_salary: Optional[Decimal] = None,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc",
) -> List[models.Employee]:
    """Retrieve a list of employees scoped to tenant with pagination, filters, search, and sorting."""
    query = db.query(models.Employee).filter(models.Employee.company_id == company_id)
    if department:
        query = query.filter(models.Employee.department.ilike(f"%{department.strip()}%"))
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    if min_salary is not None:
        query = query.filter(models.Employee.salary >= min_salary)
    if max_salary is not None:
        query = query.filter(models.Employee.salary <= max_salary)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Employee.first_name.ilike(term),
                models.Employee.last_name.ilike(term),
                models.Employee.email.ilike(term),
            )
        )

    # Validate and apply sorting
    sort_column_map = {
        "id": models.Employee.id,
        "first_name": models.Employee.first_name,
        "last_name": models.Employee.last_name,
        "salary": models.Employee.salary,
        "created_at": models.Employee.created_at,
    }
    sort_col = sort_column_map.get(sort_by, models.Employee.id)
    if order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

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


def get_company_payroll_report(db: Session, company_id: int = 1) -> schemas.CompanyPayrollReport:
    """Compute aggregate payroll and department statistics scoped to tenant."""
    employees = db.query(models.Employee).filter(models.Employee.company_id == company_id).all()

    total_headcount = len(employees)
    active_headcount = sum(1 for e in employees if e.is_active)

    dept_groups = defaultdict(list)
    for emp in employees:
        dept_groups[emp.department].append(emp)

    dept_summaries: List[schemas.DepartmentSummary] = []
    total_company_payroll = Decimal("0.00")

    for dept_name, emps in sorted(dept_groups.items()):
        dept_total = len(emps)
        dept_active = sum(1 for e in emps if e.is_active)
        salaries = [Decimal(str(e.salary)) for e in emps if e.salary is not None]

        dept_payroll = sum(salaries, Decimal("0.00"))
        total_company_payroll += dept_payroll

        avg_salary = (dept_payroll / Decimal(len(salaries))) if salaries else Decimal("0.00")
        min_salary = min(salaries) if salaries else None
        max_salary = max(salaries) if salaries else None

        dept_summaries.append(
            schemas.DepartmentSummary(
                department=dept_name,
                total_employees=dept_total,
                active_employees=dept_active,
                total_payroll=_round(dept_payroll),
                average_salary=_round(avg_salary),
                min_salary=_round(min_salary) if min_salary is not None else None,
                max_salary=_round(max_salary) if max_salary is not None else None,
            )
        )

    company_avg = (
        (total_company_payroll / Decimal(total_headcount))
        if total_headcount > 0
        else Decimal("0.00")
    )

    return schemas.CompanyPayrollReport(
        company_id=company_id,
        total_headcount=total_headcount,
        active_headcount=active_headcount,
        total_annual_payroll=_round(total_company_payroll),
        average_salary=_round(company_avg),
        departments=dept_summaries,
    )

