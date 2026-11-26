from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuotationLineCreate(BaseModel):
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


class QuotationLineResponse(QuotationLineCreate):
    id: int
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class BooksQuotationCreate(BaseModel):
    quote_number: str = Field(..., min_length=1, max_length=50)
    customer_name: str = Field(..., min_length=1, max_length=120)
    quote_date: date
    expiry_date: date
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    lines: List[QuotationLineCreate] = Field(..., min_length=1)

    @field_validator("quote_number", "customer_name", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "BooksQuotationCreate":
        if self.expiry_date < self.quote_date:
            raise ValueError("expiry_date cannot be earlier than quote_date.")
        return self


class BooksQuotationUpdate(BaseModel):
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    expiry_date: Optional[date] = None
    discount_amount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    lines: Optional[List[QuotationLineCreate]] = Field(default=None, min_length=1)


class BooksQuotationResponse(BaseModel):
    id: int
    company_id: int
    quote_number: str
    customer_name: str
    quote_date: date
    expiry_date: date
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    lines: List[QuotationLineResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
