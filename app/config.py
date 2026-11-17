from decimal import Decimal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    API_TITLE: str = "Employee Management API"
    API_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./employees.db"

    # Security & Authentication Configuration - required, minimum 32 chars, no committed defaults
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Cryptographic secret key for JWT token signing (required, min 32 chars)",
    )
    API_KEY: str = Field(
        ...,
        min_length=32,
        description="Static API key for standard employee access (required, min 32 chars)",
    )
    ADMIN_API_KEY: str = Field(
        ...,
        min_length=32,
        description="Static API key for administrative access (required, min 32 chars)",
    )
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
