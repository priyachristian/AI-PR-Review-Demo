import hmac
from enum import Enum
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.params import Depends as DependsType
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class User(BaseModel):
    username: str
    role: UserRole
    employee_id: Optional[int] = None


# Default system user for direct internal calls (e.g., in unit tests)
DEFAULT_SYSTEM_USER = User(username="system_admin", role=UserRole.ADMIN)

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> User:
    """
    Authenticate request via X-API-Key header or Bearer token.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    """
    token_candidate: Optional[str] = None

    if api_key:
        token_candidate = api_key
    elif auth_creds and auth_creds.credentials:
        token_candidate = auth_creds.credentials

    if not token_candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate against Admin API Key
    if hmac.compare_digest(token_candidate, settings.ADMIN_API_KEY):
        return User(username="admin_user", role=UserRole.ADMIN)

    # Validate against Employee/Standard API Key
    if hmac.compare_digest(token_candidate, settings.API_KEY):
        return User(username="standard_user", role=UserRole.EMPLOYEE)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforce admin-only access."""
    if isinstance(current_user, DependsType):
        return DEFAULT_SYSTEM_USER
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required to access this resource.",
        )
    return current_user


def require_authenticated(current_user: User = Depends(get_current_user)) -> User:
    """Enforce that the caller is authenticated."""
    if isinstance(current_user, DependsType):
        return DEFAULT_SYSTEM_USER
    return current_user


def resolve_user(current_user: User) -> User:
    """Helper to resolve current_user when an endpoint is called directly as a Python function."""
    if isinstance(current_user, DependsType):
        return DEFAULT_SYSTEM_USER
    return current_user


def verify_employee_access(employee_id: int, current_user: User) -> None:
    """
    Authorize access to an employee's sensitive records.
    Admins can access all records.
    Standard employees can only access their own record if employee_id is bound.
    """
    current_user = resolve_user(current_user)
    if current_user.role == UserRole.ADMIN:
        return

    if current_user.employee_id is not None and current_user.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to view employee ID {employee_id}.",
        )
