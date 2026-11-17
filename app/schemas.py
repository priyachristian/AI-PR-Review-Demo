from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
        max_length=100,
        description="Department name",
        examples=["Engineering"],
    )
    role: str = Field(
        default="Software Engineer",
        max_length=100,
        description="Job role or title",
        examples=["Backend Developer"],
    )
    salary: Optional[float] = Field(
        default=None,
        ge=0,
        description="Annual base compensation",
        examples=[95000.0],
    )
    is_active: bool = Field(
        default=True,
        description="Active employment status",
        examples=[True],
    )


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    department: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=100)
    salary: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)


class EmployeeResponse(EmployeeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
