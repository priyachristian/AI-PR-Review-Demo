from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LeadCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=150)
    contact_name: str = Field(..., min_length=1, max_length=120)
    phone: str = Field(..., min_length=5, max_length=30)
    email: Optional[EmailStr] = None
    source: str = Field(default="Inbound", min_length=1, max_length=80)
    potential_value: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    inquiry_date: date = Field(default_factory=date.today)

    @field_validator("company_name", "contact_name", "phone", "source", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value


class LeadUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    contact_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=30)
    email: Optional[EmailStr] = None
    potential_value: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)


class LeadStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)
    lost_reason: Optional[str] = Field(default=None, max_length=500)


class LeadResponse(BaseModel):
    id: int
    company_id: int
    company_name: str
    contact_name: str
    phone: str
    email: Optional[str] = None
    source: str
    status: str
    potential_value: Optional[Decimal] = None
    inquiry_date: date
    lost_reason: Optional[str] = None
    is_qualified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
