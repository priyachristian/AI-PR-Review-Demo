from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional
from fastapi import Depends, FastAPI, Path, Query
from sqlalchemy.orm import Session

from app import schemas, security
from app.config import settings
from app.database import Base, engine, get_db
from app.routers import employees


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create SQLite database tables if they do not exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.API_TITLE,
    description="Clean, production-ready, secure FastAPI service with tenant scoping and RBAC authorization.",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# Register versioned API router
app.include_router(employees.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.API_TITLE,
        "status": "healthy",
        "version": settings.API_VERSION,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.get(
    "/bonus/{employee_id}",
    response_model=schemas.BonusResponse,
    tags=["Employees"],
    summary="Convenience alias for /api/v1/employees/{employee_id}/bonus",
)
def root_calculate_bonus(
    employee_id: int = Path(..., ge=1, description="Employee ID (positive integer)"),
    bonus_percentage: Optional[Decimal] = Query(
        default=None,
        ge=0,
        le=settings.MAX_BONUS_PERCENTAGE,
        description="Bonus percentage (0 to 100)",
    ),
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    """Direct alias to employee bonus calculation service."""
    return employees.get_employee_bonus(
        employee_id=employee_id,
        bonus_percentage=bonus_percentage,
        db=db,
        current_user=current_user,
    )
