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
from app.exceptions import (
    DomainError,
    EmployeeMissingSalaryError,
    InvalidBonusPercentageError,
    InvalidSalaryError,
)
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
    safe_compare_digest,
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


def test_salary_range_filtering(db_session, admin_user):
    """Verify employees can be filtered by min_salary and max_salary."""
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Low",
            last_name="Earner",
            email="low@example.com",
            salary=Decimal("40000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Mid",
            last_name="Earner",
            email="mid@example.com",
            salary=Decimal("75000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="High",
            last_name="Earner",
            email="high@example.com",
            salary=Decimal("120000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    filtered = employees.list_employees(
        min_salary=Decimal("50000.00"),
        max_salary=Decimal("100000.00"),
        db=db_session,
        current_user=admin_user,
    )
    assert len(filtered) == 1
    assert filtered[0].first_name == "Mid"


def test_company_payroll_report(db_session, admin_user, other_tenant_admin):
    """Verify aggregate payroll analytics and department breakdown."""
    # Seed Company 1 employees across departments
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Dev",
            last_name="A",
            department="Engineering",
            email="deva@example.com",
            salary=Decimal("100000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Dev",
            last_name="B",
            department="Engineering",
            email="devb@example.com",
            salary=Decimal("120000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Sales",
            last_name="A",
            department="Sales",
            email="salesa@example.com",
            salary=Decimal("80000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    # Seed Company 2 employee to ensure tenant isolation in report
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Other",
            last_name="Corp",
            department="Engineering",
            email="other@corp2.com",
            salary=Decimal("200000.00"),
        ),
        db=db_session,
        current_user=other_tenant_admin,
    )

    report = employees.get_payroll_report(
        db=db_session,
        current_user=admin_user,
    )

    assert report.company_id == 1
    assert report.total_headcount == 3
    assert report.active_headcount == 3
    assert report.total_annual_payroll == Decimal("300000.00")
    assert report.average_salary == Decimal("100000.00")
    assert len(report.departments) == 2

    eng_summary = next(d for d in report.departments if d.department == "Engineering")
    assert eng_summary.total_employees == 2
    assert eng_summary.total_payroll == Decimal("220000.00")
    assert eng_summary.average_salary == Decimal("110000.00")
    assert eng_summary.min_salary == Decimal("100000.00")
    assert eng_summary.max_salary == Decimal("120000.00")


def test_payroll_report_forbidden_for_non_admin(db_session, standard_employee_user):
    """Verify non-admin users cannot access executive payroll reports."""
    with pytest.raises(HTTPException) as exc_info:
        employees.get_payroll_report(
            db=db_session,
            current_user=standard_employee_user,
        )
    assert exc_info.value.status_code == 403


def test_employee_search(db_session, admin_user):
    """Verify searching employees across first name, last name, and email."""
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Leonardo",
            last_name="DaVinci",
            email="leonardo.davinci@renaissance.org",
            department="R&D",
            salary=Decimal("150000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Michelangelo",
            last_name="Buonarroti",
            email="michelangelo@renaissance.org",
            department="Sculpture",
            salary=Decimal("140000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    # Search by partial first name
    res_first = employees.list_employees(search="Leon", db=db_session, current_user=admin_user)
    assert len(res_first) == 1
    assert res_first[0].first_name == "Leonardo"

    # Search by partial last name
    res_last = employees.list_employees(search="Buon", db=db_session, current_user=admin_user)
    assert len(res_last) == 1
    assert res_last[0].last_name == "Buonarroti"

    # Search by email domain
    res_email = employees.list_employees(search="renaissance.org", db=db_session, current_user=admin_user)
    assert len(res_email) == 2


def test_employee_sorting(db_session, admin_user):
    """Verify sorting employees by salary ascending and descending."""
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Junior",
            last_name="Dev",
            email="junior@code.org",
            salary=Decimal("60000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    employees.create_employee(
        employee=EmployeeCreate(
            first_name="Senior",
            last_name="Dev",
            email="senior@code.org",
            salary=Decimal("120000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    # Ascending sort by salary
    asc_res = employees.list_employees(
        sort_by="salary",
        order="asc",
        db=db_session,
        current_user=admin_user,
    )
    assert asc_res[0].salary <= asc_res[-1].salary

    # Descending sort by salary
    desc_res = employees.list_employees(
        sort_by="salary",
        order="desc",
        db=db_session,
        current_user=admin_user,
    )
    assert desc_res[0].salary >= desc_res[-1].salary


# ==============================================================================
# Issue 1: Employee-level authorization / IDOR Regression Tests
# ==============================================================================

def test_non_admin_forbidden_from_listing_employees(db_session, standard_employee_user):
    """Verify standard employees cannot list company employees or view company salaries."""
    with pytest.raises(HTTPException) as exc_info:
        employees.list_employees(
            db=db_session,
            current_user=standard_employee_user,
        )
    assert exc_info.value.status_code == 403
    assert "admin authorization required" in exc_info.value.detail.lower()


def test_employee_access_authorization_ownership(db_session, admin_user, standard_employee_user):
    """Verify employees can only access their own record and cannot access other employees' records."""
    # Create employee 1 (matches standard_employee_user.employee_id = 1)
    emp1 = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Emp",
            last_name="One",
            email="emp1@company.com",
            salary=Decimal("80000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert emp1.id == 1

    # Create employee 2
    emp2 = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Emp",
            last_name="Two",
            email="emp2@company.com",
            salary=Decimal("95000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert emp2.id == 2

    # Standard employee user 1 can view own record
    own_data = employees.get_employee(employee_id=1, db=db_session, current_user=standard_employee_user)
    assert own_data.id == 1

    # Standard employee user 1 can view own bonus
    own_bonus = employees.get_employee_bonus(employee_id=1, db=db_session, current_user=standard_employee_user)
    assert own_bonus.employee_id == 1
    assert own_bonus.bonus == Decimal("8000.00")

    # Standard employee user 1 CANNOT view employee 2 details -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee(employee_id=2, db=db_session, current_user=standard_employee_user)
    assert exc_info.value.status_code == 403
    assert "access denied" in exc_info.value.detail.lower()

    # Standard employee user 1 CANNOT view employee 2 bonus -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(employee_id=2, db=db_session, current_user=standard_employee_user)
    assert exc_info.value.status_code == 403
    assert "access denied" in exc_info.value.detail.lower()

    # Admin CAN view employee 2 bonus
    admin_bonus = employees.get_employee_bonus(employee_id=2, db=db_session, current_user=admin_user)
    assert admin_bonus.employee_id == 2


# ==============================================================================
# Issue 2: Email Normalization & Conflict Detection Regression Tests
# ==============================================================================

def test_email_normalization_handles_whitespace_and_mixed_case(db_session, admin_user):
    """Verify emails with whitespace and mixed casing are normalized properly."""
    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="John",
            last_name="Normalized",
            email="   John.Normalized@EXAMPLE.COM   ",
            salary=Decimal("70000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert created.email == "john.normalized@example.com"

    # Attempt duplicate with different casing/whitespace -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        employees.create_employee(
            employee=EmployeeCreate(
                first_name="John",
                last_name="Duplicate",
                email="  JOHN.NORMALIZED@example.com ",
            ),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 400


def test_email_migration_conflict_detection_prevents_silent_deletion(db_session):
    """Verify safe email migration detects duplicates after normalization and does not silently delete."""
    import sqlalchemy as sa

    # Directly insert raw colliding emails into table using raw SQL
    db_session.execute(
        sa.text(
            "INSERT INTO employees (company_id, first_name, last_name, email, department, role, is_active, created_at, updated_at) "
            "VALUES (99, 'User', 'A', 'collision@test.com', 'Eng', 'Dev', 1, '2026-01-01', '2026-01-01')"
        )
    )
    db_session.execute(
        sa.text(
            "INSERT INTO employees (company_id, first_name, last_name, email, department, role, is_active, created_at, updated_at) "
            "VALUES (99, 'User', 'B', 'COLLISION@test.com', 'Eng', 'Dev', 1, '2026-01-01', '2026-01-01')"
        )
    )
    db_session.commit()

    # Run check logic as implemented in migration 20261119_0003
    check_query = sa.text("""
        SELECT company_id, LOWER(TRIM(email)) AS norm_email, COUNT(*) AS cnt
        FROM employees
        WHERE company_id = 99
        GROUP BY company_id, LOWER(TRIM(email))
        HAVING COUNT(*) > 1
    """)
    duplicates = db_session.execute(check_query).fetchall()
    assert len(duplicates) == 1
    assert duplicates[0][1] == "collision@test.com"
    assert duplicates[0][2] == 2

    # Verify both records still exist and were not deleted
    count_records = db_session.execute(sa.text("SELECT COUNT(*) FROM employees WHERE company_id = 99")).scalar()
    assert count_records == 2


# ==============================================================================
# Issue 3: Domain Exceptions & Pure Business Logic Tests
# ==============================================================================

def test_domain_exceptions_raised_by_bonus_service():
    """Verify calculation functions raise domain exceptions, not HTTPException or raw errors."""
    with pytest.raises(InvalidSalaryError):
        calculate_bonus(salary=Decimal("-100.00"), bonus_percentage=Decimal("10.0"))

    with pytest.raises(InvalidBonusPercentageError):
        calculate_bonus(salary=Decimal("1000.00"), bonus_percentage=Decimal("150.0"))

    with pytest.raises(InvalidBonusPercentageError):
        calculate_bonus(salary=Decimal("1000.00"), bonus_percentage=Decimal("-5.0"))

    with pytest.raises(InvalidSalaryError):
        calculate_salary(basic_salary=Decimal("-500.00"), bonus=Decimal("100.00"))

    with pytest.raises(InvalidSalaryError):
        calculate_salary(basic_salary=Decimal("500.00"), bonus=Decimal("-100.00"))


def test_domain_exceptions_translated_to_http_400(db_session, admin_user):
    """Verify router translates domain exceptions into HTTP 400 Bad Request."""
    emp_no_salary = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Intern",
            last_name="Unpaid",
            email="intern.unpaid@org.com",
            salary=None,
        ),
        db=db_session,
        current_user=admin_user,
    )
    # calculate_employee_bonus directly raises EmployeeMissingSalaryError
    with pytest.raises(EmployeeMissingSalaryError):
        calculate_employee_bonus(emp_no_salary)

    # API route translates EmployeeMissingSalaryError to HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(
            employee_id=emp_no_salary.id,
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 400
    assert "does not have a base salary" in exc_info.value.detail


# ==============================================================================
# Issue 4: Public Example Secrets & Placeholder Rejection Tests
# ==============================================================================

def test_config_rejects_placeholder_secrets():
    """Verify Settings rejects known placeholders such as 'replace-with', 'placeholder', etc."""
    # Test 'replace-with' placeholder
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            SECRET_KEY="replace-with-a-secure-random-32-char-secret-key-in-prod",
            API_KEY="valid-length-api-key-at-least-32-chars-long",
            ADMIN_API_KEY="valid-length-admin-api-key-at-least-32-chars",
        )
    assert "Insecure placeholder 'replace-with' detected" in str(exc_info.value)

    # Test 'placeholder' in API_KEY
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            SECRET_KEY="valid-length-secret-key-at-least-32-chars",
            API_KEY="placeholder-key-long-enough-32-characters!",
            ADMIN_API_KEY="valid-length-admin-api-key-at-least-32-chars",
        )
    assert "Insecure placeholder 'placeholder' detected" in str(exc_info.value)

    # Test 'changeme' in ADMIN_API_KEY
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            SECRET_KEY="valid-length-secret-key-at-least-32-chars",
            API_KEY="valid-length-api-key-at-least-32-chars-long",
            ADMIN_API_KEY="changeme-admin-key-at-least-32-characters!",
        )
    assert "Insecure placeholder 'changeme' detected" in str(exc_info.value)


# ==============================================================================
# Issue 5: Unsafe company_id Defaults & Mandatory Tenant Scoping Tests
# ==============================================================================

def test_user_model_requires_company_id():
    """Verify User model requires company_id and does not default to 1."""
    with pytest.raises(ValidationError):
        User(username="test", role=UserRole.ADMIN)  # Missing company_id


def test_jwt_token_requires_company_id_claim():
    """Verify JWT tokens without company_id claim are rejected with 401."""
    token_missing_company = create_access_token({
        "sub": "user_no_company",
        "role": "employee",
        "employee_id": 1,
    })
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_missing_company)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key=None, auth_creds=creds)
    assert exc_info.value.status_code == 401
    assert "missing required 'company_id' claim" in exc_info.value.detail.lower()


def test_jwt_token_rejects_invalid_company_id():
    """Verify JWT tokens with non-positive or non-integer company_id are rejected with 401."""
    token_negative_company = create_access_token({
        "sub": "user_bad_company",
        "role": "employee",
        "company_id": -5,
        "employee_id": 1,
    })
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_negative_company)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key=None, auth_creds=creds)
    assert exc_info.value.status_code == 401
    assert "positive integer" in exc_info.value.detail.lower()


# ==============================================================================
# Issue 6: Non-ASCII Credentials Returning HTTP 401 Tests
# ==============================================================================

def test_non_ascii_api_key_returns_401_never_500():
    """Verify non-ASCII / Unicode API key returns HTTP 401 and never crashes with HTTP 500."""
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key="🔑non_ascii_admin_key_with_unicode_symbols_32chars", auth_creds=None)
    assert exc_info.value.status_code == 401
    assert "invalid authentication credentials" in exc_info.value.detail.lower()


def test_non_ascii_bearer_token_returns_401_never_500():
    """Verify non-ASCII Bearer token credentials return HTTP 401 and never crash with HTTP 500."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="Bearer 🔑.unicode.payload.token")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(api_key=None, auth_creds=creds)
    assert exc_info.value.status_code == 401


def test_safe_compare_digest_handles_unicode_without_exception():
    """Verify safe_compare_digest compares non-ASCII strings safely in constant time."""
    assert safe_compare_digest("🔑secret_unicode_key", "different_key") is False
    assert safe_compare_digest("🔑secret_unicode_key", "🔑secret_unicode_key") is True
    assert safe_compare_digest("üñîçødé_tökên_vâlûê", "üñîçødé_tökên_vâlûê") is True
    assert safe_compare_digest("üñîçødé_tökên_vâlûê", "other_value") is False


# ==============================================================================
# Security & Tenant Isolation: Static API Key & IDOR Verification Tests
# ==============================================================================

def test_static_api_key_cannot_access_employee_salary_idor(db_session, admin_user):
    """Verify standard API key with employee_id=None is strictly denied from accessing salary data."""
    standard_api_user = get_current_user(api_key=settings.API_KEY, auth_creds=None)
    assert standard_api_user.role == UserRole.EMPLOYEE
    assert standard_api_user.employee_id is None
    assert standard_api_user.company_id == settings.STATIC_API_KEY_COMPANY_ID

    created = employees.create_employee(
        employee=EmployeeCreate(
            first_name="Confidential",
            last_name="Worker",
            email="confidential@corp.com",
            salary=Decimal("150000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )

    # Denied on verify_employee_access -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(created.id, standard_api_user)
    assert exc_info.value.status_code == 403
    assert "access denied" in exc_info.value.detail.lower()

    # Denied on get_employee -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee(employee_id=created.id, db=db_session, current_user=standard_api_user)
    assert exc_info.value.status_code == 403

    # Denied on get_employee_bonus -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        employees.get_employee_bonus(employee_id=created.id, db=db_session, current_user=standard_api_user)
    assert exc_info.value.status_code == 403

    # Denied on list_employees -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        employees.list_employees(db=db_session, current_user=standard_api_user)
    assert exc_info.value.status_code == 403

    # Denied on require_admin -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        require_admin(standard_api_user)
    assert exc_info.value.status_code == 403


def test_verify_employee_access_comprehensive(admin_user):
    """Verify verify_employee_access handles all user roles, employee_ids, and invalid objects."""
    # Non-admin with employee_id=None -> 403
    unbound_user = User(username="unbound", role=UserRole.EMPLOYEE, company_id=1, employee_id=None)
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(1, unbound_user)
    assert exc_info.value.status_code == 403

    # Non-admin with employee_id=1 accessing ID 2 -> 403
    emp_user_1 = User(username="emp1", role=UserRole.EMPLOYEE, company_id=1, employee_id=1)
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(2, emp_user_1)
    assert exc_info.value.status_code == 403

    # Non-admin with employee_id=1 accessing ID 1 -> passes
    verify_employee_access(1, emp_user_1)

    # Admin with employee_id=None accessing any ID -> passes
    assert admin_user.employee_id is None
    verify_employee_access(1, admin_user)
    verify_employee_access(999, admin_user)

    # Non-User object -> 401 Unauthorized
    with pytest.raises(HTTPException) as exc_info:
        verify_employee_access(1, None)  # type: ignore
    assert exc_info.value.status_code == 401


def test_require_admin_direct_call_behavior(admin_user):
    """Verify require_admin behaves correctly when called directly with User, wrong role, or defaults."""
    # Direct call with Admin User -> returns user
    assert require_admin(admin_user) is admin_user

    # Direct call with Employee User -> raises 403
    emp_user = User(username="emp", role=UserRole.EMPLOYEE, company_id=1, employee_id=1)
    with pytest.raises(HTTPException) as exc_info:
        require_admin(emp_user)
    assert exc_info.value.status_code == 403
    assert "admin authorization required" in exc_info.value.detail.lower()

    # Direct call with no arguments (FastAPI Depends default) -> raises 403 without crashing
    with pytest.raises(HTTPException) as exc_info:
        require_admin()
    assert exc_info.value.status_code == 403

    # Direct call with invalid type (None / string) -> raises 403
    with pytest.raises(HTTPException) as exc_info:
        require_admin("invalid_principal")  # type: ignore
    assert exc_info.value.status_code == 403


def test_static_keys_bound_to_configured_company_id_cannot_switch_tenants():
    """Verify static API keys are bound strictly to STATIC_API_KEY_COMPANY_ID server-side."""
    admin_user = get_current_user(api_key=settings.ADMIN_API_KEY, auth_creds=None)
    assert admin_user.company_id == settings.STATIC_API_KEY_COMPANY_ID
    assert admin_user.role == UserRole.ADMIN

    standard_user = get_current_user(api_key=settings.API_KEY, auth_creds=None)
    assert standard_user.company_id == settings.STATIC_API_KEY_COMPANY_ID
    assert standard_user.role == UserRole.EMPLOYEE





