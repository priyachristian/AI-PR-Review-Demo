from decimal import Decimal
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    API_TITLE: str = "Employee Management API"
    API_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./employees.db"

    # Security & Authentication Configuration
    # Defaults provided for development/testing; must be overridden via environment in production
    SECRET_KEY: str = "dev-secret-key-must-be-changed-in-production-min-32-chars"
    API_KEY: str = "demo-employee-key-abc456"
    ADMIN_API_KEY: str = "demo-admin-key-xyz123"
    TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Business Logic Defaults
    DEFAULT_BONUS_PERCENTAGE: Decimal = Decimal("10.0")
    MAX_BONUS_PERCENTAGE: Decimal = Decimal("100.0")
    MAX_SALARY_LIMIT: Decimal = Decimal("100000000.00")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
