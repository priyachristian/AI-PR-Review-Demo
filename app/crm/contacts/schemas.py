from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ContactCreate(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=150)
    full_name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(default=None, min_length=5, max_length=30)
    job_title: Optional[str] = Field(default=None, max_length=100)
    is_primary: bool = False

    @field_validator("account_name", "full_name", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ContactUpdate(BaseModel):
    account_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=5, max_length=30)
    job_title: Optional[str] = Field(default=None, max_length=100)
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None


class ContactResponse(BaseModel):
    id: int
    company_id: int
    account_name: str
    full_name: str
    email: str
    phone: Optional[str] = None
    job_title: Optional[str] = None
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
