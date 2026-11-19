from datetime import datetime, timedelta, timezone
from enum import Enum
import hmac
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import BaseModel

from app.config import settings


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class User(BaseModel):
    username: str
    role: UserRole
    company_id: int
    employee_id: Optional[int] = None


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def safe_compare_digest(val_a: str, val_b: str) -> bool:
    """
    Safely compare two strings in constant time without raising TypeError on non-ASCII characters.
    Converts both strings to UTF-8 bytes before comparing using hmac.compare_digest.
    """
    if not isinstance(val_a, str) or not isinstance(val_b, str):
        return False
    return hmac.compare_digest(val_a.encode("utf-8"), val_b.encode("utf-8"))


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT token containing user claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a signed JWT token, returning 401 on any failure."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
        )
    except (jwt.PyJWTError, UnicodeError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> User:
    """
    Authenticate request via JWT Bearer token or static API keys.
    Extracts tenant identity (company_id) and user identity (employee_id).
    Safely handles non-ASCII credentials returning HTTP 401 instead of 500.
    Tenant identity is strictly bound to credential claims / configuration (never client headers).
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

    # Check if candidate is a signed JWT
    if token_candidate.count(".") == 2:
        payload = decode_access_token(token_candidate)
        username = payload.get("sub", "jwt_user")
        role_str = payload.get("role", UserRole.EMPLOYEE.value)
        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.EMPLOYEE

        company_id_raw = payload.get("company_id")
        if company_id_raw is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing required 'company_id' claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            company_id = int(company_id_raw)
            if company_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 'company_id' claim must be a valid positive integer.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        emp_id = payload.get("employee_id")
        employee_id = int(emp_id) if emp_id is not None else None
        return User(
            username=username,
            role=role,
            company_id=company_id,
            employee_id=employee_id,
        )

    # Validate against Admin API Key using safe constant-time comparison
    # Tenant is strictly bound server-side to configured STATIC_API_KEY_COMPANY_ID
    if safe_compare_digest(token_candidate, settings.ADMIN_API_KEY):
        return User(
            username="admin_api_user",
            role=UserRole.ADMIN,
            company_id=settings.STATIC_API_KEY_COMPANY_ID,
            employee_id=None,
        )

    # Validate against Standard API Key using safe constant-time comparison
    # Tenant is strictly bound server-side to configured STATIC_API_KEY_COMPANY_ID
    if safe_compare_digest(token_candidate, settings.API_KEY):
        return User(
            username="standard_api_user",
            role=UserRole.EMPLOYEE,
            company_id=settings.STATIC_API_KEY_COMPANY_ID,
            employee_id=None,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Strictly enforce admin-only access without test bypasses."""
    if not isinstance(current_user, User) or current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required to access this resource.",
        )
    return current_user


def require_authenticated(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the caller has a verified authentication principal."""
    if not isinstance(current_user, User):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def verify_employee_access(employee_id: int, current_user: User) -> None:
    """
    Authorize access to an employee's sensitive salary/bonus records.
    - Admins have access within their tenant company.
    - Employees can ONLY access their own record if bound (denies unbound employee_id by default).
    Prevents IDOR on salary/bonus endpoints.
    """
    if not isinstance(current_user, User):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
        )

    if current_user.role == UserRole.ADMIN:
        return

    if current_user.employee_id is None or current_user.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to view employee ID {employee_id}.",
        )
