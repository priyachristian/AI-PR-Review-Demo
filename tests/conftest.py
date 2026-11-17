import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test secrets are always present in environment
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long!!")
os.environ.setdefault("API_KEY", "test-employee-api-key-at-least-32-chars-long!")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-api-key-at-least-32-characters-long!!")

from app.database import Base
from app.security import User, UserRole

# In-memory SQLite database dedicated for tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh schema in-memory for each test and tear down afterwards."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def admin_user():
    return User(username="test_admin", role=UserRole.ADMIN, company_id=1)


@pytest.fixture
def standard_employee_user():
    return User(username="test_employee", role=UserRole.EMPLOYEE, company_id=1, employee_id=1)


@pytest.fixture
def other_tenant_admin():
    return User(username="other_admin", role=UserRole.ADMIN, company_id=2)
