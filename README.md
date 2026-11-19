# Employee Management Demo

A clean, production-style, lightweight **FastAPI** service backed by **SQLite** and **SQLAlchemy 2.0**, designed as an ideal target repository for testing and benchmarking **AI PR Review Agents**.

The `main` branch is kept completely functional, clean, and bug-free with 100% passing test coverage. You can branch off to `env/test` (or feature branches) to introduce intentional bugs, security flaws, performance regressions, or style issues to verify your AI reviewer's detection capabilities.

---

## Features

- **FastAPI Framework**: High-performance, asynchronous-ready REST API with automatic OpenAPI / Swagger documentation.
- **SQLite with SQLAlchemy 2.0**: Declarative ORM models, scoped session handling, and clean database lifecycle management.
- **Pydantic v2 Validation**: Strict data models, email validation, length constraints, and clear error responses.
- **Full CRUD Endpoints**:
  - `POST /api/v1/employees/` – Register an employee with duplicate email prevention.
  - `GET /api/v1/employees/` – List employees with pagination (`skip`, `limit`) and filters (`department`, `is_active`).
  - `GET /api/v1/employees/{employee_id}` – Fetch employee details with 404 handling.
  - `PUT /api/v1/employees/{employee_id}` – Partial/full updates with uniqueness validation.
  - `DELETE /api/v1/employees/{employee_id}` – Remove an employee record (204 No Content).
  - `GET /health` & `GET /` – Service health status endpoints.
- **Automated Test Suite**: Pytest suite using an isolated in-memory SQLite database (`sqlite:///:memory:`).
- **Zero External Infrastructure**: Self-contained SQLite database file (`employees.db`) requiring no external database server.

---

## Project Structure

```text
employee-management-demo/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app initialization, routes, and lifespan
│   ├── database.py        # SQLite engine, session maker, and get_db dependency
│   ├── models.py          # SQLAlchemy ORM models (Employee)
│   ├── schemas.py         # Pydantic schemas for request validation & responses
│   ├── crud.py            # Reusable database queries & mutations
│   └── routers/
│       ├── __init__.py
│       └── employees.py   # Employee CRUD REST API routes
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures with in-memory SQLite database
│   └── test_employees.py  # Comprehensive test cases covering all CRUD flows
├── .gitignore             # Standard Python, SQLite, and IDE ignore rules
├── pytest.ini             # Test runner configuration
├── requirements.txt       # Production & test dependencies
└── README.md              # Project documentation & PR review test guide
```

---

## Quickstart

### 1. Prerequisites
- Python 3.10+ (Python 3.11+ recommended)
- `pip` package manager

### 2. Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the API Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The application starts on `http://127.0.0.1:8000`. The SQLite database (`employees.db`) is automatically initialized on startup.

---

## Interactive Documentation

FastAPI provides automatic interactive Swagger UI and ReDoc documentation:

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Reference

### Health Checks

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `GET` | `/` | Root info & service metadata | `200 OK` |
| `GET` | `/health` | Service health status | `200 OK` |

### Employee CRUD & Analytics

| Method | Endpoint | Query Parameters | Description | Status Code | Required Role |
|---|---|---|---|---|---|
| `POST` | `/api/v1/employees/` | – | Create a new employee | `201 Created` / `400` / `409` | `admin` |
| `GET` | `/api/v1/employees/` | `skip`, `limit`, `department`, `is_active`, `min_salary`, `max_salary`, `search`, `sort_by`, `order` | List employees with filters, search & sorting | `200 OK` | `authenticated` |
| `GET` | `/api/v1/employees/reports/payroll` | – | Executive department payroll analytics | `200 OK` | `admin` |
| `GET` | `/api/v1/employees/{id}` | – | Get single employee by ID | `200 OK` / `404 Not Found` | `authenticated` (admin/owner) |
| `GET` | `/api/v1/employees/{id}/bonus` | `bonus_percentage` (0-100) | Calculate employee bonus & total compensation | `200 OK` / `400` / `404` | `authenticated` (admin/owner) |
| `GET` | `/bonus/{id}` | `bonus_percentage` (0-100) | Alias for bonus calculation | `200 OK` / `400` / `404` | `authenticated` (admin/owner) |
| `PUT` | `/api/v1/employees/{id}` | – | Update employee details | `200 OK` / `400` / `404` / `409` | `admin` |
| `DELETE` | `/api/v1/employees/{id}` | – | Delete employee | `204 No Content` / `404 Not Found` | `admin` |

### Authentication & Tenant Scoping

All endpoints enforce tenant isolation via `company_id` bound to the caller's authenticated principal. Authentication can be provided via either:

1. **Header API Key**:
   - Admin: `X-API-Key: <ADMIN_API_KEY>`
   - Employee: `X-API-Key: <API_KEY>`
2. **Bearer Token (JWT)**:
   - `Authorization: Bearer <signed_jwt>`
   - Claims: `{"sub": "<username>", "role": "admin|employee", "company_id": <int>, "employee_id": <int>}`

---

### Database Migrations (Alembic)

Database schema migrations are managed via Alembic:

```bash
# Apply pending migrations to database
alembic upgrade head

# Check current revision status
alembic current
```

### Sample Payload

**Create Employee (`POST /api/v1/employees/`):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane.doe@example.com",
  "department": "Engineering",
  "role": "Software Engineer",
  "salary": 95000.0,
  "is_active": true
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane.doe@example.com",
  "department": "Engineering",
  "role": "Software Engineer",
  "salary": 95000.0,
  "is_active": true,
  "created_at": "2026-11-17T05:30:00Z",
  "updated_at": "2026-11-17T05:30:00Z"
}
```

---

## Running Unit Tests

Execute the test suite with pytest:

```bash
python -m pytest
```

Tests run against an isolated in-memory SQLite database (`sqlite:///:memory:`) so your local `employees.db` file is never modified during test execution.

---

## Testing Your AI PR Review Agent

This repository is set up specifically for validating AI code review pipelines (e.g. GitHub Actions, PR webhooks, or CI bots).

### Recommended Workflow

1. **Keep `main` Clean**: Keep the `main` branch in a verified, clean state.
2. **Create Test Branch**:
   ```bash
   git checkout -b env/test
   ```
3. **Introduce Intentional Defects**: Edit one or more files to inject realistic bugs (see catalog below).
4. **Commit & Push to Remote**:
   ```bash
   git add .
   git commit -m "feat: add employee batch query and export"
   git push origin env/test
   ```
5. **Open a Pull Request**: Open a PR from `env/test` targeting `main`.
6. **Evaluate AI Reviewer**: Check if your AI agent detects the issues, comments on the specific lines, and provides correct recommendations.

---

### Bug Catalog for AI Review Testing

Here are suggested bug categories you can inject into `env/test`:

| Bug Category | Example Injection | What the AI Agent Should Flag |
|---|---|---|
| **SQL Injection** | Concatenating strings into `db.execute(text(f"SELECT * FROM employees WHERE department = '{dept}'"))` | Critical security alert: potential SQL injection vulnerability; use parameterized queries. |
| **Hardcoded Secrets** | Adding `API_KEY = "sk-live-9382109283019283"` or database passwords directly in code | Critical security alert: secret exposure; recommend environment variables or secrets manager. |
| **Resource Leak** | Opening a database connection or file without closing it or without using a context manager (`with open(...)`) | Warning / Performance: file descriptor / connection leak. |
| **Missing Input Validation** | Removing `EmailStr` and using `str` without format check, or allowing negative salaries | Bug / Data integrity: invalid email strings and negative salaries accepted. |
| **HTTP Status Code Violation** | Changing `POST` response code from `201 Created` to `200 OK`, or returning a body with `204 No Content` | REST compliance: incorrect HTTP semantics. |
| **Unhandled Exception / 500 Risk** | Accessing dictionary keys without `.get()` or removing 404 checks when an ID does not exist | Stability: Uncaught `AttributeError` or `KeyError` resulting in unhandled HTTP 500 error. |
| **Mutable Default Argument** | Defining a helper function with `def filter_records(items=[]):` | Python antipattern: default mutable argument shared across calls. |
| **Race Condition** | Performing email check and insert without database-level uniqueness constraint or transaction handling | Concurrency issue: potential race condition during concurrent inserts. |

---

## Example GitHub Action for Automated AI PR Review

You can add `.github/workflows/pr-review.yml` in your repository to trigger your AI agent on every PR:

```yaml
name: AI PR Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt

      - name: Run Test Suite
        run: |
          python -m pytest

      - name: Trigger AI Review Agent
        run: |
          # Call your AI PR review script / bot here
          echo "Triggering AI PR Review Agent..."
```
