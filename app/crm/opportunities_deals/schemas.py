from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpportunityDealCreate(BaseModel):
    deal_name: str = Field(..., min_length=1, max_length=150)
    account_name: str = Field(..., min_length=1, max_length=150)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    expected_close_date: date
    owner_username: str = Field(default="sales_rep", min_length=1, max_length=80)

    @field_validator("deal_name", "account_name", "owner_username", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or whitespace.")
            return cleaned
        return value


class OpportunityDealUpdate(BaseModel):
    deal_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    expected_close_date: Optional[date] = None
    owner_username: Optional[str] = Field(default=None, min_length=1, max_length=80)


class OpportunityStageTransition(BaseModel):
    stage: str = Field(..., min_length=1, max_length=40)
    loss_reason: Optional[str] = Field(default=None, max_length=500)


class OpportunityDealResponse(BaseModel):
    id: int
    company_id: int
    deal_name: str
    account_name: str
    stage: str
    amount: Decimal
    probability_pct: int
    expected_close_date: date
    loss_reason: Optional[str] = None
    owner_username: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineForecastSummary(BaseModel):
    company_id: int
    open_deals_count: int
    total_pipeline_amount: Decimal
    weighted_forecast_amount: Decimal
