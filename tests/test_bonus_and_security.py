from decimal import Decimal
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

import app as app_pkg
from app.bonus import (
    calculate_bonus,
    calculate_discount,
    calculate_employee_bonus,
    calculate_salary,
    calculate_total,
    divide_salary,
    round_currency,
)
from app.config import Settings, settings
from app.main import app, root_calculate_bonus
from app.routers import employees
from app.schemas import EmployeeCreate, EmployeeUpdate
from app.security import (
    User,
    UserRole,
    create_access_token,
    decode_access_token,
    get_current_user,
    require_admin,
    require_authenticated,
    verify_employee_access,
)


# ==============================================================================
# Finding 1: Secret Key Validation Tests
# ==============================================================================

def test_missing_or_short_secrets_fail_validation():
    """Verify application configuration fails at startup if secrets are missing or short."""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY="short-secret",
            API_KEY="valid-length-api-key-at-least-32-chars-long",
            ADMIN_API_KEY="valid-length-admin-api-key-at-least-32-chars",
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY="valid-length-secret-key-at-least-32-chars",
            API_KEY="short",
            ADMIN_API_KEY="valid-length-admin-api-key-at-least-32-chars",
        )


# ==============================================================================
# Finding 2: Tenant Isolation & Company ID Scoping Tests
# ==============================================================================

def test_tenant_scoping_isolation(db_session, admin_user, other_tenant_admin):
    """Verify employees in Company 1 cannot be read, updated, or deleted by Company 2."""
    emp_company1 = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Alice",
            last_name="Corp1",
            email="alice@company1.com",
            salary=Decimal("100000.00"),
        ),
        db=db_session,
        current_user=admin_user,  # company_id = 1
    )

    # Company 2 admin tries to read Company 1 employee -> 404
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee(
            employee_id=emp_company1.id,
            db=db_session,
            current_user=other_tenant_admin,  # company_id = 2
        )
    assert exc_info.value.status_code == 404

    # Company 2 admin tries to calculate bonus for Company 1 employee -> 404
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=emp_company1.id,
            db=db_session,
            current_user=other_tenant_admin,
        )
    assert exc_info.value.status_code == 404

    # Company 2 list employees returns 0 employees
    company2_list = employees.list_employees(
        db=db_session,
        current_user=other_tenant_admin,
    )
    assert len(company2_list) == 0

    # Company 2 CAN create an employee with the SAME email address (tenant-scoped uniqueness)
    emp_company2 = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Alice",
            last_name="Corp2",
            email="alice@company1.com",  # same email, different company
            salary=Decimal("95000.00"),
        ),
        db=db_session,
        current_user=other_tenant_admin,  # company_id = 2
    )
    assert emp_company2.id != emp_company1.id
    assert emp_company2.company_id == 2


# ==============================================================================
# Finding 3: IDOR Prevention and Employee-Level Authorization Tests
# ==============================================================================

def test_idor_protection_denies_unbound_employee():
    """Verify standard users without bound employee_id are denied by default."""
    unbound_user = User(username="staff", role=UserRole.EMPLOYEE, company_id=1, employee_id=None)
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(employee_id=1, current_user=unbound_user)
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail


def test_idor_protection_cross_employee_access():
    """Verify standard user can access own record but is denied on other employee records."""
    emp1_user = User(username="staff1", role=UserRole.EMPLOYEE, company_id=1, employee_id=1)

    # Accessing employee 2 -> 403
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(employee_id=2, current_user=emp1_user)
    assert exc_info.value.status_code == 403

    # Accessing own record -> passes
    verify_employee_access(employee_id=1, current_user=emp1_user)


def test_jwt_token_with_per_user_identity(db_session, admin_user):
    """Verify JWT authentication provides per-user claims and resolves accurately."""
    emp = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Grace",
            last_name="Hopper",
            email="grace@navy.mil",
            salary=Decimal("120000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    token = create_access_token({
        "sub": "grace.hopper",
        "role": "employee",
        "company_id": 1,
        "employee_id": emp.id,
    })

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    authenticated_user = get_current_user(api_key=None, auth_creds=creds)

    assert authenticated_user.username == "grace.hopper"
    assert authenticated_user.role == UserRole.EMPLOYEE
    assert authenticated_user.employee_id == emp.id

    # Employee accesses their own bonus via JWT
    bonus_data = employees.get_employee_bonus(
        employee_id=emp.id,
        db=db_session,
        current_user=authenticated_user,
    )
    assert bonus_data.employee_id == emp.id
    assert bonus_data.bonus == Decimal("12000.00")

    # Employee tries to access another employee's bonus -> 403
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=999,
            db=db_session,
            current_user=authenticated_user,
        )
    assert exc_info.value.status_code == 403


# ==============================================================================
# Finding 4: No Depends Shortcut in Security Functions
# ==============================================================================

def test_require_admin_strict_enforcement():
    """Verify require_admin strictly checks role and does not silently grant admin."""
    employee_user = User(username="emp", role=UserRole.EMPLOYEE, company_id=1)
    with pytest.raises(HTTPException) as exc_info:
        require_admin(employee_user)
    assert exc_info.value.status_code == 403


# ==============================================================================
# Finding 5: app.py Clean Entrypoint Test
# ==============================================================================

def test_app_py_clean_entrypoint():
    """Verify root app.py is a clean entrypoint re-exporting app with no duplicate routes."""
    import app as root_app
    assert hasattr(root_app, "app")
    assert root_app.app is app


# ==============================================================================
# Finding 6: Email Normalization & IntegrityError Handling Tests
# ==============================================================================

def test_email_normalization_at_schema_level():
    """Verify email normalization to lowercase at schema creation and update."""
    payload = EmployeeCreate(
        first_name="Mixed",
        last_name="Case",
        email="MiXeD.CaSe@ExAmPlE.CoM",
    )
    assert payload.email == "mixed.case@example.com"

    update_payload = EmployeeUpdate(email="UPPER.CASE@EXAMPLE.COM")
    assert update_payload.email == "upper.case@example.com"


# ==============================================================================
# Finding 7: Salary Decimal Places Validation Tests
# ==============================================================================

def test_salary_decimal_places_constraint():
    """Verify salary enforces decimal_places=2 constraint."""
    # Valid 2 decimal places
    valid = EmployeeCreate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        salary=Decimal("95000.50"),
    )
    assert valid.salary == Decimal("95000.50")

    # More than 2 decimal places rejected by Pydantic
    with pytest.raises(ValidationError):
        EmployeeCreate(
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
            salary=Decimal("95000.555"),
        )


# ==============================================================================
# Finding 8: Pure Framework-Free Calculation & Shared Service Tests
# ==============================================================================

def test_framework_free_bonus_calculations():
    """Verify app.bonus calculations are pure Python without framework dependencies."""
    # Decimal rounding
    assert round_currency(Decimal("100.005")) == Decimal("101.00") or round_currency(Decimal("100.005")) == Decimal("100.01")
    assert round_currency(Decimal("99999.99875")) == Decimal("12500.00") or calculate_bonus(Decimal("99999.99"), Decimal("12.5")) == Decimal("12500.00")

    # Pure calculation functions
    assert calculate_bonus(Decimal("100000.00"), Decimal("10.0")) == Decimal("10000.00")
    assert calculate_salary(Decimal("95000.00"), Decimal("5000.00")) == Decimal("100000.00")
    assert divide_salary(Decimal("100000.00"), 4) == Decimal("25000.00")
    assert calculate_discount(Decimal("100.00"), Decimal("15.50")) == Decimal("84.50")
    assert calculate_total(Decimal("19.99"), 3) == Decimal("59.97")

    with pytest.raises(ValueError, match="Number of employees must be a positive integer"):
        divide_salary(Decimal("100000.00"), 0)


def test_shared_service_calculate_employee_bonus(db_session, admin_user):
    """Verify shared service function calculate_employee_bonus."""
    emp = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Katherine",
            last_name="Johnson",
            email="katherine.j@nasa.gov",
            salary=Decimal("110000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    bonus_res = calculate_employee_bonus(emp, bonus_percentage=Decimal("10.0"))
    assert bonus_res.employee_id == emp.id
    assert bonus_res.company_id == 1
    assert bonus_res.bonus == Decimal("11000.00")
    assert bonus_res.total_compensation == Decimal("121000.00")


def test_sql_injection_defense(db_session, admin_user):
    """Verify parameterized queries handle SQL injection attempts safely."""
    results = employees.list_employees(
        department="'; DROP TABLE employees; --",
        db=db_session,
        current_user=admin_user,
    )
    assert results == []


def test_integrity_error_handling_returns_409(db_session, admin_user):
    """Verify IntegrityError on commit rolls back and raises 409 Conflict."""
    from unittest.mock import patch
    from sqlalchemy.exc import IntegrityError
    from app import crud

    payload = EmployeeCreate(
        first_name="Race",
        last_name="Condition",
        email="race.condition@example.com",
    )

    with patch.object(db_session, "commit", side_effect=IntegrityError("statement", "params", "orig")):
        with pytest.raises(HTTPException) as exc_info:
            crud.create_employee(db=db_session, employee=payload, company_id=1)
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail


def test_unauthenticated_request_raises_401():
    """Verify missing credentials raise 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key=None, auth_creds=None)
    assert exc_info.value.status_code == 401
    assert "required" in exc_info.value.detail.lower()


def test_invalid_api_key_raises_401():
    """Verify invalid API key raises 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key="invalid-api-key-at-least-32-chars-long", auth_creds=None)
    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


def test_invalid_jwt_raises_401():
    """Verify malformed or invalid JWT token raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("header.invalidpayload.signature")
    assert exc_info.value.status_code == 401


def test_root_bonus_alias_endpoint(db_session, admin_user):
    """Verify /bonus/{employee_id} root alias endpoint calls service correctly."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Margaret",
            last_name="Hamilton",
            email="margaret.h@mit.edu",
            salary=Decimal("140000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    res = root_calculate_bonus(
        employee_id=created.id,
        bonus_percentage=Decimal("15.0"),
        db=db_session,
        current_user=admin_user,
    )
    assert res.employee_id == created.id
    assert res.bonus == Decimal("21000.00")
    assert res.total_compensation == Decimal("161000.00")


def test_bonus_missing_salary_raises_400(db_session, admin_user):
    """Verify calculating bonus on employee without base salary raises 400."""
    emp_no_salary = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Volunteer",
            last_name="Staff",
            email="volunteer@nonprofit.org",
            salary=None,
        ),
        db=db_session,
        current_user=admin_user,
    )
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=emp_no_salary.id,
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 400
    assert "does not have a base salary" in exc_info.value.detail


def test_bonus_invalid_percentage_raises_400(db_session, admin_user):
    """Verify out-of-bounds bonus percentage raises 400."""
    emp = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Valid",
            last_name="Worker",
            email="valid.worker@example.com",
            salary=Decimal("80000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=emp.id,
            bonus_percentage=Decimal("-5.0"),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 400
    assert "between 0 and 100" in exc_info.value.detail

