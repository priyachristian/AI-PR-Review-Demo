from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, Text

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrmOpportunityDeal(Base):
    """Tenant-scoped CRM Opportunity / Deal entity."""

    __tablename__ = "crm_opportunities_deals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    deal_name = Column(String(150), nullable=False)
    account_name = Column(String(150), nullable=False)
    stage = Column(String(40), nullable=False, default="PROSPECTING")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    probability_pct = Column(Integer, nullable=False, default=10)
    expected_close_date = Column(Date, nullable=False)
    loss_reason = Column(Text, nullable=True)
    owner_username = Column(String(80), nullable=False, default="sales_rep")
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)
