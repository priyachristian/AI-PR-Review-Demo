from decimal import Decimal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    API_TITLE: str = "Employee Management API"
    API_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./employees.db"

    # Security & Authentication Configuration - required, minimum 32 chars, no committed defaults or placeholders
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

    @field_validator("SECRET_KEY", "API_KEY", "ADMIN_API_KEY")
    @classmethod
    def validate_secure_secret(cls, v: str) -> str:
        """Enforce strong production secrets and reject known placeholders."""
        if not v or len(v.strip()) < 32:
            raise ValueError("Secret must be at least 32 characters long.")

        v_lower = v.lower()
        disallowed_placeholders = [
            "replace-with",
            "placeholder",
            "changeme",
            "your-secret",
            "example",
            "demo-secret",
        ]
        for placeholder in disallowed_placeholders:
            if placeholder in v_lower:
                raise ValueError(
                    f"Insecure placeholder '{placeholder}' detected in secret configuration. "
                    "Generate a secure production key using 'secrets.token_urlsafe(48)'."
                )
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
