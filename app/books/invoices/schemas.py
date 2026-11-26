from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InvoiceLineCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=200)
    quantity: Decimal = Field(..., gt=0, decimal_places=2)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    tax_rate_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, decimal_places=2)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Line item description cannot be empty.")
            return cleaned
        return value


class InvoiceLineResponse(InvoiceLineCreate):
    id: int
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=50)
    customer_name: str = Field(..., min_length=1, max_length=120)
    issue_date: date
    due_date: date
    lines: List[InvoiceLineCreate] = Field(..., min_length=1)

    @field_validator("invoice_number", "customer_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "InvoiceCreate":
        if self.due_date < self.issue_date:
            raise ValueError("due_date cannot be earlier than issue_date.")
        return self


class InvoiceUpdate(BaseModel):
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    due_date: Optional[date] = None
    lines: Optional[List[InvoiceLineCreate]] = Field(default=None, min_length=1)


class InvoiceResponse(BaseModel):
    id: int
    company_id: int
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    balance_due: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    lines: List[InvoiceLineResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
