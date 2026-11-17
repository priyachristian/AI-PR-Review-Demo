from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import Base, engine
from app.routers import employees


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create SQLite database tables if they do not exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Employee Management API",
    description="Clean, lightweight FastAPI demo application with SQLite database for testing AI PR Review Agents.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register route handlers
app.include_router(employees.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Employee Management API",
        "status": "healthy",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
