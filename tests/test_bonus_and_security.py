from decimal import Decimal
import importlib.util
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app as app_pkg
from app.bonus import (
    calculate_bonus,
    calculate_discount,
    calculate_salary,
    calculate_total,
    divide_salary,
    round_currency,
)
from app.config import settings
from app.main import app, root_calculate_bonus
from app.routers import employees
from app.schemas import EmployeeCreate, EmployeeUpdate
from app.security import (
    DEFAULT_SYSTEM_USER,
    User,
    UserRole,
    get_current_user,
    require_admin,
    require_authenticated,
    verify_employee_access,
)


def get_root_app_module():
    """Dynamically load root app.py to verify its standalone exports."""
    root_path = Path(__file__).resolve().parent.parent / "app.py"
    spec = importlib.util.spec_from_file_location("root_app", root_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ==============================================================================
# 1. Decimal & Monetary Calculation Tests
# ==============================================================================

def test_decimal_rounding_and_precision():
    """Verify monetary rounding avoids floating-point inaccuracies."""
    # 99999.99 * 12.5% = 12499.99875 -> rounds to 12500.00
    res = calculate_bonus(Decimal("99999.99"), Decimal("12.5"))
    assert res == Decimal("12500.00")

    # 1000.054 -> rounds to 1000.05
    res = round_currency(Decimal("1000.054"))
    assert res == Decimal("1000.05")

    # 1000.055 -> rounds to 1000.06 (ROUND_HALF_UP)
    res = round_currency(Decimal("1000.055"))
    assert res == Decimal("1000.06")


def test_calculate_bonus_logic():
    """Test standard and custom percentage bonus calculations."""
    bonus = calculate_bonus(Decimal("100000.00"), Decimal("10.0"))
    assert bonus == Decimal("10000.00")

    # Custom percentage
    bonus_custom = calculate_bonus(Decimal("80000.00"), Decimal("15.5"))
    assert bonus_custom == Decimal("12400.00")

    # Zero salary
    assert calculate_bonus(Decimal("0.00"), Decimal("10.0")) == Decimal("0.00")

    # Invalid negative salary
    with pytest.raises(ValueError, match="Salary must be non-negative"):
        calculate_bonus(Decimal("-500.00"), Decimal("10.0"))

    # Invalid percentage out of bounds
    with pytest.raises(ValueError, match="Bonus percentage must be between 0 and 100"):
        calculate_bonus(Decimal("50000.00"), Decimal("150.0"))

    with pytest.raises(ValueError, match="Bonus percentage must be between 0 and 100"):
        calculate_bonus(Decimal("50000.00"), Decimal("-5.0"))


def test_calculate_salary_helpers():
    """Test calculate_salary arithmetic and validation."""
    total = calculate_salary(Decimal("95000.00"), Decimal("9500.00"))
    assert total == Decimal("104500.00")

    with pytest.raises(ValueError, match="Basic salary must be non-negative"):
        calculate_salary(Decimal("-100"), Decimal("50"))

    with pytest.raises(ValueError, match="Bonus must be non-negative"):
        calculate_salary(Decimal("100"), Decimal("-50"))


def test_divide_salary_safe_from_zero_division():
    """Verify divide_salary prevents ZeroDivisionError and handles negative values."""
    divided = divide_salary(Decimal("100000.00"), 4)
    assert divided == Decimal("25000.00")

    with pytest.raises(ValueError, match="Number of employees must be a positive integer"):
        divide_salary(Decimal("100000.00"), 0)

    with pytest.raises(ValueError, match="Number of employees must be a positive integer"):
        divide_salary(Decimal("100000.00"), -2)

    with pytest.raises(ValueError, match="Salary must be non-negative"):
        divide_salary(Decimal("-1000.00"), 2)


def test_calculate_discount_and_total():
    """Test discount and total utilities."""
    final_price = calculate_discount(Decimal("100.00"), Decimal("15.50"))
    assert final_price == Decimal("84.50")

    with pytest.raises(ValueError, match="Discount cannot exceed original price"):
        calculate_discount(Decimal("50.00"), Decimal("60.00"))

    total = calculate_total(Decimal("19.99"), 3)
    assert total == Decimal("59.97")

    with pytest.raises(ValueError, match="Quantity must be a non-negative integer"):
        calculate_total(Decimal("19.99"), -1)


# ==============================================================================
# 2. Employee Bonus Endpoint Tests
# ==============================================================================

def test_employee_bonus_endpoint_success(db_session):
    """Test bonus calculation endpoint with an existing employee."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Grace",
            last_name="Hopper",
            email="grace.hopper@example.com",
            department="Engineering",
            role="Chief Architect",
            salary=Decimal("120000.00"),
        ),
        db=db_session,
    )

    bonus_resp = employees.get_employee_bonus(
        employee_id=created.id,
        bonus_percentage=Decimal("15.0"),
        db=db_session,
    )

    assert bonus_resp.employee_id == created.id
    assert bonus_resp.first_name == "Grace"
    assert bonus_resp.salary == Decimal("120000.00")
    assert bonus_resp.bonus_percentage == Decimal("15.0")
    assert bonus_resp.bonus == Decimal("18000.00")
    assert bonus_resp.total_compensation == Decimal("138000.00")


def test_employee_bonus_not_found(db_session):
    """Verify 404 when calculating bonus for non-existent employee."""
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=99999,
            bonus_percentage=Decimal("10.0"),
            db=db_session,
        )
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_employee_bonus_missing_salary(db_session):
    """Verify 400 Bad Request when employee has no salary set."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Intern",
            last_name="Candidate",
            email="intern@example.com",
            department="Internship",
            role="Junior Intern",
            salary=None,
        ),
        db=db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=created.id,
            bonus_percentage=Decimal("10.0"),
            db=db_session,
        )
    assert exc_info.value.status_code == 400
    assert "base salary configured" in exc_info.value.detail.lower()


# ==============================================================================
# 3. Input Validation Tests
# ==============================================================================

def test_employee_blank_name_validation():
    """Verify whitespace-only names are rejected."""
    with pytest.raises(Exception):
        EmployeeCreate(
            first_name="   ",
            last_name="Smith",
            email="valid@example.com",
        )

    with pytest.raises(Exception):
        EmployeeCreate(
            first_name="John",
            last_name="   ",
            email="valid@example.com",
        )


def test_employee_negative_salary_validation():
    """Verify negative salary is rejected by Pydantic schema."""
    with pytest.raises(Exception):
        EmployeeCreate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            salary=Decimal("-1000.00"),
        )


def test_employee_excessive_salary_validation():
    """Verify unrealistically excessive salary is rejected."""
    with pytest.raises(Exception):
        EmployeeCreate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            salary=Decimal("99999999999.00"),
        )


def test_employee_invalid_email_validation():
    """Verify invalid email formats are rejected."""
    with pytest.raises(Exception):
        EmployeeCreate(
            first_name="John",
            last_name="Doe",
            email="not-an-email",
        )


# ==============================================================================
# 4. Authentication and Authorization Tests
# ==============================================================================

def test_authentication_credentials_validation():
    """Verify authentication dependency validates API key and Bearer tokens."""
    # Missing credentials -> 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key=None, auth_creds=None)
    assert exc_info.value.status_code == 401
    assert "required" in exc_info.value.detail.lower()

    # Invalid API key -> 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key="bad-api-key-999", auth_creds=None)
    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()

    # Invalid Bearer token -> 401
    with pytest.raises(HTTPException) as exc_info:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-bearer-token")
        get_current_user(api_key=None, auth_creds=creds)
    assert exc_info.value.status_code == 401

    # Valid Admin API Key -> User with ADMIN role
    admin_user = get_current_user(api_key=settings.ADMIN_API_KEY, auth_creds=None)
    assert admin_user.role == UserRole.ADMIN

    # Valid Employee API Key -> User with EMPLOYEE role
    emp_user = get_current_user(api_key=settings.API_KEY, auth_creds=None)
    assert emp_user.role == UserRole.EMPLOYEE

    # Valid Bearer Token (Admin)
    admin_bearer = get_current_user(
        api_key=None,
        auth_creds=HTTPAuthorizationCredentials(scheme="Bearer", credentials=settings.ADMIN_API_KEY),
    )
    assert admin_bearer.role == UserRole.ADMIN


def test_authorization_role_enforcement(db_session):
    """Verify non-admin users cannot perform admin actions."""
    standard_user = User(username="staff", role=UserRole.EMPLOYEE, employee_id=1)

    # Standard employee cannot create records
    with pytest.raises(HTTPException) as exc_info:
        employees.create_employee(
            employee=EmployeeCreate(
                first_name="Unauthorized",
                last_name="Entry",
                email="unauth@example.com",
            ),
            db=db_session,
            current_user=standard_user,
        )
    assert exc_info.value.status_code == 403

    # Standard employee cannot update records
    with pytest.raises(HTTPException) as exc_info:
        employees.update_employee(
            employee_id=1,
            employee_update=EmployeeUpdate(role="CTO"),
            db=db_session,
            current_user=standard_user,
        )
    assert exc_info.value.status_code == 403

    # Standard employee cannot delete records
    with pytest.raises(HTTPException) as exc_info:
        employees.delete_employee(
            employee_id=1,
            db=db_session,
            current_user=standard_user,
        )
    assert exc_info.value.status_code == 403


def test_prevent_unauthorized_record_access():
    """Verify employee cannot access another employee's private record."""
    user_emp1 = User(username="user1", role=UserRole.EMPLOYEE, employee_id=1)

    # Attempting to access employee 2's sensitive data
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(employee_id=2, current_user=user_emp1)
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail

    # Employee 1 accessing own data passes without exception
    verify_employee_access(employee_id=1, current_user=user_emp1)

    # Admin accessing any record passes without exception
    admin_user = User(username="admin", role=UserRole.ADMIN)
    verify_employee_access(employee_id=999, current_user=admin_user)


def test_root_calculate_bonus_route(db_session):
    """Verify root /bonus/{employee_id} route function works with authentication."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            department="Analytics",
            role="Lead Mathematician",
            salary=Decimal("150000.00"),
        ),
        db=db_session,
    )

    admin_user = User(username="admin", role=UserRole.ADMIN)
    res = root_calculate_bonus(
        employee_id=created.id,
        bonus_percentage=Decimal("20.0"),
        db=db_session,
        current_user=admin_user,
    )
    assert res.employee_id == created.id
    assert res.bonus == Decimal("30000.00")
    assert res.total_compensation == Decimal("180000.00")


# ==============================================================================
# 5. app.py Root Module Utility Tests
# ==============================================================================

def test_app_py_module_functions(db_session):
    """Verify all functions in app.py are fully implemented and working."""
    root_app = get_root_app_module()

    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Katherine",
            last_name="Johnson",
            email="katherine@example.com",
            department="Orbital Mechanics",
            salary=Decimal("110000.00"),
        ),
        db=db_session,
    )

    # get_employee with injected session
    emp = root_app.get_employee(employee_id=created.id, db=db_session)
    assert emp is not None
    assert emp.first_name == "Katherine"

    # calculate_bonus endpoint function
    bonus_data = root_app.calculate_bonus(
        employee_id=created.id,
        db=db_session,
        current_user=DEFAULT_SYSTEM_USER,
    )
    assert bonus_data.bonus == Decimal("11000.00")

    # get_customer_name
    assert root_app.get_customer_name("  Acme Corp  ") == "Acme Corp"
    with pytest.raises(ValueError):
        root_app.get_customer_name("   ")

    # verify app package exports
    assert app_pkg.get_employee is not None
    assert app_pkg.calculate_bonus is not None
    assert app_pkg.calculate_salary is not None


def test_bonus_edge_cases_zero_salary(db_session):
    """Test bonus calculation for employee with 0 salary."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Volunteer",
            last_name="Worker",
            email="volunteer@example.com",
            salary=Decimal("0.00"),
        ),
        db=db_session,
    )
    res = employees.get_employee_bonus(
        employee_id=created.id,
        bonus_percentage=Decimal("10.0"),
        db=db_session,
    )
    assert res.bonus == Decimal("0.00")
    assert res.total_compensation == Decimal("0.00")


def test_bonus_percentage_invalid_error_handling(db_session):
    """Test bonus calculation handles out-of-range percentage with HTTP 400."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Standard",
            last_name="Staff",
            email="standard@example.com",
            salary=Decimal("60000.00"),
        ),
        db=db_session,
    )
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=created.id,
            bonus_percentage=Decimal("-10.0"),
            db=db_session,
        )
    assert exc_info.value.status_code == 400
    assert "between 0 and 100" in exc_info.value.detail


def test_sql_injection_defense(db_session):
    """Verify parameterized queries handle SQL injection attempts safely."""
    # Attempting to search with SQL injection payload string in department
    results = employees.list_employees(
        department="'; DROP TABLE employees; --",
        db=db_session,
    )
    assert results == []

    # Verify table is intact and operational
    all_emps = employees.list_employees(db=db_session)
    assert isinstance(all_emps, list)

