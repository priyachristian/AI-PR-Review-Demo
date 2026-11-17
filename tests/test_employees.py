import pytest
from fastapi import HTTPException
from app.routers import employees
from app.schemas import EmployeeCreate, EmployeeUpdate
from app.main import root, health_check


def test_root_endpoint():
    res = root()
    assert res["status"] == "healthy"
    assert "service" in res
    assert res["version"] == "1.0.0"


def test_health_check():
    res = health_check()
    assert res == {"status": "ok"}


def test_create_employee(db_session):
    payload = EmployeeCreate(
        first_name="Alice",
        last_name="Smith",
        email="alice.smith@example.com",
        department="Engineering",
        role="Backend Engineer",
        salary=92000.0,
        is_active=True,
    )
    emp = employees.create_employee(employee=payload, db=db_session)
    assert emp.id is not None
    assert emp.first_name == "Alice"
    assert emp.last_name == "Smith"
    assert emp.email == "alice.smith@example.com"
    assert emp.salary == 92000.0
    assert emp.is_active is True
    assert emp.created_at is not None
    assert emp.updated_at is not None


def test_create_employee_duplicate_email(db_session):
    payload = EmployeeCreate(
        first_name="Bob",
        last_name="Taylor",
        email="bob.taylor@example.com",
        department="Product",
        role="Product Manager",
    )
    employees.create_employee(employee=payload, db=db_session)

    with pytest.raises(HTTPException) as exc_info:
        employees.create_employee(employee=payload, db=db_session)
    assert exc_info.value.status_code == 400
    assert "already exists" in exc_info.value.detail


def test_get_employee_by_id(db_session):
    payload = EmployeeCreate(
        first_name="Carol",
        last_name="Danvers",
        email="carol.danvers@example.com",
        department="Operations",
        role="Director",
    )
    created = employees.create_employee(employee=payload, db=db_session)
    fetched = employees.get_employee(employee_id=created.id, db=db_session)
    assert fetched.id == created.id
    assert fetched.email == "carol.danvers@example.com"


def test_get_employee_not_found(db_session):
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee(employee_id=99999, db=db_session)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_list_employees_and_filter(db_session):
    emp_list = [
        EmployeeCreate(
            first_name="Dev",
            last_name="One",
            email="dev1@example.com",
            department="Engineering",
            is_active=True,
        ),
        EmployeeCreate(
            first_name="Dev",
            last_name="Two",
            email="dev2@example.com",
            department="Engineering",
            is_active=False,
        ),
        EmployeeCreate(
            first_name="Sales",
            last_name="One",
            email="sales1@example.com",
            department="Sales",
            is_active=True,
        ),
    ]
    for emp in emp_list:
        employees.create_employee(employee=emp, db=db_session)

    all_emps = employees.list_employees(
        skip=0, limit=100, department=None, is_active=None, db=db_session
    )
    assert len(all_emps) == 3

    eng_emps = employees.list_employees(
        skip=0, limit=100, department="Engineering", is_active=None, db=db_session
    )
    assert len(eng_emps) == 2

    active_emps = employees.list_employees(
        skip=0, limit=100, department=None, is_active=True, db=db_session
    )
    assert len(active_emps) == 2


def test_update_employee(db_session):
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Dave",
            last_name="Miller",
            email="dave@example.com",
            department="HR",
            salary=60000.0,
        ),
        db=db_session,
    )
    update_payload = EmployeeUpdate(role="Lead HR Manager", salary=75000.0)
    updated = employees.update_employee(
        employee_id=created.id, employee_update=update_payload, db=db_session
    )
    assert updated.role == "Lead HR Manager"
    assert updated.salary == 75000.0
    assert updated.first_name == "Dave"


def test_update_employee_email_conflict(db_session):
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="User",
            last_name="A",
            email="usera@example.com",
        ),
        db=db_session,
    )
    user_b = employees.create_employee(
        employee=EmployeeCreate(
            first_name="User",
            last_name="B",
            email="userb@example.com",
        ),
        db=db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        employees.update_employee(
            employee_id=user_b.id,
            employee_update=EmployeeUpdate(email="usera@example.com"),
            db=db_session,
        )
    assert exc_info.value.status_code == 400
    assert "already in use" in exc_info.value.detail


def test_update_employee_not_found(db_session):
    with pytest.raises(HTTPException) as exc_info:
        employees.update_employee(
            employee_id=99999,
            employee_update=EmployeeUpdate(role="Manager"),
            db=db_session,
        )
    assert exc_info.value.status_code == 404


def test_delete_employee(db_session):
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Eve",
            last_name="Adams",
            email="eve@example.com",
        ),
        db=db_session,
    )
    emp_id = created.id
    employees.delete_employee(employee_id=emp_id, db=db_session)

    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee(employee_id=emp_id, db=db_session)
    assert exc_info.value.status_code == 404


def test_delete_employee_not_found(db_session):
    with pytest.raises(HTTPException) as exc_info:
        employees.delete_employee(employee_id=99999, db=db_session)
    assert exc_info.value.status_code == 404
