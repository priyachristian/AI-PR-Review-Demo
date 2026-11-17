from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmployeeBase(BaseModel):
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Employee's first name",
        examples=["Jane"],
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Employee's last name",
        examples=["Doe"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique corporate email address",
        examples=["jane.doe@example.com"],
    )
    department: str = Field(
        default="Engineering",
        min_length=1,
        max_length=100,
        description="Department name",
        examples=["Engineering"],
    )
    role: str = Field(
        default="Software Engineer",
        min_length=1,
        max_length=100,
        description="Job role or title",
        examples=["Backend Developer"],
    )
    salary: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=100_000_000,
        description="Annual base compensation in USD",
        examples=[Decimal("95000.00")],
    )
    is_active: bool = Field(
        default=True,
        description="Active employment status",
        examples=[True],
    )

    @field_validator("first_name", "last_name", "department", "role", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, value: str) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("Field cannot be empty or contain only whitespace.")
            return stripped
        return value


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    department: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, min_length=1, max_length=100)
    salary: Optional[Decimal] = Field(default=None, ge=0, le=100_000_000)
    is_active: Optional[bool] = Field(default=None)

    @field_validator("first_name", "last_name", "department", "role", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("Field cannot be empty or contain only whitespace.")
            return stripped
        return value


class EmployeeResponse(EmployeeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BonusResponse(BaseModel):
    employee_id: int = Field(..., description="Employee ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    department: str = Field(..., description="Department")
    role: str = Field(..., description="Role")
    salary: Decimal = Field(..., description="Base salary")
    bonus_percentage: Decimal = Field(..., description="Bonus percentage applied (0-100)")
    bonus: Decimal = Field(..., description="Calculated bonus amount")
    total_compensation: Decimal = Field(..., description="Total compensation (salary + bonus)")

    model_config = ConfigDict(from_attributes=True)
