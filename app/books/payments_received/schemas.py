from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

PaymentMode = Literal["CASH", "BANK_TRANSFER", "CHEQUE", "UPI", "CARD"]


class PaymentReceivedCreate(BaseModel):
    payment_number: str = Field(..., min_length=1, max_length=50)
    customer_name: str = Field(..., min_length=1, max_length=120)
    payment_mode: PaymentMode
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    payment_date: date
    reference_number: Optional[str] = Field(default=None, max_length=100)

    @field_validator("payment_number", "customer_name", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value


class PaymentReceivedUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    payment_date: Optional[date] = None
    payment_mode: Optional[PaymentMode] = None
    reference_number: Optional[str] = Field(default=None, max_length=100)


class PaymentAllocationResponse(BaseModel):
    id: int
    company_id: int
    payment_id: int
    invoice_id: int
    amount_applied: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentReceivedResponse(BaseModel):
    id: int
    company_id: int
    payment_number: str
    customer_name: str
    payment_mode: str
    status: str
    amount: Decimal
    unused_amount: Decimal
    payment_date: date
    reference_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    allocations: List[PaymentAllocationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
